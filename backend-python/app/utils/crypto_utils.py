"""Symmetric encryption helpers for per-user LLM API keys."""

import base64
import hashlib

from cryptography.fernet import Fernet
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from app.core.config import get_settings

IV_LENGTH = 12
TAG_LENGTH = 16


def _fernet_key() -> bytes:
    """Derive a valid 32-byte URL-safe base64 Fernet key from the raw secret."""
    secret = get_settings().llm_key_encryption_secret
    raw = hashlib.sha256(secret.encode()).digest()
    return base64.urlsafe_b64encode(raw)


def encrypt_api_key(plaintext: str) -> str:
    """Encrypt an API key using Fernet.

    Returns a base64-encoded ciphertext string.
    If no encryption secret is configured, returns the plaintext as-is
    (dev-mode fallback).
    """
    if not get_settings().llm_key_encryption_secret:
        return plaintext
    f = Fernet(_fernet_key())
    return f.encrypt(plaintext.encode()).decode()


def decrypt_api_key(ciphertext: str) -> str:
    """Decrypt an API key previously encrypted with :func:`encrypt_api_key`.

    If no encryption secret is configured, returns the ciphertext as-is
    (dev-mode fallback).
    """
    if not get_settings().llm_key_encryption_secret:
        return ciphertext
    f = Fernet(_fernet_key())
    return f.decrypt(ciphertext.encode()).decode()


def _aes_key_bytes() -> bytes:
    secret = get_settings().llm_key_encryption_secret
    if not secret:
        raise ValueError("blank llm key encryption secret")
    return base64.b64decode(secret)


def decrypt_api_key_gcm(cipher_b64: str) -> str:
    if not get_settings().llm_key_encryption_secret:
        return cipher_b64
    raw = base64.b64decode(cipher_b64)
    if len(raw) < IV_LENGTH + TAG_LENGTH:
        raise ValueError("ciphertext too short for AES-GCM")
    iv = raw[:IV_LENGTH]
    ciphertext = raw[IV_LENGTH:]
    return AESGCM(_aes_key_bytes()).decrypt(iv, ciphertext, None).decode("utf-8")


def decrypt_task_api_key(ciphertext: str) -> str:
    try:
        return decrypt_api_key_gcm(ciphertext)
    except Exception:
        return decrypt_api_key(ciphertext)
