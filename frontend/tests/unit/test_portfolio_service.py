from __future__ import annotations

import pytest

from mocks.scenarios import MockScenario
from services.base import ServiceError
from services.portfolio_service import PortfolioService


def test_get_snapshot_requires_login(store) -> None:
    service = PortfolioService(store)
    with pytest.raises(ServiceError):
        service.get_snapshot()


def test_get_snapshot_rich(store) -> None:
    store.current_user_email = "alice@cryptobot.dev"
    store.scenario = MockScenario.PORTFOLIO_RICH
    service = PortfolioService(store)
    snapshot = service.get_snapshot()
    assert snapshot.asset_count >= 10
    assert snapshot.total_value_usdt > 10000


def test_cancel_order(store) -> None:
    store.current_user_email = "alice@cryptobot.dev"
    service = PortfolioService(store)
    ok, message = service.cancel_order("ord_101")
    assert ok is True
    assert "ord_101" in message
