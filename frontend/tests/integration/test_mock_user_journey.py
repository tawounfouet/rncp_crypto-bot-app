"""Integration test: simulated full user journey via mocked backend HTTP clients."""

from __future__ import annotations

import streamlit as st

from mocks.db import create_mock_store
from schemas.account import AccountProfile
from schemas.auth import LoginRequest, RegisterRequest
from schemas.common import UserRole
from services.account_service import AccountService
from services.admin_service import AdminService
from services.api_client import BackendApiClient
from services.auth_api_client import ApiResponse
from services.auth_service import AuthService
from services.bot_config_service import BotConfigService
from services.bot_control_service import BotControlService
from state.session import set_auth_tokens
from utils.constants import ACTION_START


class JourneyAuthClient:
    """Auth client simule pour le test de parcours."""

    def __init__(self) -> None:
        self.users: dict[str, dict] = {}
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
        user = {k: v for k, v in self.users[email_key].items() if k != "password"}
        if not user.get("last_name"):
            user["last_name"] = None
        return ApiResponse(status_code=200, data=user)

    def _issue_tokens(self, email_key: str) -> ApiResponse:
        access_token = f"access-{email_key}"
        refresh_token = f"refresh-{email_key}"
        self.token_to_email[access_token] = email_key
        self.token_to_email[refresh_token] = email_key

        user = {k: v for k, v in self.users[email_key].items() if k != "password"}
        if not user.get("last_name"):
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


class JourneyBackendClient(BackendApiClient):
    """
    Simule le backend FastAPI en memoire pour les tests d'integration.
    Extends BackendApiClient mais intercepte tous les appels reseau.
    """

    def __init__(self, auth_client: JourneyAuthClient) -> None:
        # Ne pas appeler super().__init__() pour eviter toute connexion reseau
        self._auth = auth_client
        self._strategies: dict[str, dict] = {
            "strat_sol": {
                "id": "strat_sol",
                "name": "SOL Trend",
                "strategy_type": "trend",
                "is_active": True,
                "updated_at": "2024-01-01T00:00:00Z",
                "parameters": {"budget_usdc": 2000.0, "max_open_positions": 3, "version": 1},
            },
        }
        self._configured_exchanges: dict[str, set[str]] = {}

    def _user_by_token(self, token: str) -> dict | None:
        email = self._auth.token_to_email.get(token)
        return self._auth.users.get(email) if email else None

    # ─── Users ───────────────────────────────────────────────────────────────

    def update_user(self, access_token, *, first_name=None, last_name=None, email=None):
        user = self._user_by_token(access_token)
        if not user:
            return ApiResponse(status_code=401, data={"detail": "Unauthorized"})
        old_email = user["email"]
        if first_name is not None:
            user["first_name"] = first_name
        if last_name is not None:
            user["last_name"] = last_name
        if email and email.lower() != old_email:
            new_email = email.lower()
            user["email"] = new_email
            self._auth.users[new_email] = user
            del self._auth.users[old_email]
            for k, v in list(self._auth.token_to_email.items()):
                if v == old_email:
                    self._auth.token_to_email[k] = new_email
        result = {k: v for k, v in user.items() if k != "password"}
        return ApiResponse(status_code=200, data=result)

    def get_user_settings(self, access_token):
        if not self._user_by_token(access_token):
            return ApiResponse(status_code=401, data={})
        email = self._auth.token_to_email.get(access_token, "")
        return ApiResponse(
            status_code=200,
            data={"configured_exchanges": sorted(self._configured_exchanges.get(email, set()))},
        )

    def update_user_settings(self, access_token, *, exchange=None, api_key=None, api_secret=None, **_):
        email = self._auth.token_to_email.get(access_token)
        if not email:
            return ApiResponse(status_code=401, data={})
        if api_key and api_secret:
            self._configured_exchanges.setdefault(email, set()).add(exchange or "binance")
        return ApiResponse(
            status_code=200,
            data={"configured_exchanges": sorted(self._configured_exchanges.get(email, set()))},
        )

    def list_users(self, access_token):
        return ApiResponse(
            status_code=200,
            data=[{k: v for k, v in u.items() if k != "password"} for u in self._auth.users.values()],
        )

    def activate_user(self, access_token, user_id):
        return ApiResponse(status_code=200, data={"message": "activated"})

    def deactivate_user(self, access_token, user_id):
        return ApiResponse(status_code=200, data={"message": "deactivated"})

    def make_user_admin(self, access_token, user_id):
        return ApiResponse(status_code=200, data={"message": "promoted"})

    def remove_user_admin(self, access_token, user_id):
        return ApiResponse(status_code=200, data={"message": "demoted"})

    # ─── Strategies ──────────────────────────────────────────────────────────

    def list_strategies(self, access_token):
        return ApiResponse(status_code=200, data=list(self._strategies.values()))

    def get_strategy(self, access_token, strategy_id):
        s = self._strategies.get(strategy_id)
        if not s:
            return ApiResponse(status_code=404, data={"detail": "Not found"})
        return ApiResponse(status_code=200, data=dict(s))

    def update_strategy(self, access_token, strategy_id, payload):
        s = self._strategies.get(strategy_id)
        if not s:
            return ApiResponse(status_code=404, data={"detail": "Not found"})
        if "parameters" in payload:
            params = dict(s.get("parameters") or {})
            params.update(payload["parameters"])
            s["parameters"] = params
        return ApiResponse(status_code=200, data=dict(s))

    def list_deployments(self, access_token, *, active_only=False):
        return ApiResponse(status_code=200, data=[])

    # ─── Trading (stub) ──────────────────────────────────────────────────────

    def get_portfolio(self, access_token):
        return ApiResponse(status_code=200, data={"total_usd_value": 0.0, "balances": []})

    def list_orders(self, access_token, *, status=None, limit=50):
        return ApiResponse(status_code=200, data=[])

    def list_transactions(self, access_token, *, limit=100):
        return ApiResponse(status_code=200, data=[])

    def get_trading_stats(self, access_token, period="30d"):
        return ApiResponse(status_code=200, data={"total_trades": 0, "total_profit_loss": 0.0, "win_rate": 0.0})


def test_end_to_end_auth_and_backend_pages_journey() -> None:
    st.session_state.clear()
    store = create_mock_store(disable_latency=True)
    auth_client = JourneyAuthClient()
    backend = JourneyBackendClient(auth_client)

    # ── Auth: register + login ────────────────────────────────────────────────
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

    # ── Account: mise a jour du profil ───────────────────────────────────────
    account = AccountService(store, client=backend)
    ok, _ = account.update_profile(
        AccountProfile(first_name="Nina", last_name="Durand", email="nina2@cryptobot.dev")
    )
    assert ok is True
    # L'email dans le store est mis a jour via sync_current_user_from_backend
    assert store.current_user_email == "nina2@cryptobot.dev"

    # ── Bot control/config: bascule sur le fallback mock (pas simule par
    # JourneyBackendClient) ────────────────────────────────────────────────────
    set_auth_tokens(None, None)
    bot_control = BotControlService(store)
    action_result = bot_control.apply_action("bot_sol_trend", ACTION_START)
    assert action_result.success is True

    bot_config = BotConfigService(store)
    template = bot_config.list_templates()[0]
    select_result = bot_config.select_template(template.id)
    assert select_result[0] is True
    assert select_result[2] is not None
    assert select_result[2].config_snapshot["symbol"] == template.symbol

    # ── Admin: set_role fonctionne (mock fallback) ─────────────────────────────
    store.current_user_email = "nina2@cryptobot.dev"
    # Simuler un admin pour le store (pre-requis de AdminService._ensure_admin)
    store.users["nina2@cryptobot.dev"].role = UserRole.ADMIN

    admin = AdminService(store)
    ok, _ = admin.set_role("nina2@cryptobot.dev", UserRole.ADMIN)
    assert ok is True

    # list_users puis set_enabled fonctionne
    admin.list_users()
    ok, _ = admin.set_enabled("nina2@cryptobot.dev", True)
    assert ok is True
