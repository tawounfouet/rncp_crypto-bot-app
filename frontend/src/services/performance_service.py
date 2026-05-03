"""Service performances Spot mocke."""

from __future__ import annotations

from datetime import datetime

from mocks.db import MockStore
from mocks.factories import build_performance_snapshot
from mocks.scenarios import MockScenario
from schemas.performance import PerformanceSnapshot
from services.base import ServiceError, raise_if_forced_error, simulate_latency


class PerformanceService:
    def __init__(self, store: MockStore) -> None:
        self.store = store

    def get_snapshot(
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
            now=datetime.utcnow(),
        )
