"""Service portfolio Spot mocke."""

from __future__ import annotations

from datetime import UTC, datetime

from mocks.db import MockStore
from mocks.factories import build_portfolio_snapshot
from schemas.portfolio import PortfolioSnapshot
from services.base import ServiceError, raise_if_forced_error, simulate_latency


class PortfolioService:
    def __init__(self, store: MockStore) -> None:
        self.store = store

    def get_snapshot(self) -> PortfolioSnapshot:
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
        simulate_latency(self.store, min_ms=80, max_ms=260)
        raise_if_forced_error(
            self.store,
            "portfolio.cancel_order",
            "Impossible d'annuler cet ordre (erreur mock).",
        )
        if not order_id:
            return False, "Aucun ordre selectionne."
        return True, f"Ordre {order_id} annule (mock)."
