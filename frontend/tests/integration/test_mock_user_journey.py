from __future__ import annotations

import streamlit as st

from mocks.db import create_mock_store
from schemas.account import AccountProfile
from schemas.auth import LoginRequest, RegisterRequest
from schemas.bot import BotConfigUpdate
from schemas.common import UserRole
from services.account_service import AccountService
from services.admin_service import AdminService
from services.auth_api_client import ApiResponse
from services.auth_service import AuthService
from services.bot_config_service import BotConfigService
from services.bot_control_service import BotControlService
from utils.constants import ACTION_START


class JourneyAuthClient:
    def __init__(self) -> None:
        self.users: dict[str, dict[str, str | bool]] = {}
        self.token_to_email: dict[str, str] = {}

    def register(
        self,
        *,
        email: str,
        username: str,
        password: str,
        first_name: str | None = None,
        last_name: str | None = None,
    ) -> ApiResponse:
        email_key = email.lower()
        if email_key in self.users:
            return ApiResponse(status_code=400, data={"detail": "Email already registered"})

        self.users[email_key] = {
            "id": f"usr-{len(self.users) + 1}",
            "email": email_key,
            "username": username,
            "password": password,
            "first_name": first_name or username,
            "last_name": last_name or "",
            "is_active": True,
            "is_admin": False,
            "created_at": "2026-04-25T10:00:00+00:00",
            "updated_at": "2026-04-25T10:00:00+00:00",
        }
        return self._issue_tokens(email_key)

    def login_json(self, *, username: str, password: str) -> ApiResponse:
        email_key = username.lower()
        user = self.users.get(email_key)
        if not user or user["password"] != password:
            return ApiResponse(status_code=401, data={"detail": "Incorrect username or password"})
        return self._issue_tokens(email_key)

    def refresh_token(self, refresh_token: str) -> ApiResponse:
        email_key = self.token_to_email.get(refresh_token)
        if not email_key:
            return ApiResponse(status_code=401, data={"detail": "Invalid refresh token"})
        access_token = f"access-{email_key}-refreshed"
        self.token_to_email[access_token] = email_key
        return ApiResponse(status_code=200, data={"access_token": access_token, "token_type": "bearer"})

    def logout(self, refresh_token: str) -> ApiResponse:
        self.token_to_email.pop(refresh_token, None)
        return ApiResponse(status_code=200, data={"message": "Successfully logged out"})

    def get_current_user(self, access_token: str) -> ApiResponse:
        email_key = self.token_to_email.get(access_token)
        if not email_key:
            return ApiResponse(status_code=401, data={"detail": "Could not validate credentials"})
        user = self.users[email_key].copy()
        user.pop("password", None)
        if not user["last_name"]:
            user["last_name"] = None
        return ApiResponse(status_code=200, data=user)

    def _issue_tokens(self, email_key: str) -> ApiResponse:
        access_token = f"access-{email_key}"
        refresh_token = f"refresh-{email_key}"
        self.token_to_email[access_token] = email_key
        self.token_to_email[refresh_token] = email_key

        user = self.users[email_key].copy()
        user.pop("password", None)
        if not user["last_name"]:
            user["last_name"] = None

        return ApiResponse(
            status_code=200,
            data={
                "success": True,
                "message": None,
                "data": None,
                "timestamp": "2026-04-25T10:00:00+00:00",
                "access_token": access_token,
                "refresh_token": refresh_token,
                "token_type": "bearer",
                "expires_in": 1800,
                "user": user,
            },
        )


def test_end_to_end_auth_and_mock_pages_journey() -> None:
    st.session_state.clear()
    store = create_mock_store(disable_latency=True)
    auth_client = JourneyAuthClient()

    auth = AuthService(store, client=auth_client)
    register = auth.register(
        RegisterRequest(
            first_name="Nina",
            last_name="Durand",
            email="nina@cryptobot.dev",
            username="nina",
            password="Strong123",
            confirm_password="Strong123",
        )
    )
    assert register.success is True
    assert store.current_user_email == "nina@cryptobot.dev"

    auth.logout()

    login = auth.login(LoginRequest(email="nina@cryptobot.dev", password="Strong123"))
    assert login.success is True
    assert store.current_user_email == "nina@cryptobot.dev"
    assert auth.ensure_authenticated_user() is not None

    account = AccountService(store)
    ok, _ = account.update_profile(
        AccountProfile(first_name="Nina", last_name="Durand", email="nina2@cryptobot.dev")
    )
    assert ok is True
    assert store.current_user_email == "nina2@cryptobot.dev"

    bot_control = BotControlService(store)
    action_result = bot_control.apply_action("bot_sol_trend", ACTION_START)
    assert action_result.success is True

    bot_config = BotConfigService(store)
    save_result = bot_config.save(
        "bot_sol_trend",
        BotConfigUpdate(
            strategy="Trend Following",
            budget_usdt=2500,
            max_open_positions=3,
            risk_per_trade_pct=1.1,
            take_profit_pct=5.8,
            stop_loss_pct=2.2,
            cooldown_seconds=180,
        ),
    )
    assert save_result[0] is True

    store.current_user_email = "admin@cryptobot.dev"
    store.users["nina2@cryptobot.dev"].role = UserRole.USER
    admin = AdminService(store)
    ok, _ = admin.set_role("nina2@cryptobot.dev", UserRole.ADMIN)
    assert ok is True
