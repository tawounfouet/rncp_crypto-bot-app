from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from schemas.bot import BotInfo
from schemas.common import BotRuntimeStatus
from schemas.dashboard import DashboardBotRow
from schemas.performance import PerformanceMetrics, PerformanceSnapshot
from services.api_client import BackendApiClient
from services.auth_api_client import ApiResponse
from services.dashboard_service import DashboardService, aggregate_overview

MOCK_STRATEGIES = [
    {
        "id": "strat_btc",
        "name": "BTC Scalp",
        "strategy_type": "scalping",
        "is_active": True,
        "updated_at": "2024-01-01T00:00:00Z",
    },
    {
        "id": "strat_sol",
        "name": "SOL Trend",
        "strategy_type": "trend",
        "is_active": True,
        "updated_at": "2024-01-01T00:00:00Z",
    },
]

MOCK_DEPLOYMENTS = [
    {
        "id": "deploy_1",
        "strategy_id": "strat_sol",
        "status": "active",
        "updated_at": "2024-01-01T00:00:00Z",
    },
]

MOCK_STATS = {
    "total_trades": 42,
    "total_profit_loss": 1250.75,
    "win_rate": 0.65,
    "max_drawdown": 0.08,
}


def _ok(data: object) -> ApiResponse:
    return ApiResponse(status_code=200, data=data)


def _bot(status: BotRuntimeStatus) -> BotInfo:
    return BotInfo(
        id="strat_btc",
        name="BTC Scalp",
        strategy="scalping",
        mode_live=True,
        status=status,
        heartbeat_at="2024-01-01T00:00:00Z",
        last_action_result="ok",
        last_action_at="2024-01-01T00:00:00Z",
    )


def _snapshot(pnl: float) -> PerformanceSnapshot:
    return PerformanceSnapshot(
        bot_id="strat_btc",
        period_days=30,
        metrics=PerformanceMetrics(
            pnl_realized_usdc=pnl,
            roi_pct=3.5,
            max_drawdown_pct=2.0,
            win_rate_pct=65.0,
            fees_usdc=10.0,
        ),
        scenario_label="Live",
    )


def test_aggregate_overview_empty() -> None:
    overview = aggregate_overview(bots=[], snapshots={})
    assert overview.total_bots == 0
    assert overview.active_bots == 0
    assert overview.pnl_usdc == 0.0
    assert overview.avg_roi_pct == 0.0
    assert overview.bots == []


def test_aggregate_overview_aggregates_pnl_and_active_count() -> None:
    running = _bot(BotRuntimeStatus.RUNNING)
    stopped = _bot(BotRuntimeStatus.STOPPED)
    running.id = "strat_btc"
    stopped.id = "strat_sol"
    stopped.name = "SOL Trend"

    overview = aggregate_overview(
        bots=[running, stopped],
        snapshots={
            "strat_btc": _snapshot(250.0),
            "strat_sol": _snapshot(75.0),
        },
        period_days=30,
    )

    assert overview.total_bots == 2
    assert overview.active_bots == 1
    assert overview.pnl_usdc == pytest.approx(325.0)
    assert overview.avg_roi_pct == pytest.approx(3.5)
    assert overview.fees_usdc == pytest.approx(20.0)
    assert [row.status for row in overview.bots] == ["RUNNING", "STOPPED"]


def test_aggregate_overview_defaults_missing_snapshot_to_zero() -> None:
    overview = aggregate_overview(
        bots=[_bot(BotRuntimeStatus.RUNNING)],
        snapshots={},
    )
    row = overview.bots[0]
    assert row.pnl_usdc == 0.0
    assert row.roi_pct == 0.0
    assert row.fees_usdc == 0.0


def test_aggregate_overview_preserves_input_order() -> None:
    running = _bot(BotRuntimeStatus.RUNNING)
    stopped = _bot(BotRuntimeStatus.STOPPED)
    stopped.id = "strat_sol"
    stopped.name = "SOL Trend"

    overview = aggregate_overview(
        bots=[running, stopped],
        snapshots={"strat_btc": _snapshot(1.0), "strat_sol": _snapshot(2.0)},
    )

    assert [row.name for row in overview.bots] == ["BTC Scalp", "SOL Trend"]


@pytest.fixture(autouse=True)
def _mock_token():
    with (
        patch("services.bot_control_service.get_access_token", return_value="fake-token"),
        patch("services.performance_service.get_access_token", return_value="fake-token"),
    ):
        yield


MOCK_USER_BOTS = [
    {
        "id": "inst_btc",
        "status": "ACTIVE",
        "auto_trade_enabled": True,
        "config_snapshot": {"name": "BTC Scalp", "strategy_type": "scalping", "environment": "testnet"},
        "updated_at": "2024-01-01T00:00:00Z",
        "last_decision_at": "2024-01-01T00:00:00Z",
    },
    {
        "id": "inst_sol",
        "status": "STOPPED",
        "auto_trade_enabled": False,
        "config_snapshot": {"name": "SOL Trend", "strategy_type": "trend", "environment": "testnet"},
        "updated_at": "2024-01-01T00:00:00Z",
        "last_decision_at": "2024-01-01T00:00:00Z",
    },
]


def _performance_for(instance_id: str, *, realized_pnl: float) -> dict:
    return {"id": instance_id, "realized_pnl": realized_pnl, "unrealized_pnl": 0.0}


def test_get_overview_loads_snapshot_per_bot(store) -> None:
    client = MagicMock(spec=BackendApiClient)
    client.list_user_bots.return_value = _ok(MOCK_USER_BOTS)
    client.get_user_bot_performance.side_effect = lambda token, *, instance_id: _ok(
        _performance_for(instance_id, realized_pnl=2000.0 if instance_id == "inst_btc" else 501.5)
    )
    client.list_user_bot_trades.return_value = _ok([])
    service = DashboardService(store, client=client)

    overview = service.get_overview(period_days=30)

    assert overview.total_bots == 2
    assert overview.active_bots == 1
    assert overview.pnl_usdc == pytest.approx(2501.5)
    assert client.get_user_bot_performance.call_count == 2


def test_get_overview_no_bots_returns_empty(store) -> None:
    client = MagicMock(spec=BackendApiClient)
    client.list_user_bots.return_value = _ok([])
    service = DashboardService(store, client=client)

    overview = service.get_overview(period_days=30)

    assert overview.total_bots == 0
    assert overview.bots == []
    client.get_user_bot_performance.assert_not_called()
