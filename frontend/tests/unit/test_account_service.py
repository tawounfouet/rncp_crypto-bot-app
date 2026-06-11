from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from schemas.account import AccountProfile, BinanceCredentialInput
from services.account_service import AccountService
from services.api_client import BackendApiClient
from services.auth_api_client import ApiResponse


def _ok(data: object) -> ApiResponse:
    return ApiResponse(status_code=200, data=data)


def _err(msg: str = "error", code: int = 400) -> ApiResponse:
    return ApiResponse(status_code=code, data={}, error=msg)


@pytest.fixture(autouse=True)
def _mock_token():
    with patch("services.account_service.get_access_token", return_value="fake-token"):
        yield


@pytest.fixture(autouse=True)
def _mock_sync():
    with patch("services.account_service.sync_current_user_from_backend"):
        yield


@pytest.fixture(autouse=True)
def _mock_set_binance():
    with patch("services.account_service.set_binance_configured"):
        yield


def test_update_profile_success(store) -> None:
    client = MagicMock(spec=BackendApiClient)
    client.update_user.return_value = _ok(
        {"first_name": "Alice2", "last_name": "Martin", "email": "alice2@cryptobot.dev"}
    )
    service = AccountService(store, client=client)
    ok, _ = service.update_profile(
        AccountProfile(first_name="Alice2", last_name="Martin", email="alice2@cryptobot.dev")
    )
    assert ok is True
    client.update_user.assert_called_once()


def test_update_profile_invalid_email(store) -> None:
    client = MagicMock(spec=BackendApiClient)
    service = AccountService(store, client=client)
    ok, _ = service.update_profile(
        AccountProfile(first_name="Alice", last_name="Martin", email="not-an-email")
    )
    assert ok is False
    client.update_user.assert_not_called()


def test_update_profile_empty_first_name(store) -> None:
    client = MagicMock(spec=BackendApiClient)
    service = AccountService(store, client=client)
    ok, _ = service.update_profile(
        AccountProfile(first_name="", last_name="Martin", email="alice@test.dev")
    )
    assert ok is False
    client.update_user.assert_not_called()


def test_save_binance_credentials_empty_key_rejected(store) -> None:
    client = MagicMock(spec=BackendApiClient)
    service = AccountService(store, client=client)
    ok, _ = service.save_binance_credentials(
        BinanceCredentialInput(api_key="", api_secret="AS_NEW_987")
    )
    assert ok is False
    client.update_user_settings.assert_not_called()


def test_save_binance_credentials_empty_secret_rejected(store) -> None:
    client = MagicMock(spec=BackendApiClient)
    service = AccountService(store, client=client)
    ok, _ = service.save_binance_credentials(
        BinanceCredentialInput(api_key="AK_NEW_123", api_secret="")
    )
    assert ok is False
    client.update_user_settings.assert_not_called()


def test_save_binance_credentials_success(store) -> None:
    client = MagicMock(spec=BackendApiClient)
    client.update_user_settings.return_value = _ok({"has_binance_credentials": True})
    service = AccountService(store, client=client)
    ok, _ = service.save_binance_credentials(
        BinanceCredentialInput(api_key="AK_NEW_123", api_secret="AS_NEW_987")
    )
    assert ok is True
    client.update_user_settings.assert_called_once()


def test_get_binance_status_configured(store) -> None:
    client = MagicMock(spec=BackendApiClient)
    client.get_user_settings.return_value = _ok({"has_binance_credentials": True})
    service = AccountService(store, client=client)
    status = service.get_binance_status()
    assert status.configured is True
    assert "*" in status.api_key_masked


def test_get_binance_status_not_configured(store) -> None:
    client = MagicMock(spec=BackendApiClient)
    client.get_user_settings.return_value = _ok({"has_binance_credentials": False})
    service = AccountService(store, client=client)
    status = service.get_binance_status()
    assert status.configured is False
    assert status.api_key_masked == ""
