"""Service portfolio Spot backed by Binance Testnet APIs."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from mocks.db import MockStore
from mocks.factories import build_portfolio_snapshot
from schemas.portfolio import BalanceRow, OpenOrder, PortfolioSnapshot, SpotTrade, SystemStatus
from services.auth_api_client import ApiResponse, AuthApiClient
from services.base import ServiceError, raise_if_forced_error, simulate_latency
from services.runtime_mode import allow_mock_fallback, backend_required_message
from state.session import get_access_token, get_refresh_token, set_auth_tokens

TRADE_SYMBOLS = ("BTCUSDT", "ETHUSDT")
STABLE_ASSETS = {"USDT", "BUSD", "USDC", "FDUSD"}


class PortfolioService:
    def __init__(self, store: MockStore, client: AuthApiClient | None = None) -> None:
        self.store = store
        self.client = client or AuthApiClient()
        self._order_symbols: dict[str, str] = {}

    def get_snapshot(self) -> PortfolioSnapshot:
        access_token = get_access_token()
        if access_token:
            return self._get_snapshot_backend()
        if not allow_mock_fallback():
            raise ServiceError(backend_required_message("le portefeuille Spot"))
        return self._get_snapshot_mock()

    def _get_snapshot_mock(self) -> PortfolioSnapshot:
        simulate_latency(self.store, min_ms=180, max_ms=560)
        raise_if_forced_error(self.store, "portfolio.fetch", "Erreur mock portfolio.")

        if not self.store.current_user_email:
            raise ServiceError("Utilisateur non connecte.")
        user = self.store.users[self.store.current_user_email]
        snapshot = build_portfolio_snapshot(
            scenario=self.store.scenario,
            binance_configured=user.binance_configured,
            now=datetime.now(UTC),
        )
        self.store.last_sync = snapshot.system_status.last_sync
        return snapshot

    def cancel_order(self, order_id: str) -> tuple[bool, str]:
        access_token = get_access_token()
        if access_token:
            return self._cancel_order_backend(order_id)
        if not allow_mock_fallback():
            raise ServiceError(backend_required_message("l'annulation d'ordre"))
        return self._cancel_order_mock(order_id)

    def _cancel_order_mock(self, order_id: str) -> tuple[bool, str]:
        simulate_latency(self.store, min_ms=80, max_ms=260)
        raise_if_forced_error(
            self.store,
            "portfolio.cancel_order",
            "Impossible d'annuler cet ordre (erreur mock).",
        )
        if not order_id:
            return False, "Aucun ordre selectionne."
        return True, f"Ordre {order_id} annule (mock)."

    def _get_snapshot_backend(self) -> PortfolioSnapshot:
        now = datetime.now(UTC)
        balances_payload = self._backend_list(
            lambda token: self.client.get_testnet_balances(token, non_zero=True)
        )
        orders_payload = self._backend_list(
            lambda token: self.client.get_testnet_open_orders(token)
        )
        trades_payload = self._recent_trades_payload()

        balances = self._balances_from_backend(balances_payload)
        open_orders = self._orders_from_backend(orders_payload)
        recent_trades = self._trades_from_backend(trades_payload)
        total_value = sum(row.value_usdt for row in balances)
        free_cash = sum(row.free for row in balances if row.asset in STABLE_ASSETS)

        snapshot = PortfolioSnapshot(
            system_status=SystemStatus(
                backend_ok=True,
                binance_ok=True,
                last_sync=now,
                backend_message="Connecte",
                binance_message="Binance Spot Testnet",
            ),
            total_value_usdt=total_value,
            free_cash_usdt=free_cash,
            asset_count=len(balances),
            open_order_count=len(open_orders),
            balances=balances,
            open_orders=open_orders,
            recent_trades=recent_trades,
        )
        self.store.last_sync = now
        return snapshot

    def _cancel_order_backend(self, order_id: str) -> tuple[bool, str]:
        if not order_id:
            return False, "Aucun ordre selectionne."
        symbol = self._order_symbols.get(str(order_id))
        if not symbol:
            orders = self._backend_list(lambda token: self.client.get_testnet_open_orders(token))
            for order in orders:
                candidate = str(order.get("orderId") or order.get("clientOrderId") or "")
                if candidate == str(order_id):
                    symbol = str(order.get("symbol") or "")
                    break
        if not symbol:
            return False, "Symbole de l'ordre introuvable dans les ordres ouverts."

        payload: dict[str, Any] = {"symbol": symbol}
        try:
            payload["order_id"] = int(order_id)
        except (TypeError, ValueError):
            payload["orig_client_order_id"] = str(order_id)
        response = self._request_with_auth_refresh(
            lambda token: self.client.cancel_testnet_order(token, payload)
        )
        if response.success:
            return True, f"Ordre {order_id} annule sur Binance Spot Testnet."
        return False, self._extract_error_message(response)

    def _balances_from_backend(self, payload: list[dict[str, Any]]) -> list[BalanceRow]:
        rows: list[BalanceRow] = []
        for item in payload:
            asset = str(item.get("asset") or "").upper()
            if not asset:
                continue
            free = self._float(item.get("free"))
            locked = self._float(item.get("locked"))
            rows.append(
                BalanceRow(
                    asset=asset,
                    free=free,
                    locked=locked,
                    value_usdt=(free + locked) * self._asset_price_usdt(asset),
                )
            )
        return sorted(rows, key=lambda row: row.value_usdt, reverse=True)

    def _orders_from_backend(self, payload: list[dict[str, Any]]) -> list[OpenOrder]:
        rows: list[OpenOrder] = []
        self._order_symbols = {}
        for item in payload:
            order_id = str(item.get("orderId") or item.get("clientOrderId") or "")
            symbol = str(item.get("symbol") or "")
            if order_id and symbol:
                self._order_symbols[order_id] = symbol
            rows.append(
                OpenOrder(
                    order_id=order_id,
                    symbol=symbol,
                    side=str(item.get("side") or ""),
                    price=self._float(item.get("price")),
                    amount=self._float(item.get("origQty") or item.get("executedQty")),
                    status=str(item.get("status") or ""),
                    created_at=self._parse_exchange_time(
                        item.get("time") or item.get("updateTime")
                    ),
                )
            )
        return sorted(rows, key=lambda row: row.created_at, reverse=True)

    def _recent_trades_payload(self) -> list[dict[str, Any]]:
        payload: list[dict[str, Any]] = []
        for symbol in TRADE_SYMBOLS:
            payload.extend(
                self._backend_list(
                    lambda token, symbol=symbol: self.client.get_testnet_my_trades(
                        token, symbol=symbol, limit=50
                    )
                )
            )
        return payload

    def _trades_from_backend(self, payload: list[dict[str, Any]]) -> list[SpotTrade]:
        rows: list[SpotTrade] = []
        for item in payload:
            is_buyer = bool(item.get("isBuyer"))
            rows.append(
                SpotTrade(
                    trade_id=str(item.get("id") or item.get("orderId") or ""),
                    symbol=str(item.get("symbol") or ""),
                    side="BUY" if is_buyer else "SELL",
                    price=self._float(item.get("price")),
                    quantity=self._float(item.get("qty") or item.get("quantity")),
                    pnl_realized=0.0,
                    fee_usdt=self._float(item.get("commission")),
                    executed_at=self._parse_exchange_time(item.get("time")),
                )
            )
        return sorted(rows, key=lambda row: row.executed_at, reverse=True)[:100]

    def _asset_price_usdt(self, asset: str) -> float:
        if asset in STABLE_ASSETS:
            return 1.0
        symbol = f"{asset}USDT"
        response = self._request_with_auth_refresh(
            lambda token: self.client.get_testnet_ticker(token, symbol=symbol)
        )
        if not response.success or not isinstance(response.data, dict):
            return 0.0
        return self._float(response.data.get("lastPrice") or response.data.get("weightedAvgPrice"))

    def _backend_list(self, request_fn) -> list[dict[str, Any]]:
        response = self._request_with_auth_refresh(request_fn)
        if response.success and isinstance(response.data, list):
            return [item for item in response.data if isinstance(item, dict)]
        raise ServiceError(self._extract_error_message(response))

    def _request_with_auth_refresh(self, request_fn) -> ApiResponse:
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

    @staticmethod
    def _extract_error_message(response: ApiResponse) -> str:
        if response.error:
            return response.error
        payload = response.data
        if isinstance(payload, dict):
            detail = payload.get("detail")
            if isinstance(detail, str) and detail:
                return detail
            if isinstance(detail, dict):
                message = detail.get("message")
                if isinstance(message, str) and message:
                    return message
            message = payload.get("message")
            if isinstance(message, str) and message:
                return message
        if response.status_code == 0:
            return "API portefeuille indisponible."
        return f"Erreur backend ({response.status_code})."

    @staticmethod
    def _parse_exchange_time(value: object) -> datetime:
        if isinstance(value, int | float):
            return datetime.fromtimestamp(float(value) / 1000, UTC)
        if isinstance(value, datetime):
            parsed = value
        elif isinstance(value, str) and value.strip():
            try:
                parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
            except ValueError:
                parsed = datetime.now(UTC)
        else:
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
