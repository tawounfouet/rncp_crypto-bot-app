"""Service performances Spot - connecte au backend reel."""

from __future__ import annotations

from datetime import UTC, datetime

from mocks.db import MockStore
from schemas.performance import (
    EquityPoint,
    PerformanceMetrics,
    PerformanceSnapshot,
    TradeJournalEntry,
)
from services.api_client import BackendApiClient
from services.base import ServiceError
from state.session import get_access_token

_PERIOD_MAP = {7: "7d", 14: "30d", 30: "30d", 90: "90d", 365: "1y"}


def _parse_dt(value: object) -> datetime:
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            pass
    return datetime.now(UTC)


def _float(value: object, default: float = 0.0) -> float:
    try:
        return float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return default


class PerformanceService:
    def __init__(self, store: MockStore, client: BackendApiClient | None = None) -> None:
        self.store = store
        self.client = client or BackendApiClient()

    def get_snapshot(
        self,
        bot_id: str,
        period_days: int,
        scenario_override: object = None,
    ) -> PerformanceSnapshot:
        token = get_access_token()
        if not token:
            raise ServiceError("Non authentifie.")

        period = _PERIOD_MAP.get(period_days, "30d")

        # --- Stats de trading ---
        stats_resp = self.client.get_trading_stats(token, period=period)
        metrics = PerformanceMetrics(
            pnl_realized_usdt=0.0,
            roi_pct=0.0,
            max_drawdown_pct=0.0,
            win_rate_pct=0.0,
            fees_usdt=0.0,
        )
        if stats_resp.success and isinstance(stats_resp.data, dict):
            raw = stats_resp.data.get("stats") or stats_resp.data
            win_rate = _float(raw.get("win_rate")) * 100
            metrics = PerformanceMetrics(
                pnl_realized_usdt=_float(raw.get("total_profit_loss")),
                roi_pct=0.0,
                max_drawdown_pct=_float(raw.get("max_drawdown")) * 100,
                win_rate_pct=win_rate,
                fees_usdt=0.0,
            )

        # --- Journal de trades (transactions) ---
        tx_resp = self.client.list_transactions(token, limit=200)
        trade_journal: list[TradeJournalEntry] = []
        if tx_resp.success:
            raw_list = (
                tx_resp.data
                if isinstance(tx_resp.data, list)
                else (tx_resp.data or {}).get("transactions", [])
                if isinstance(tx_resp.data, dict)
                else []
            )
            for t in raw_list:
                if t.get("transaction_type") == "TRADE":
                    trade_journal.append(
                        TradeJournalEntry(
                            id=t.get("id", ""),
                            bot_id=bot_id,
                            symbol=t.get("asset", "") + (t.get("quote_asset") or "USDT"),
                            side="BUY" if t.get("direction") == "IN" else "SELL",
                            entry_price=_float(t.get("price")),
                            exit_price=_float(t.get("price")),
                            pnl_usdt=0.0,
                            fee_usdt=_float(t.get("fee_amount")),
                            duration_min=0,
                            closed_at=_parse_dt(t.get("timestamp")),
                        )
                    )

        # L'equity curve necessite un endpoint time-series non disponible
        equity_curve: list[EquityPoint] = []

        return PerformanceSnapshot(
            bot_id=bot_id,
            period_days=period_days,
            metrics=metrics,
            equity_curve=equity_curve,
            trade_journal=trade_journal,
            scenario_label="Live",
        )
