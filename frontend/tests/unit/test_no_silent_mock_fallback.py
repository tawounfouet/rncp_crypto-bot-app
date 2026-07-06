from __future__ import annotations

import pytest
import streamlit as st

from services.admin_service import AdminService
from services.auth_api_client import ApiResponse
from services.bot_control_service import BotControlService
from services.performance_service import PerformanceService
from services.portfolio_service import PortfolioService
from state.session import set_auth_tokens


class UnreachableClient:
    def list_user_bots(self, access_token: str) -> ApiResponse:
        return ApiResponse(status_code=0, error="backend down")

    def get_user_bot_performance(self, access_token: str, *, instance_id: str) -> ApiResponse:
        return ApiResponse(status_code=0, error="backend down")

    def get_user_bot_performance_summary(self, access_token: str, **kwargs) -> ApiResponse:
        return ApiResponse(status_code=0, error="backend down")

    def get_testnet_balances(self, access_token: str, *, non_zero: bool = True) -> ApiResponse:
        return ApiResponse(status_code=0, error="backend down")

    def list_users(self, access_token: str, **kwargs) -> ApiResponse:
        return ApiResponse(status_code=0, error="backend down")


@pytest.fixture(autouse=True)
def backend_session():
    st.session_state.clear()
    set_auth_tokens("access-token", "refresh-token")
    yield
    st.session_state.clear()


def test_bot_control_does_not_fallback_to_mock_when_backend_session_exists(store) -> None:
    store.current_user_email = "alice@cryptobot.dev"
    service = BotControlService(store, client=UnreachableClient())

    with pytest.raises(RuntimeError, match="backend down"):
        service.list_bots()


def test_portfolio_does_not_fallback_to_mock_when_backend_session_exists(store) -> None:
    store.current_user_email = "alice@cryptobot.dev"
    service = PortfolioService(store, client=UnreachableClient())

    with pytest.raises(RuntimeError, match="backend down"):
        service.get_snapshot()


def test_performance_does_not_fallback_to_mock_when_backend_session_exists(store) -> None:
    store.current_user_email = "alice@cryptobot.dev"
    service = PerformanceService(store, client=UnreachableClient())

    with pytest.raises(RuntimeError, match="backend down"):
        service.get_snapshot(bot_id="bot_btc_scalp", period_days=30)

    with pytest.raises(RuntimeError, match="backend down"):
        service.get_dashboard(period_days=30)


def test_admin_does_not_fallback_to_mock_when_backend_session_exists(store) -> None:
    store.current_user_email = "admin@cryptobot.dev"
    service = AdminService(store, client=UnreachableClient())

    with pytest.raises(RuntimeError, match="backend down"):
        service.list_users()
