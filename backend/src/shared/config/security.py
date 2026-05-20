"""
Chiffrement AES-GCM des secrets utilisateur (cles API Binance).

La cle racine est lue depuis BINANCE_ENC_KEY (base64, 128/192/256 bits).
Chaque appel a encrypt_secret() genere un nouveau nonce aleatoire.
"""

import os
from base64 import b64decode, b64encode

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

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
    aesgcm = AESGCM(_get_binance_aes_key())
    nonce = os.urandom(12)
    ciphertext = aesgcm.encrypt(nonce, plaintext.encode("utf-8"), None)
    return {
        "ciphertext": b64encode(ciphertext).decode(),
        "nonce": b64encode(nonce).decode(),
    }


def decrypt_secret(ciphertext_b64: str, nonce_b64: str) -> str:
    aesgcm = AESGCM(_get_binance_aes_key())
    ciphertext = b64decode(ciphertext_b64)
    nonce = b64decode(nonce_b64)
    return aesgcm.decrypt(nonce, ciphertext, None).decode()
