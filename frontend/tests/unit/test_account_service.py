from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from schemas.account import AccountProfile, ExchangeCredentialInput
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
def _mock_set_exchange():
    with patch("services.account_service.set_exchange_configured"):
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


def test_save_exchange_credentials_empty_key_rejected(store) -> None:
    client = MagicMock(spec=BackendApiClient)
    service = AccountService(store, client=client)
    ok, _ = service.save_exchange_credentials(
        ExchangeCredentialInput(exchange="binance", api_key="", api_secret="AS_NEW_987")
    )
    assert ok is False
    client.update_user_settings.assert_not_called()


def test_save_exchange_credentials_empty_secret_rejected(store) -> None:
    client = MagicMock(spec=BackendApiClient)
    service = AccountService(store, client=client)
    ok, _ = service.save_exchange_credentials(
        ExchangeCredentialInput(exchange="binance", api_key="AK_NEW_123", api_secret="")
    )
    assert ok is False
    client.update_user_settings.assert_not_called()


def test_save_exchange_credentials_success(store) -> None:
    client = MagicMock(spec=BackendApiClient)
    client.update_user_settings.return_value = _ok({"configured_exchanges": ["binance"]})
    service = AccountService(store, client=client)
    ok, _ = service.save_exchange_credentials(
        ExchangeCredentialInput(exchange="binance", api_key="AK_NEW_123", api_secret="AS_NEW_987")
    )
    assert ok is True
    client.update_user_settings.assert_called_once()
    assert client.update_user_settings.call_args.kwargs["exchange"] == "binance"


def test_save_exchange_credentials_for_kraken_passes_exchange_through(store) -> None:
    client = MagicMock(spec=BackendApiClient)
    client.update_user_settings.return_value = _ok({"configured_exchanges": ["kraken"]})
    service = AccountService(store, client=client)
    ok, _ = service.save_exchange_credentials(
        ExchangeCredentialInput(exchange="kraken", api_key="AK_NEW_123", api_secret="AS_NEW_987")
    )
    assert ok is True
    assert client.update_user_settings.call_args.kwargs["exchange"] == "kraken"


def test_get_exchange_status_configured(store) -> None:
    client = MagicMock(spec=BackendApiClient)
    client.get_user_settings.return_value = _ok({"configured_exchanges": ["binance"]})
    service = AccountService(store, client=client)
    status = service.get_exchange_status("binance")
    assert status.configured is True
    assert "*" in status.api_key_masked


def test_get_exchange_status_not_configured(store) -> None:
    client = MagicMock(spec=BackendApiClient)
    client.get_user_settings.return_value = _ok({"configured_exchanges": []})
    service = AccountService(store, client=client)
    status = service.get_exchange_status("binance")
    assert status.configured is False
    assert status.api_key_masked == ""


def test_get_exchange_status_distinguishes_exchanges(store) -> None:
    client = MagicMock(spec=BackendApiClient)
    client.get_user_settings.return_value = _ok({"configured_exchanges": ["binance"]})
    service = AccountService(store, client=client)
    assert service.get_exchange_status("binance").configured is True
    assert service.get_exchange_status("kraken").configured is False


def test_list_configured_exchanges_returns_sorted_list(store) -> None:
    client = MagicMock(spec=BackendApiClient)
    client.get_user_settings.return_value = _ok({"configured_exchanges": ["kraken", "binance"]})
    service = AccountService(store, client=client)
    assert service.list_configured_exchanges() == ["binance", "kraken"]


def test_list_configured_exchanges_empty_when_backend_call_fails(store) -> None:
    client = MagicMock(spec=BackendApiClient)
    client.get_user_settings.return_value = _err()
    service = AccountService(store, client=client)
    assert service.list_configured_exchanges() == []


def test_delete_exchange_credentials_sends_empty_keys_for_that_exchange(store) -> None:
    client = MagicMock(spec=BackendApiClient)
    client.update_user_settings.return_value = _ok({"configured_exchanges": ["kraken"]})
    service = AccountService(store, client=client)
    ok, _ = service.delete_exchange_credentials("binance")
    assert ok is True
    client.update_user_settings.assert_called_once_with(
        "fake-token", exchange="binance", api_key="", api_secret=""
    )


def test_delete_exchange_credentials_does_not_affect_other_exchanges(store) -> None:
    client = MagicMock(spec=BackendApiClient)
    client.update_user_settings.side_effect = [
        _ok({"configured_exchanges": ["binance"]}),
    ]
    service = AccountService(store, client=client)
    service.delete_exchange_credentials("kraken")
    # Seul "kraken" est envoye pour suppression ; "binance" n'est jamais touche par cet appel.
    _, kwargs = client.update_user_settings.call_args
    assert kwargs["exchange"] == "kraken"
