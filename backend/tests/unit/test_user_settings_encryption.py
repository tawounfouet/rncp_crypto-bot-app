"""Unit tests for encrypted user API key storage."""

import base64
import os

import pytest
from auth.models import UserSettings
from shared.config.security import decrypt_secret, encrypt_secret


# =============================================================================
# Tests encrypt_secret / decrypt_secret
# =============================================================================


class TestEncryptDecryptSecret:
    """Tests directs pour les fonctions encrypt_secret et decrypt_secret."""

    def test_encrypt_decrypt_roundtrip(self, monkeypatch):
        """Chiffrer puis dechiffrer retourne le texte original."""
        raw_key = base64.b64encode(os.urandom(32)).decode()
        monkeypatch.setenv("EXCHANGE_ENC_KEY", raw_key)

        plaintext = "my_super_secret_api_key_123"
        encrypted = encrypt_secret(plaintext)
        decrypted = decrypt_secret(encrypted["ciphertext"], encrypted["nonce"])

        assert decrypted == plaintext

    def test_encrypt_returns_dict_with_required_keys(self, monkeypatch):
        """encrypt_secret retourne un dict avec ciphertext et nonce en base64."""
        raw_key = base64.b64encode(os.urandom(32)).decode()
        monkeypatch.setenv("EXCHANGE_ENC_KEY", raw_key)

        result = encrypt_secret("test")

        assert isinstance(result, dict)
        assert "ciphertext" in result
        assert "nonce" in result
        # Verifier que ce sont des strings base64 valides
        base64.b64decode(result["ciphertext"])
        base64.b64decode(result["nonce"])

    def test_encrypt_produces_different_ciphertexts(self, monkeypatch):
        """Deux chiffrements du meme texte donnent des resultats differents (nonce aleatoire)."""
        raw_key = base64.b64encode(os.urandom(32)).decode()
        monkeypatch.setenv("EXCHANGE_ENC_KEY", raw_key)

        enc1 = encrypt_secret("same_text")
        enc2 = encrypt_secret("same_text")

        assert enc1["ciphertext"] != enc2["ciphertext"]
        assert enc1["nonce"] != enc2["nonce"]

    def test_encrypt_raises_without_env_key(self, monkeypatch):
        """encrypt_secret leve RuntimeError si EXCHANGE_ENC_KEY n'est pas defini."""
        monkeypatch.delenv("EXCHANGE_ENC_KEY", raising=False)

        with pytest.raises(RuntimeError, match="Missing required environment variable"):
            encrypt_secret("test")

    def test_encrypt_raises_with_invalid_key_length(self, monkeypatch):
        """encrypt_secret leve ValueError si la cle n'a pas une taille AES valide."""
        # 10 bytes = 80 bits, pas valide pour AES
        bad_key = base64.b64encode(os.urandom(10)).decode()
        monkeypatch.setenv("EXCHANGE_ENC_KEY", bad_key)

        with pytest.raises(ValueError, match="128-, 192- or 256-bit"):
            encrypt_secret("test")


# =============================================================================
# Tests UserSettings - credentials API
# =============================================================================


def test_user_settings_encrypts_and_decrypts_binance_credentials(monkeypatch):
    """UserSettings should encrypt stored Binance API credentials and decrypt them when read."""
    raw_key = base64.b64encode(os.urandom(32)).decode()
    monkeypatch.setenv("EXCHANGE_ENC_KEY", raw_key)

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
    stored = settings.api_keys["binance"]["live"]
    assert stored["api_key"] != "test_binance_key"
    assert stored["api_secret"] != "test_binance_secret"
    assert isinstance(stored["api_key"], dict)
    assert isinstance(stored["api_secret"], dict)
    assert settings.api_keys["binance"]["active_mode"] == "live"

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


def test_user_settings_multiple_exchanges(monkeypatch):
    """On peut stocker des credentials pour plusieurs exchanges."""
    raw_key = base64.b64encode(os.urandom(32)).decode()
    monkeypatch.setenv("EXCHANGE_ENC_KEY", raw_key)

    settings = UserSettings(
        id="test-id",
        user_id="test-user",
        theme="light",
        notification_preferences={"email": True},
        risk_profile="moderate",
        api_keys=None,
    )

    settings.set_api_credentials("binance", "binance_key", "binance_secret")
    settings.set_api_credentials("kraken", "kraken_key", "kraken_secret")

    assert settings.get_api_key("binance") == "binance_key"
    assert settings.get_api_secret("binance") == "binance_secret"
    assert settings.get_api_key("kraken") == "kraken_key"
    assert settings.get_api_secret("kraken") == "kraken_secret"


def test_user_settings_remove_api_credentials(monkeypatch):
    """remove_api_credentials supprime les credentials d'un exchange."""
    raw_key = base64.b64encode(os.urandom(32)).decode()
    monkeypatch.setenv("EXCHANGE_ENC_KEY", raw_key)

    settings = UserSettings(
        id="test-id",
        user_id="test-user",
        theme="light",
        notification_preferences={"email": True},
        risk_profile="moderate",
        api_keys=None,
    )

    settings.set_api_credentials("binance", "key", "secret")
    settings.remove_api_credentials("binance")

    assert settings.get_api_key("binance") is None
    assert settings.get_api_secret("binance") is None


def test_user_settings_get_api_key_unknown_exchange():
    """get_api_key retourne None pour un exchange inconnu."""
    settings = UserSettings(
        id="test-id",
        user_id="test-user",
        theme="light",
        notification_preferences={"email": True},
        risk_profile="moderate",
        api_keys=None,
    )

    assert settings.get_api_key("binance") is None
    assert settings.get_api_secret("binance") is None


# =============================================================================
# Tests UserSettings - mode simule/reel (live/sandbox)
# =============================================================================


def _settings_with_env(monkeypatch) -> UserSettings:
    raw_key = base64.b64encode(os.urandom(32)).decode()
    monkeypatch.setenv("EXCHANGE_ENC_KEY", raw_key)
    return UserSettings(
        id="test-id",
        user_id="test-user",
        theme="light",
        notification_preferences={"email": True},
        risk_profile="moderate",
        api_keys=None,
    )


def test_set_api_credentials_defaults_to_live_mode_and_activates_it(monkeypatch):
    settings = _settings_with_env(monkeypatch)

    settings.set_api_credentials("binance", "key", "secret")

    assert settings.get_active_mode("binance") == "live"
    assert settings.has_credentials("binance", "live")
    assert not settings.has_credentials("binance", "sandbox")


def test_set_api_credentials_can_target_sandbox_mode_without_touching_live(monkeypatch):
    settings = _settings_with_env(monkeypatch)

    settings.set_api_credentials("binance", "live_key", "live_secret", mode="live")
    settings.set_api_credentials("binance", "sandbox_key", "sandbox_secret", mode="sandbox")

    assert settings.get_active_mode("binance") == "sandbox"  # dernier mode enregistre devient actif
    assert settings.get_api_key("binance", mode="live") == "live_key"
    assert settings.get_api_key("binance", mode="sandbox") == "sandbox_key"
    assert settings.get_api_key("binance") == "sandbox_key"  # sans mode explicite -> mode actif


def test_set_active_mode_switches_without_resupplying_keys(monkeypatch):
    settings = _settings_with_env(monkeypatch)
    settings.set_api_credentials("binance", "live_key", "live_secret", mode="live")
    settings.set_api_credentials("binance", "sandbox_key", "sandbox_secret", mode="sandbox")

    settings.set_active_mode("binance", "live")

    assert settings.get_active_mode("binance") == "live"
    assert settings.get_api_key("binance") == "live_key"


def test_set_active_mode_raises_without_any_live_credentials(monkeypatch):
    settings = _settings_with_env(monkeypatch)

    with pytest.raises(ValueError, match="non configure"):
        settings.set_active_mode("binance", "sandbox")


def test_kraken_style_exchange_can_use_sandbox_mode_without_dedicated_keys(monkeypatch):
    """Kraken n'a pas de cles sandbox distinctes : le mode 'sandbox' pilote validate=true
    a l'execution, pas un jeu de cles different (cf. testnet-simulation-modes.md)."""
    settings = _settings_with_env(monkeypatch)
    settings.set_api_credentials("kraken", "real_key", "real_secret", mode="live")

    settings.set_active_mode("kraken", "sandbox")

    assert settings.get_active_mode("kraken") == "sandbox"
    assert not settings.has_credentials("kraken", "sandbox")
    # Les cles utilisees restent les cles reelles -- seul le comportement (validate=true)
    # differe, decide par le mode actif au niveau du client d'execution, pas ici.
    assert settings.get_api_key("kraken", mode="live") == "real_key"


def test_remove_api_credentials_for_one_mode_keeps_the_other(monkeypatch):
    settings = _settings_with_env(monkeypatch)
    settings.set_api_credentials("binance", "live_key", "live_secret", mode="live")
    settings.set_api_credentials("binance", "sandbox_key", "sandbox_secret", mode="sandbox")

    settings.remove_api_credentials("binance", mode="sandbox")

    assert settings.has_credentials("binance", "live")
    assert not settings.has_credentials("binance", "sandbox")
    assert settings.get_active_mode("binance") == "live"  # bascule automatique, sandbox supprime


def test_remove_api_credentials_last_mode_removes_the_exchange_entirely(monkeypatch):
    settings = _settings_with_env(monkeypatch)
    settings.set_api_credentials("binance", "key", "secret", mode="live")

    settings.remove_api_credentials("binance", mode="live")

    assert "binance" not in (settings.api_keys or {})


def test_legacy_flat_storage_is_read_as_live_mode_without_migration():
    """Anciennes cles (avant le mode simule/reel) restent lisibles telles quelles."""
    settings = UserSettings(
        id="test-id",
        user_id="test-user",
        theme="light",
        notification_preferences={"email": True},
        risk_profile="moderate",
        api_keys={"binance": {"api_key": "legacy_key", "api_secret": "legacy_secret"}},
    )

    assert settings.get_active_mode("binance") == "live"
    assert settings.get_api_key("binance", mode="live") == "legacy_key"
    assert settings.get_api_key("binance", mode="sandbox") is None


def test_exchange_credentials_detail_reports_modes_and_active_mode(monkeypatch):
    settings = _settings_with_env(monkeypatch)
    settings.set_api_credentials("binance", "live_key", "live_secret", mode="live")
    settings.set_api_credentials("binance", "sandbox_key", "sandbox_secret", mode="sandbox")
    settings.set_api_credentials("kraken", "real_key", "real_secret", mode="live")

    detail = settings.exchange_credentials_detail()

    assert detail == {
        "binance": {"live": True, "sandbox": True, "active_mode": "sandbox"},
        "kraken": {"live": True, "sandbox": False, "active_mode": "live"},
    }


def test_exchange_credentials_detail_handles_legacy_storage():
    settings = UserSettings(
        id="test-id",
        user_id="test-user",
        theme="light",
        notification_preferences={"email": True},
        risk_profile="moderate",
        api_keys={"binance": {"api_key": "legacy_key", "api_secret": "legacy_secret"}},
    )

    assert settings.exchange_credentials_detail() == {
        "binance": {"live": True, "sandbox": False, "active_mode": "live"},
    }
