"""对称加解密工具，负责保护每个用户自己的 LLM API Key。"""
# 加解密工具模块，负责 LLM 密钥的加密与解密。


import base64
import hashlib

from cryptography.fernet import Fernet
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from app.core.config import get_settings

IV_LENGTH = 12
TAG_LENGTH = 16


def _fernet_key() -> bytes:
    """根据原始密钥派生出 Fernet 需要的 32 字节 URL-safe Base64 密钥。"""
    secret = get_settings().llm_key_encryption_secret
    raw = hashlib.sha256(secret.encode()).digest()
    return base64.urlsafe_b64encode(raw)


def encrypt_api_key(plaintext: str) -> str:
    """使用 Fernet 加密 API Key。

    返回 Base64 编码后的密文字符串。
    如果当前没有配置加密密钥，则直接回传原文，作为开发环境兜底行为。
    """
    if not get_settings().llm_key_encryption_secret:
        return plaintext
    f = Fernet(_fernet_key())
    return f.encrypt(plaintext.encode()).decode()


def decrypt_api_key(ciphertext: str) -> str:
    """解密由 :func:`encrypt_api_key` 加密过的 API Key。

    如果当前没有配置加密密钥，则直接回传原始输入，作为开发环境兜底行为。
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
