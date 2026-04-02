"""Unit tests for encrypted user API key storage."""

import base64
import os

from auth.models import UserSettings


def test_user_settings_encrypts_and_decrypts_binance_credentials(monkeypatch):
    """UserSettings should encrypt stored Binance API credentials and decrypt them when read."""
    raw_key = base64.b64encode(os.urandom(32)).decode()
    monkeypatch.setenv("BINANCE_ENC_KEY", raw_key)

    settings = UserSettings(
        id="test-settings-id",
        user_id="test-user-id",
        theme="light",
        notification_preferences={"email": True, "push": False},
        risk_profile="moderate",
        api_keys=None,
    )

    settings.set_api_credentials("binance", "test_binance_key", "test_binance_secret")

    assert settings.api_keys is not None
    assert settings.api_keys["binance"]["api_key"] != "test_binance_key"
    assert settings.api_keys["binance"]["api_secret"] != "test_binance_secret"
    assert isinstance(settings.api_keys["binance"]["api_key"], dict)
    assert isinstance(settings.api_keys["binance"]["api_secret"], dict)

    assert settings.get_api_key("binance") == "test_binance_key"
    assert settings.get_api_secret("binance") == "test_binance_secret"


def test_user_settings_returns_plaintext_values_for_legacy_storage():
    """Legacy plaintext API values should still be returned if present."""
    settings = UserSettings(
        id="test-settings-id",
        user_id="test-user-id",
        theme="light",
        notification_preferences={"email": True, "push": False},
        risk_profile="moderate",
        api_keys={
            "binance": {
                "api_key": "legacy_key",
                "api_secret": "legacy_secret",
            }
        },
    )

    assert settings.get_api_key("binance") == "legacy_key"
    assert settings.get_api_secret("binance") == "legacy_secret"
