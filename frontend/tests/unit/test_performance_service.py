from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from services.api_client import BackendApiClient
from services.auth_api_client import ApiResponse
from services.performance_service import PerformanceService


def _ok(data: object) -> ApiResponse:
    return ApiResponse(status_code=200, data=data)


def _err() -> ApiResponse:
    return ApiResponse(status_code=500, data={}, error="backend error")


MOCK_STATS = {
    "total_trades": 42,
    "total_profit_loss": 1250.75,
    "win_rate": 0.65,
    "max_drawdown": 0.08,
}

MOCK_TRANSACTIONS = [
    {
        "id": "tx1",
        "transaction_type": "TRADE",
        "asset": "BTC",
        "quote_asset": "USDC",
        "direction": "IN",
        "price": 45000.0,
        "amount": 0.1,
        "fee_amount": 2.5,
        "timestamp": "2024-01-15T10:00:00Z",
    },
    {
        "id": "tx2",
        "transaction_type": "TRADE",
        "asset": "ETH",
        "quote_asset": "USDC",
        "direction": "OUT",
        "price": 2500.0,
        "amount": 1.0,
        "fee_amount": 1.5,
        "timestamp": "2024-01-16T10:00:00Z",
    },
]


@pytest.fixture(autouse=True)
def _mock_token():
    with patch("services.performance_service.get_access_token", return_value="fake-token"):
        yield


def test_performance_positive_pnl(store) -> None:
    client = MagicMock(spec=BackendApiClient)
    client.get_trading_stats.return_value = _ok(MOCK_STATS)
    client.list_transactions.return_value = _ok(MOCK_TRANSACTIONS)
    service = PerformanceService(store, client=client)
    snapshot = service.get_snapshot(bot_id="strat_btc", period_days=30)
    assert snapshot.metrics.pnl_realized_usdt == pytest.approx(1250.75)
    assert snapshot.metrics.win_rate_pct == pytest.approx(65.0)


def test_performance_snapshot_has_trade_journal(store) -> None:
    client = MagicMock(spec=BackendApiClient)
    client.get_trading_stats.return_value = _ok(MOCK_STATS)
    client.list_transactions.return_value = _ok(MOCK_TRANSACTIONS)
    service = PerformanceService(store, client=client)
    snapshot = service.get_snapshot(bot_id="strat_btc", period_days=7)
    assert len(snapshot.trade_journal) == 2
    assert snapshot.scenario_label == "Live"


def test_performance_backend_failure_returns_zero_metrics(store) -> None:
    client = MagicMock(spec=BackendApiClient)
    client.get_trading_stats.return_value = _err()
    client.list_transactions.return_value = _err()
    service = PerformanceService(store, client=client)
    snapshot = service.get_snapshot(bot_id="strat_btc", period_days=30)
    assert snapshot.metrics.pnl_realized_usdt == 0.0
    assert snapshot.metrics.win_rate_pct == 0.0
    assert snapshot.trade_journal == []
