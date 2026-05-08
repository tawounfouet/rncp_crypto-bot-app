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
        monkeypatch.setenv("BINANCE_ENC_KEY", raw_key)

        plaintext = "my_super_secret_api_key_123"
        encrypted = encrypt_secret(plaintext)
        decrypted = decrypt_secret(encrypted["ciphertext"], encrypted["nonce"])

        assert decrypted == plaintext

    def test_encrypt_returns_dict_with_required_keys(self, monkeypatch):
        """encrypt_secret retourne un dict avec ciphertext et nonce en base64."""
        raw_key = base64.b64encode(os.urandom(32)).decode()
        monkeypatch.setenv("BINANCE_ENC_KEY", raw_key)

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
        monkeypatch.setenv("BINANCE_ENC_KEY", raw_key)

        enc1 = encrypt_secret("same_text")
        enc2 = encrypt_secret("same_text")

        assert enc1["ciphertext"] != enc2["ciphertext"]
        assert enc1["nonce"] != enc2["nonce"]

    def test_encrypt_raises_without_env_key(self, monkeypatch):
        """encrypt_secret leve RuntimeError si BINANCE_ENC_KEY n'est pas defini."""
        monkeypatch.delenv("BINANCE_ENC_KEY", raising=False)

        with pytest.raises(RuntimeError, match="Missing required environment variable"):
            encrypt_secret("test")

    def test_encrypt_raises_with_invalid_key_length(self, monkeypatch):
        """encrypt_secret leve ValueError si la cle n'a pas une taille AES valide."""
        # 10 bytes = 80 bits, pas valide pour AES
        bad_key = base64.b64encode(os.urandom(10)).decode()
        monkeypatch.setenv("BINANCE_ENC_KEY", bad_key)

        with pytest.raises(ValueError, match="128-, 192- or 256-bit"):
            encrypt_secret("test")


# =============================================================================
# Tests UserSettings - credentials API
# =============================================================================


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


def test_user_settings_multiple_exchanges(monkeypatch):
    """On peut stocker des credentials pour plusieurs exchanges."""
    raw_key = base64.b64encode(os.urandom(32)).decode()
    monkeypatch.setenv("BINANCE_ENC_KEY", raw_key)

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
    monkeypatch.setenv("BINANCE_ENC_KEY", raw_key)

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
