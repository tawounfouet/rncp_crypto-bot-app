"""Service portfolio Spot - connecte au backend reel."""

from __future__ import annotations

from datetime import UTC, datetime

from mocks.db import MockStore
from schemas.portfolio import BalanceRow, OpenOrder, PortfolioSnapshot, SpotTrade, SystemStatus
from services.api_client import BackendApiClient
from services.base import ServiceError
from state.session import get_access_token, get_selected_exchange
from utils.dates import parse_dt_or_now
from utils.numeric import to_float as _float


class PortfolioService:
    def __init__(self, store: MockStore, client: BackendApiClient | None = None) -> None:
        self.store = store
        self.client = client or BackendApiClient()

    def get_snapshot(self, exchange: str | None = None) -> PortfolioSnapshot:
        token = get_access_token()
        if not token:
            raise ServiceError("Non authentifie.")

        now = datetime.now(UTC)
        exchange = exchange or get_selected_exchange()

        # --- Portfolio (balances) ---
        portfolio_resp = self.client.get_portfolio(token, exchange=exchange)
        backend_ok = portfolio_resp.success
        balances: list[BalanceRow] = []
        total_value_usdc = 0.0
        free_cash_usdc = 0.0

        exchange_ok = False
        exchange_message = "Non configure"

        if portfolio_resp.success and isinstance(portfolio_resp.data, dict):
            raw_portfolio = portfolio_resp.data.get("portfolio") or portfolio_resp.data
            inner_success = portfolio_resp.data.get("success", True)  # absent in stub → True
            inner_message = portfolio_resp.data.get("message") or ""
            raw_balances = raw_portfolio.get("balances") or []
            total_value_usdc = _float(raw_portfolio.get("total_usd_value"))
            for b in raw_balances:
                asset = b.get("asset", "")
                free = _float(b.get("available"))
                locked = _float(b.get("locked"))
                value = _float(b.get("usd_value"))
                if asset in ("USDC",):
                    free_cash_usdc = free
                if free > 0 or locked > 0:
                    balances.append(
                        BalanceRow(asset=asset, free=free, locked=locked, value_usdc=value)
                    )
            if inner_success:
                exchange_ok = True
                exchange_message = "Connecte"
            else:
                exchange_message = inner_message or "Clés d'exchange non configurées"

        # --- Open orders ---
        orders_resp = self.client.list_orders(token, status="NEW", limit=50)
        open_orders: list[OpenOrder] = []
        if orders_resp.success and isinstance(orders_resp.data, list):
            for o in orders_resp.data:
                open_orders.append(
                    OpenOrder(
                        order_id=o.get("id", ""),
                        symbol=o.get("symbol", ""),
                        side=o.get("side", ""),
                        price=_float(o.get("price")),
                        amount=_float(o.get("quantity")),
                        status=o.get("status", ""),
                        created_at=parse_dt_or_now(o.get("created_at")),
                    )
                )

        # --- Recent trades (transactions) ---
        tx_resp = self.client.list_transactions(token, limit=20)
        recent_trades: list[SpotTrade] = []
        if tx_resp.success:
            raw_list = (
                tx_resp.data
                if isinstance(tx_resp.data, list)
                else (tx_resp.data or {}).get("transactions", [])
                if isinstance(tx_resp.data, dict)
                else []
            )
            for t in raw_list[:20]:
                recent_trades.append(
                    SpotTrade(
                        trade_id=t.get("id", ""),
                        symbol=t.get("asset", "") + (t.get("quote_asset") or "USDC"),
                        side="BUY" if t.get("direction") == "IN" else "SELL",
                        price=_float(t.get("price")),
                        quantity=_float(t.get("amount")),
                        pnl_realized=0.0,
                        fee_usdc=_float(t.get("fee_amount")),
                        executed_at=parse_dt_or_now(t.get("timestamp")),
                    )
                )

        system_status = SystemStatus(
            backend_ok=backend_ok,
            exchange=exchange,
            exchange_ok=exchange_ok,
            last_sync=now,
            backend_message="Connecte" if backend_ok else "Erreur backend",
            exchange_message=exchange_message,
        )

        return PortfolioSnapshot(
            system_status=system_status,
            total_value_usdc=total_value_usdc,
            free_cash_usdc=free_cash_usdc,
            asset_count=len(balances),
            open_order_count=len(open_orders),
            balances=balances,
            open_orders=open_orders,
            recent_trades=recent_trades,
        )

    def list_snapshots(self, exchanges: list[str]) -> dict[str, PortfolioSnapshot]:
        return {exchange: self.get_snapshot(exchange) for exchange in exchanges}

    def cancel_order(self, order_id: str) -> tuple[bool, str]:
        token = get_access_token()
        if not token:
            return False, "Non authentifie."
        if not order_id:
            return False, "Aucun ordre selectionne."
        response = self.client.cancel_order(token, order_id)
        if not response.success:
            if response.error:
                return False, response.error
            data = response.data
            if isinstance(data, dict):
                detail = data.get("detail")
                if isinstance(detail, str):
                    return False, detail
            return False, f"Impossible d'annuler l'ordre ({response.status_code})."
        return True, f"Ordre {order_id[:8]}... annule."
