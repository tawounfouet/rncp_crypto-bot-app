from __future__ import annotations

from schemas.account import AccountProfile, BinanceCredentialInput
from services.account_service import AccountService


def test_update_profile(store) -> None:
    store.current_user_email = "alice@cryptobot.dev"
    service = AccountService(store)
    ok, _ = service.update_profile(
        AccountProfile(first_name="Alice2", last_name="Martin", email="alice2@cryptobot.dev")
    )
    assert ok is True
    assert store.current_user_email == "alice2@cryptobot.dev"


def test_save_binance_credentials_requires_password(store) -> None:
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
