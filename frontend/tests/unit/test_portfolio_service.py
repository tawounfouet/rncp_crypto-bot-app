from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from services.api_client import BackendApiClient
from services.auth_api_client import ApiResponse
from services.base import ServiceError
from services.portfolio_service import PortfolioService


def _ok(data: object) -> ApiResponse:
    return ApiResponse(status_code=200, data=data)


def _err(code: int = 400) -> ApiResponse:
    return ApiResponse(status_code=code, data={}, error="error")


MOCK_PORTFOLIO = {
    "total_usd_value": 15000.0,
    "balances": [
        {"asset": "USDC", "available": 5000.0, "locked": 0.0, "usd_value": 5000.0},
        {"asset": "BTC", "available": 0.1, "locked": 0.0, "usd_value": 4500.0},
        {"asset": "ETH", "available": 2.0, "locked": 0.0, "usd_value": 5000.0},
    ],
}

MOCK_ORDERS = [
    {
        "id": "ord_101",
        "symbol": "BTCUSDC",
        "side": "BUY",
        "price": 44000.0,
        "quantity": 0.05,
        "status": "NEW",
        "created_at": "2024-01-01T10:00:00Z",
    }
]

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
    }
]


def test_get_snapshot_requires_login(store) -> None:
    with patch("services.portfolio_service.get_access_token", return_value=None):
        service = PortfolioService(store)
        with pytest.raises(ServiceError):
            service.get_snapshot()


@pytest.fixture(autouse=True)
def _mock_token():
    with patch("services.portfolio_service.get_access_token", return_value="fake-token"):
        yield


def test_get_snapshot_rich(store) -> None:
    client = MagicMock(spec=BackendApiClient)
    client.get_portfolio.return_value = _ok(MOCK_PORTFOLIO)
    client.list_orders.return_value = _ok(MOCK_ORDERS)
    client.list_transactions.return_value = _ok(MOCK_TRANSACTIONS)
    service = PortfolioService(store, client=client)
    snapshot = service.get_snapshot()
    assert snapshot.asset_count == 3
    assert snapshot.total_value_usdc == pytest.approx(15000.0)
    assert snapshot.open_order_count == 1


def test_get_snapshot_empty_portfolio(store) -> None:
    client = MagicMock(spec=BackendApiClient)
    client.get_portfolio.return_value = _ok({"total_usd_value": 0.0, "balances": []})
    client.list_orders.return_value = _ok([])
    client.list_transactions.return_value = _ok([])
    service = PortfolioService(store, client=client)
    snapshot = service.get_snapshot()
    assert snapshot.asset_count == 0
    assert snapshot.total_value_usdc == 0.0


def test_cancel_order(store) -> None:
    client = MagicMock(spec=BackendApiClient)
    client.cancel_order.return_value = _ok({"message": "cancelled"})
    service = PortfolioService(store, client=client)
    ok, message = service.cancel_order("ord_101")
    assert ok is True
    assert "ord_101"[:8] in message
    client.cancel_order.assert_called_once_with("fake-token", "ord_101")


def test_cancel_order_backend_error(store) -> None:
    client = MagicMock(spec=BackendApiClient)
    client.cancel_order.return_value = _err(404)
    service = PortfolioService(store, client=client)
    ok, _ = service.cancel_order("ord_999")
    assert ok is False
