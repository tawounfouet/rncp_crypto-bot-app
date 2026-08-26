"""Service performances Spot backed by user bot runtime APIs."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from mocks.db import MockStore
from mocks.factories import build_performance_snapshot
from mocks.scenarios import MockScenario
from schemas.performance import (
    BotPerformanceContribution,
    EquityPoint,
    PerformanceDashboard,
    PerformanceDecisionHistory,
    PerformanceMetrics,
    PerformanceOrderHistory,
    PerformancePnlPoint,
    PerformanceSnapshot,
    PerformanceTradeHistory,
    PerformanceUnavailableReason,
    TradeJournalEntry,
    UserPerformanceGlobal,
)
from services.auth_api_client import ApiResponse, AuthApiClient
from services.base import ServiceError, raise_if_forced_error, simulate_latency
from services.bot_control_service import BotControlService
from services.runtime_mode import allow_mock_fallback, backend_required_message
from state.session import get_access_token, get_refresh_token, set_auth_tokens


class PerformanceService:
    def __init__(self, store: MockStore, client: AuthApiClient | None = None) -> None:
        self.store = store
        self.client = client or AuthApiClient()

    def get_snapshot(
        self,
        bot_id: str,
        period_days: int,
        scenario_override: MockScenario | None = None,
    ) -> PerformanceSnapshot:
        if get_access_token():
            return self._get_snapshot_backend(bot_id=bot_id, period_days=period_days)
        if not allow_mock_fallback():
            raise ServiceError(backend_required_message("les performances Spot"))
        return self._get_snapshot_mock(bot_id, period_days, scenario_override)

    def get_dashboard(
        self,
        *,
        period_days: int,
        bot_id: str | None = None,
        model_name: str | None = None,
    ) -> PerformanceDashboard:
        if not get_access_token():
            raise ServiceError(backend_required_message("les performances Spot reelles"))

        response = self._request_with_auth_refresh(
            lambda token: self.client.get_user_bot_performance_summary(
                token,
                period_days=period_days,
                bot_id=bot_id,
                model_name=model_name,
            )
        )
        if response.success and isinstance(response.data, dict):
            return self._dashboard_from_backend(response.data)
        raise ServiceError(BotControlService._extract_error_message(response))

    def _get_snapshot_mock(
        self,
        bot_id: str,
        period_days: int,
        scenario_override: MockScenario | None = None,
    ) -> PerformanceSnapshot:
        simulate_latency(self.store, min_ms=200, max_ms=720)
        raise_if_forced_error(
            self.store,
            "performance.fetch",
            "Erreur mock lors du chargement des performances.",
        )
        if not self.store.current_user_email:
            raise ServiceError("Utilisateur non connecte.")

        scenario = scenario_override or self.store.scenario
        if scenario not in {
            MockScenario.PERFORMANCE_STRONG,
            MockScenario.PERFORMANCE_WEAK,
            MockScenario.USER_NORMAL,
            MockScenario.USER_ADMIN,
        }:
            scenario = MockScenario.USER_NORMAL

        return build_performance_snapshot(
            bot_id=bot_id,
            period_days=period_days,
            scenario=scenario,
            now=datetime.now(UTC),
        )

    def _get_snapshot_backend(self, *, bot_id: str, period_days: int) -> PerformanceSnapshot:
        bot_service = BotControlService(self.store, client=self.client)
        performance = bot_service.get_performance(bot_id)
        if not isinstance(performance, dict):
            raise ServiceError("Performance backend introuvable pour ce bot.")
        trades = bot_service.list_trades(bot_id)

        realized_pnl = self._float(performance.get("realized_pnl"))
        unrealized_pnl = self._float(performance.get("unrealized_pnl"))
        fees = sum(self._float(item.get("fee")) for item in trades)
        base_quote = self._base_quote_from_bot(bot_id)
        roi_pct = ((realized_pnl + unrealized_pnl) / base_quote * 100) if base_quote > 0 else 0.0
        journal = self._journal_from_backend(bot_id, trades)
        metrics = PerformanceMetrics(
            pnl_realized_usdc=realized_pnl,
            roi_pct=roi_pct,
            max_drawdown_pct=0.0,
            win_rate_pct=self._win_rate(journal),
            fees_usdc=fees,
        )
        return PerformanceSnapshot(
            bot_id=bot_id,
            period_days=period_days,
            metrics=metrics,
            equity_curve=self._equity_curve(period_days, realized_pnl + unrealized_pnl),
            trade_journal=journal,
            scenario_label="Backend bots Testnet",
        )

    def _base_quote_from_bot(self, bot_id: str) -> float:
        selections = self.store.user_bot_selections.get(
            (self.store.current_user_email or "").lower(), []
        )
        for selection in selections:
            if selection.id == bot_id:
                order_policy = dict(selection.config_snapshot.get("order_policy") or {})
                return max(self._float(order_policy.get("quote_order_quantity")), 1.0)
        return 100.0

    def _journal_from_backend(
        self, bot_id: str, trades: list[dict[str, Any]]
    ) -> list[TradeJournalEntry]:
        rows: list[TradeJournalEntry] = []
        for item in trades:
            raw_response = (
                item.get("raw_response") if isinstance(item.get("raw_response"), dict) else {}
            )
            rows.append(
                TradeJournalEntry(
                    id=str(item.get("id") or item.get("order_id") or ""),
                    bot_id=bot_id,
                    symbol=str(item.get("symbol") or ""),
                    side=str(item.get("side") or ""),
                    entry_price=self._float(item.get("price")),
                    exit_price=self._float(item.get("price")),
                    pnl_usdc=self._float(raw_response.get("realized_pnl")),
                    fee_usdc=self._float(item.get("fee")),
                    duration_min=0,
                    closed_at=self._parse_datetime(
                        item.get("trade_time") or item.get("created_at")
                    ),
                )
            )
        return sorted(rows, key=lambda row: row.closed_at, reverse=True)

    @staticmethod
    def _equity_curve(period_days: int, pnl: float) -> list[EquityPoint]:
        now = datetime.now(UTC)
        baseline = 1000.0
        return [
            EquityPoint(timestamp=now - timedelta(days=period_days), equity_usdc=baseline),
            EquityPoint(timestamp=now, equity_usdc=baseline + pnl),
        ]

    @staticmethod
    def _win_rate(journal: list[TradeJournalEntry]) -> float:
        closed = [entry for entry in journal if entry.pnl_usdc != 0]
        if not closed:
            return 0.0
        wins = sum(1 for entry in closed if entry.pnl_usdc > 0)
        return wins / len(closed) * 100

    @staticmethod
    def _parse_datetime(value: object) -> datetime:
        parsed: datetime | None = None
        if isinstance(value, datetime):
            parsed = value
        elif isinstance(value, str) and value.strip():
            try:
                parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
            except ValueError:
                pass
        if parsed is None:
            parsed = datetime.now(UTC)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=UTC)
        return parsed.astimezone(UTC)

    @staticmethod
    def _float(value: object) -> float:
        try:
            if value is None or value == "":
                return 0.0
            return float(value)
        except (TypeError, ValueError):
            return 0.0

    def _dashboard_from_backend(self, payload: dict[str, Any]) -> PerformanceDashboard:
        global_payload = payload.get("global_performance")
        if not isinstance(global_payload, dict):
            raise ServiceError("Performance backend invalide: global_performance manquant.")
        return PerformanceDashboard(
            generated_at=self._parse_datetime(payload.get("generated_at")),
            period_start=self._parse_datetime_optional(payload.get("period_start")),
            period_end=self._parse_datetime(payload.get("period_end")),
            period_days=int(payload.get("period_days") or 0),
            bot_id=self._optional_str(payload.get("bot_id")),
            model_name=self._optional_str(payload.get("model_name")),
            unavailable_reasons=[
                PerformanceUnavailableReason(
                    field=str(item.get("field") or ""),
                    reason=str(item.get("reason") or ""),
                )
                for item in self._list_of_dicts(payload.get("unavailable_reasons"))
            ],
            global_performance=UserPerformanceGlobal(
                capital_initial=self._float_or_none(global_payload.get("capital_initial")),
                capital_current=self._float_or_none(global_payload.get("capital_current")),
                pnl_total=self._float_or_none(global_payload.get("pnl_total")),
                pnl_realized=self._float(global_payload.get("pnl_realized")),
                pnl_unrealized=self._float_or_none(global_payload.get("pnl_unrealized")),
                total_orders=int(global_payload.get("total_orders") or 0),
                total_trades=int(global_payload.get("total_trades") or 0),
                win_rate_pct=self._float_or_none(global_payload.get("win_rate_pct")),
            ),
            bots=[
                BotPerformanceContribution(
                    bot_id=str(item.get("bot_id") or ""),
                    bot_name=str(item.get("bot_name") or ""),
                    model_name=self._optional_str(item.get("model_name")),
                    model_version=self._optional_str(item.get("model_version")),
                    pnl_total=self._float_or_none(item.get("pnl_total")),
                    pnl_realized=self._float(item.get("pnl_realized")),
                    pnl_unrealized=self._float_or_none(item.get("pnl_unrealized")),
                    orders=int(item.get("orders") or 0),
                    trades=int(item.get("trades") or 0),
                    last_decision=self._optional_str(item.get("last_decision")),
                    last_decision_at=self._parse_datetime_optional(item.get("last_decision_at")),
                    last_ai_signal=self._optional_str(item.get("last_ai_signal")),
                    average_confidence=self._float_or_none(item.get("average_confidence")),
                    pnl_contribution_pct=self._float_or_none(item.get("pnl_contribution_pct")),
                )
                for item in self._list_of_dicts(payload.get("bots"))
            ],
            decisions=[
                PerformanceDecisionHistory(
                    id=str(item.get("id") or ""),
                    bot_id=str(item.get("bot_id") or ""),
                    bot_name=str(item.get("bot_name") or ""),
                    timestamp=self._parse_datetime(item.get("timestamp")),
                    model_source=self._optional_str(item.get("model_source")),
                    registry_source=self._optional_str(item.get("registry_source")),
                    model_name=self._optional_str(item.get("model_name")),
                    model_version=self._optional_str(item.get("model_version")),
                    confidence=self._float_or_none(item.get("confidence")),
                    raw_ai_signal=self._optional_str(item.get("raw_ai_signal")),
                    deterministic_signal=self._optional_str(item.get("deterministic_signal")),
                    final_action=str(item.get("final_action") or ""),
                    risk_decision=str(item.get("risk_decision") or ""),
                    reason=self._optional_str(item.get("reason")),
                )
                for item in self._list_of_dicts(payload.get("decisions"))
            ],
            orders=[
                PerformanceOrderHistory(
                    id=str(item.get("id") or ""),
                    bot_id=str(item.get("bot_id") or ""),
                    bot_name=str(item.get("bot_name") or ""),
                    created_at=self._parse_datetime(item.get("created_at")),
                    symbol=str(item.get("symbol") or ""),
                    side=str(item.get("side") or ""),
                    order_type=str(item.get("order_type") or ""),
                    status=str(item.get("status") or ""),
                    binance_order_id=self._optional_str(item.get("binance_order_id")),
                    quote_order_quantity=self._float_or_none(item.get("quote_order_quantity")),
                    quantity=self._float_or_none(item.get("quantity")),
                )
                for item in self._list_of_dicts(payload.get("orders"))
            ],
            trades=[
                PerformanceTradeHistory(
                    id=str(item.get("id") or ""),
                    bot_id=str(item.get("bot_id") or ""),
                    bot_name=str(item.get("bot_name") or ""),
                    order_id=str(item.get("order_id") or ""),
                    trade_time=self._parse_datetime(item.get("trade_time")),
                    symbol=str(item.get("symbol") or ""),
                    side=str(item.get("side") or ""),
                    quantity=self._float(item.get("quantity")),
                    price=self._float(item.get("price")),
                    fee=self._float_or_none(item.get("fee")),
                    fee_asset=self._optional_str(item.get("fee_asset")),
                    realized_pnl=self._float_or_none(item.get("realized_pnl")),
                )
                for item in self._list_of_dicts(payload.get("trades"))
            ],
            pnl_curve=[
                PerformancePnlPoint(
                    timestamp=self._parse_datetime(item.get("timestamp")),
                    bot_id=self._optional_str(item.get("bot_id")),
                    bot_name=self._optional_str(item.get("bot_name")),
                    realized_pnl=self._float(item.get("realized_pnl")),
                    cumulative_realized_pnl=self._float(item.get("cumulative_realized_pnl")),
                    capital_current=self._float_or_none(item.get("capital_current")),
                )
                for item in self._list_of_dicts(payload.get("pnl_curve"))
            ],
        )

    @classmethod
    def _parse_datetime_optional(cls, value: object) -> datetime | None:
        if value is None or value == "":
            return None
        return cls._parse_datetime(value)

    @staticmethod
    def _float_or_none(value: object) -> float | None:
        try:
            if value is None or value == "":
                return None
            return float(value)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _optional_str(value: object) -> str | None:
        if value is None:
            return None
        text = str(value).strip()
        return text or None

    @staticmethod
    def _list_of_dicts(value: object) -> list[dict[str, Any]]:
        if not isinstance(value, list):
            return []
        return [item for item in value if isinstance(item, dict)]

    def _request_with_auth_refresh(
        self,
        request_fn,
    ) -> ApiResponse:
        access_token = get_access_token()
        if not access_token:
            return ApiResponse(status_code=0, error="Utilisateur non connecte.")

        response = request_fn(access_token)
        if response.status_code != 401:
            return response

        refresh_token = get_refresh_token()
        if not refresh_token:
            return response

        refresh_response = self.client.refresh_token(refresh_token)
        if not refresh_response.success or not isinstance(refresh_response.data, dict):
            return response

        new_access_token = refresh_response.data.get("access_token")
        if not isinstance(new_access_token, str) or not new_access_token:
            return response

        set_auth_tokens(new_access_token, refresh_token)
        return request_fn(new_access_token)
