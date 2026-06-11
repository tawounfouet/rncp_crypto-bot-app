from __future__ import annotations

import streamlit as st

from schemas.account import AccountProfile, BinanceCredentialInput
from services.account_service import AccountService
from services.auth_api_client import ApiResponse


class StubAccountClient:
    def __init__(self) -> None:
        self.status_response = ApiResponse(
            status_code=200,
            data={
                "configured": True,
                "updated_at": "2026-04-25T10:00:00+00:00",
                "api_key_masked": "AK_T********1234",
            },
        )
        self.save_response = self.status_response
        self.delete_response = ApiResponse(status_code=200, data={"configured": False})
        self.refresh_response = ApiResponse(status_code=500, data={"detail": "missing stub"})
        self.calls: list[tuple] = []

    def get_binance_credentials_status(self, access_token: str) -> ApiResponse:
        self.calls.append(("get_binance_credentials_status", access_token))
        return self.status_response

    def save_binance_credentials(
        self,
        *,
        access_token: str,
        api_key: str,
        api_secret: str,
        password_confirmation: str,
    ) -> ApiResponse:
        self.calls.append(
            ("save_binance_credentials", access_token, api_key, api_secret, password_confirmation)
        )
        return self.save_response

    def delete_binance_credentials(self, access_token: str) -> ApiResponse:
        self.calls.append(("delete_binance_credentials", access_token))
        return self.delete_response

    def refresh_token(self, refresh_token: str) -> ApiResponse:
        self.calls.append(("refresh_token", refresh_token))
        return self.refresh_response


def test_update_profile(store) -> None:
    st.session_state.clear()
    store.current_user_email = "alice@cryptobot.dev"
    service = AccountService(store)
    ok, _ = service.update_profile(
        AccountProfile(first_name="Alice2", last_name="Martin", email="alice2@cryptobot.dev")
    )
    assert ok is True
    assert store.current_user_email == "alice2@cryptobot.dev"


def test_save_binance_credentials_requires_password(store) -> None:
    st.session_state.clear()
    store.current_user_email = "alice@cryptobot.dev"
    service = AccountService(store)
    ok, message = service.save_binance_credentials(
        BinanceCredentialInput(
            api_key="AK_NEW_123",
            api_secret="AS_NEW_987",
            password_confirmation="wrong",
        )
    )
    assert ok is False
    assert "invalide" in message


def test_save_binance_credentials_success(store) -> None:
    st.session_state.clear()
    store.current_user_email = "alice@cryptobot.dev"
    service = AccountService(store)
    ok, _ = service.save_binance_credentials(
        BinanceCredentialInput(
            api_key="AK_NEW_123",
            api_secret="AS_NEW_987",
            password_confirmation="Passw0rd!",
        )
    )
    assert ok is True
    status = service.get_binance_status()
    assert status.configured is True
    assert "*" in status.api_secret_masked


def test_update_profile_preserves_binance_configuration_when_email_changes(store) -> None:
    st.session_state.clear()
    store.current_user_email = "alice@cryptobot.dev"
    service = AccountService(store)
    ok, _ = service.update_profile(
        AccountProfile(first_name="Alice", last_name="Martin", email="alice_new@cryptobot.dev")
    )
    assert ok is True
    assert "alice@cryptobot.dev" not in store.binance_credentials
    assert "alice_new@cryptobot.dev" in store.binance_credentials
    status = service.get_binance_status()
    assert status.configured is True


def test_get_binance_status_uses_backend_when_token_present(store) -> None:
    st.session_state.clear()
    st.session_state["access_token"] = "access-token"
    st.session_state["refresh_token"] = "refresh-token"
    store.current_user_email = "alice@cryptobot.dev"
    client = StubAccountClient()
    service = AccountService(store, client=client)

    status = service.get_binance_status()

    assert status.configured is True
    assert status.api_key_masked == "AK_T********1234"
    assert status.api_secret_masked == ""
    assert store.users["alice@cryptobot.dev"].binance_configured is True
    assert client.calls == [("get_binance_credentials_status", "access-token")]


def test_save_binance_credentials_uses_backend_when_token_present(store) -> None:
    st.session_state.clear()
    st.session_state["access_token"] = "access-token"
    st.session_state["refresh_token"] = "refresh-token"
    store.current_user_email = "alice@cryptobot.dev"
    client = StubAccountClient()
    service = AccountService(store, client=client)

    ok, message = service.save_binance_credentials(
        BinanceCredentialInput(
            api_key="AK_NEW_123",
            api_secret="AS_NEW_987",
            password_confirmation="Passw0rd!",
        )
    )

    assert ok is True
    assert "base" in message
    assert store.users["alice@cryptobot.dev"].binance_configured is True
    assert client.calls == [
        ("save_binance_credentials", "access-token", "AK_NEW_123", "AS_NEW_987", "Passw0rd!")
    ]


def test_save_binance_credentials_surfaces_backend_password_error(store) -> None:
    st.session_state.clear()
    st.session_state["access_token"] = "access-token"
    store.current_user_email = "alice@cryptobot.dev"
    client = StubAccountClient()
    client.save_response = ApiResponse(
        status_code=403,
        data={"detail": "Invalid password confirmation"},
    )
    service = AccountService(store, client=client)

    ok, message = service.save_binance_credentials(
        BinanceCredentialInput(
            api_key="AK_NEW_123",
            api_secret="AS_NEW_987",
            password_confirmation="wrong",
        )
    )

    assert ok is False
    assert "invalide" in message


def test_delete_binance_credentials_uses_backend_when_token_present(store) -> None:
    st.session_state.clear()
    st.session_state["access_token"] = "access-token"
    store.current_user_email = "alice@cryptobot.dev"
    client = StubAccountClient()
    service = AccountService(store, client=client)

    ok, message = service.delete_binance_credentials()

    assert ok is True
    assert "supprimees" in message
    assert store.users["alice@cryptobot.dev"].binance_configured is False
    assert client.calls == [("delete_binance_credentials", "access-token")]
