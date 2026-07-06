"""
Chiffrement AES-GCM des secrets utilisateur (cles API Binance).

La cle racine est lue depuis BINANCE_ENC_KEY (base64, 128/192/256 bits).
Chaque appel a encrypt_secret() genere un nouveau nonce aleatoire.
"""

import os
from base64 import b64decode, b64encode
from hashlib import sha256
from hmac import compare_digest
from hmac import new as hmac_new

try:
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
except ModuleNotFoundError:
    AESGCM = None

BINANCE_ENC_KEY_ENV = "BINANCE_ENC_KEY"


def _get_binance_aes_key() -> bytes:
    key_b64 = os.getenv(BINANCE_ENC_KEY_ENV)
    if not key_b64:
        raise RuntimeError("Missing required environment variable BINANCE_ENC_KEY for Binance API key encryption")

    key = b64decode(key_b64)
    if len(key) not in (16, 24, 32):
        raise ValueError("BINANCE_ENC_KEY must decode to a 128-, 192- or 256-bit AES key")

    return key


def encrypt_secret(plaintext: str) -> dict:
    if AESGCM is None:
        if not _allow_crypto_fallback():
            raise RuntimeError("cryptography is required to encrypt Binance API credentials")
        return _fallback_encrypt_secret(plaintext)
    aesgcm = AESGCM(_get_binance_aes_key())
    nonce = os.urandom(12)
    ciphertext = aesgcm.encrypt(nonce, plaintext.encode("utf-8"), None)
    return {
        "ciphertext": b64encode(ciphertext).decode(),
        "nonce": b64encode(nonce).decode(),
    }


def decrypt_secret(ciphertext_b64: str, nonce_b64: str) -> str:
    if AESGCM is None:
        if not _allow_crypto_fallback():
            raise RuntimeError("cryptography is required to decrypt Binance API credentials")
        return _fallback_decrypt_secret(ciphertext_b64, nonce_b64)
    aesgcm = AESGCM(_get_binance_aes_key())
    ciphertext = b64decode(ciphertext_b64)
    nonce = b64decode(nonce_b64)
    return aesgcm.decrypt(nonce, ciphertext, None).decode()


def _fallback_encrypt_secret(plaintext: str) -> dict:
    key = _get_binance_aes_key()
    nonce = os.urandom(16)
    plaintext_bytes = plaintext.encode("utf-8")
    keystream = _fallback_keystream(key, nonce, len(plaintext_bytes))
    ciphertext = bytes(left ^ right for left, right in zip(plaintext_bytes, keystream, strict=True))
    tag = hmac_new(key, nonce + ciphertext, sha256).digest()
    return {
        "ciphertext": b64encode(ciphertext + tag).decode(),
        "nonce": b64encode(nonce).decode(),
        "alg": "fallback-hmac-sha256-stream",
    }


def _fallback_decrypt_secret(ciphertext_b64: str, nonce_b64: str) -> str:
    key = _get_binance_aes_key()
    nonce = b64decode(nonce_b64)
    payload = b64decode(ciphertext_b64)
    if len(payload) < 32:
        raise ValueError("Invalid encrypted secret payload")
    ciphertext = payload[:-32]
    tag = payload[-32:]
    expected_tag = hmac_new(key, nonce + ciphertext, sha256).digest()
    if not compare_digest(tag, expected_tag):
        raise ValueError("Invalid encrypted secret authentication tag")
    keystream = _fallback_keystream(key, nonce, len(ciphertext))
    plaintext = bytes(left ^ right for left, right in zip(ciphertext, keystream, strict=True))
    return plaintext.decode("utf-8")


def _fallback_keystream(key: bytes, nonce: bytes, length: int) -> bytes:
    blocks = []
    counter = 0
    while sum(len(block) for block in blocks) < length:
        blocks.append(hmac_new(key, nonce + counter.to_bytes(8, "big"), sha256).digest())
        counter += 1
    return b"".join(blocks)[:length]


def _allow_crypto_fallback() -> bool:
    return os.getenv("ALLOW_INSECURE_CRYPTO_FALLBACK") == "1"
