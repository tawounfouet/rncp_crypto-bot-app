from __future__ import annotations

from collections import deque

import streamlit as st

from schemas.auth import LoginRequest, RegisterRequest
from services.auth_api_client import ApiResponse
from services.auth_service import AuthService
from state.session import set_auth_tokens, sync_current_user_from_backend


def _token_payload(
    *,
    email: str,
    username: str,
    is_admin: bool = False,
) -> dict[str, object]:
    return {
        "success": True,
        "message": None,
        "data": None,
        "timestamp": "2026-04-25T10:00:00+00:00",
        "access_token": "access-token",
        "refresh_token": "refresh-token",
        "token_type": "bearer",
        "expires_in": 1800,
        "user": {
            "id": "usr-test-1",
            "email": email,
            "username": username,
            "first_name": "Nina",
            "last_name": "Durand",
            "is_active": True,
            "is_admin": is_admin,
            "created_at": "2026-04-25T09:59:00+00:00",
            "updated_at": "2026-04-25T10:00:00+00:00",
        },
    }


class StubAuthClient:
    def __init__(self) -> None:
        self.login_response = ApiResponse(status_code=500, data={"detail": "missing stub"})
        self.register_response = ApiResponse(status_code=500, data={"detail": "missing stub"})
        self.refresh_response = ApiResponse(status_code=500, data={"detail": "missing stub"})
        self.logout_response = ApiResponse(status_code=200, data={"message": "ok"})
        self.current_user_responses: deque[ApiResponse] = deque()
        self.calls: list[tuple] = []

    def login_json(self, *, username: str, password: str) -> ApiResponse:
        self.calls.append(("login_json", username, password))
        return self.login_response

    def register(
        self,
        *,
        email: str,
        username: str,
        password: str,
        first_name: str | None = None,
        last_name: str | None = None,
    ) -> ApiResponse:
        self.calls.append(("register", email, username, password, first_name, last_name))
        return self.register_response

    def refresh_token(self, refresh_token: str) -> ApiResponse:
        self.calls.append(("refresh_token", refresh_token))
        return self.refresh_response

    def logout(self, refresh_token: str) -> ApiResponse:
        self.calls.append(("logout", refresh_token))
        return self.logout_response

    def get_current_user(self, access_token: str) -> ApiResponse:
        self.calls.append(("get_current_user", access_token))
        return self.current_user_responses.popleft()


def test_login_success(store) -> None:
    st.session_state.clear()
    client = StubAuthClient()
    client.login_response = ApiResponse(status_code=200, data=_token_payload(email="nina@cryptobot.dev", username="nina"))

    service = AuthService(store, client=client)
    result = service.login(LoginRequest(email="nina@cryptobot.dev", password="Strong123"))

    assert result.success is True
    assert result.user is not None
    assert store.current_user_email == "nina@cryptobot.dev"
    assert st.session_state["access_token"] == "access-token"
    assert st.session_state["refresh_token"] == "refresh-token"
    assert client.calls[0] == ("login_json", "nina@cryptobot.dev", "Strong123")


def test_login_normalizes_email_before_backend_call(store) -> None:
    st.session_state.clear()
    client = StubAuthClient()
    client.login_response = ApiResponse(status_code=200, data=_token_payload(email="nina@cryptobot.dev", username="nina"))

    service = AuthService(store, client=client)
    result = service.login(LoginRequest(email=" Nina@CryptoBot.Dev ", password="Strong123"))

    assert result.success is True
    assert client.calls[0] == ("login_json", "nina@cryptobot.dev", "Strong123")


def test_register_surfaces_backend_error(store) -> None:
    st.session_state.clear()
    client = StubAuthClient()
    client.register_response = ApiResponse(status_code=400, data={"detail": "Email already registered"})

    service = AuthService(store, client=client)
    result = service.register(
        RegisterRequest(
            first_name="Nina",
            last_name="Durand",
            email="nina@cryptobot.dev",
            username="nina",
            password="Strong123",
            confirm_password="Strong123",
        )
    )

    assert result.success is False
    assert result.message == "Email already registered"


def test_register_derives_username_when_missing(store) -> None:
    st.session_state.clear()
    client = StubAuthClient()
    client.register_response = ApiResponse(
        status_code=201,
        data=_token_payload(email="nina@cryptobot.dev", username="nina"),
    )

    service = AuthService(store, client=client)
    result = service.register(
        RegisterRequest(
            first_name="Nina",
            last_name="Durand",
            email="nina@cryptobot.dev",
            password="Strong123",
            confirm_password="Strong123",
        )
    )

    assert result.success is True
    assert ("register", "nina@cryptobot.dev", "nina", "Strong123", "Nina", "Durand") in client.calls


def test_ensure_authenticated_user_reuses_recent_local_user_without_backend_call(store) -> None:
    st.session_state.clear()
    client = StubAuthClient()
    set_auth_tokens("access-token", "refresh-token")
    sync_current_user_from_backend(
        {
            "id": "usr-test-1",
            "email": "nina@cryptobot.dev",
            "username": "nina",
            "first_name": "Nina",
            "last_name": "Durand",
            "is_active": True,
            "is_admin": False,
            "created_at": "2026-04-25T09:59:00+00:00",
            "updated_at": "2026-04-25T10:00:00+00:00",
        },
        store=store,
        access_token="access-token",
    )

    service = AuthService(store, client=client)
    user = service.ensure_authenticated_user()

    assert user is not None
    assert user.email == "nina@cryptobot.dev"
    assert client.calls == []


def test_ensure_authenticated_user_refreshes_token_on_401(store) -> None:
    st.session_state.clear()
    client = StubAuthClient()
    client.current_user_responses.extend(
        [
            ApiResponse(status_code=401, data={"detail": "Could not validate credentials"}),
            ApiResponse(
                status_code=200,
                data={
                    "id": "usr-test-1",
                    "email": "nina@cryptobot.dev",
                    "username": "nina",
                    "first_name": "Nina",
                    "last_name": "Durand",
                    "is_active": True,
                    "is_admin": False,
                    "created_at": "2026-04-25T09:59:00+00:00",
                    "updated_at": "2026-04-25T10:00:00+00:00",
                },
            ),
        ]
    )
    client.refresh_response = ApiResponse(
        status_code=200,
        data={"access_token": "new-access-token", "token_type": "bearer"},
    )

    st.session_state["access_token"] = "expired-access-token"
    st.session_state["refresh_token"] = "refresh-token"
    service = AuthService(store, client=client)

    user = service.ensure_authenticated_user()

    assert user is not None
    assert user.email == "nina@cryptobot.dev"
    assert st.session_state["access_token"] == "new-access-token"
    assert store.current_user_email == "nina@cryptobot.dev"
    assert client.calls == [
        ("get_current_user", "expired-access-token"),
        ("refresh_token", "refresh-token"),
        ("get_current_user", "new-access-token"),
    ]


def test_logout_clears_local_session_even_if_backend_logout_fails(store) -> None:
    st.session_state.clear()
    client = StubAuthClient()
    client.logout_response = ApiResponse(status_code=400, data={"detail": "Invalid refresh token"})
    st.session_state["access_token"] = "access-token"
    st.session_state["refresh_token"] = "refresh-token"
    store.current_user_email = "alice@cryptobot.dev"

    service = AuthService(store, client=client)
    service.logout()

    assert store.current_user_email is None
    assert st.session_state["access_token"] is None
    assert st.session_state["refresh_token"] is None
    assert ("logout", "refresh-token") in client.calls
