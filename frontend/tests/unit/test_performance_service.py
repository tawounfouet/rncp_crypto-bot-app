from __future__ import annotations

from mocks.scenarios import MockScenario
from services.performance_service import PerformanceService


def test_performance_strong_scenario_positive_roi(store) -> None:
    store.current_user_email = "alice@cryptobot.dev"
    service = PerformanceService(store)
    snapshot = service.get_snapshot(
        bot_id="bot_btc_scalp",
        period_days=30,
        scenario_override=MockScenario.PERFORMANCE_STRONG,
    )
    assert snapshot.metrics.roi_pct > 0
    assert len(snapshot.equity_curve) == 31


def test_performance_weak_scenario_has_curve(store) -> None:
    store.current_user_email = "alice@cryptobot.dev"
    service = PerformanceService(store)
    snapshot = service.get_snapshot(
        bot_id="bot_btc_scalp",
        period_days=7,
        scenario_override=MockScenario.PERFORMANCE_WEAK,
    )
    assert len(snapshot.equity_curve) == 8
    assert snapshot.scenario_label
