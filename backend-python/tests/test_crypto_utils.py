import base64

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from app.utils import crypto_utils


def test_decrypt_task_api_key_prefers_aes_gcm(monkeypatch):
    secret_b64 = "MGo++WTIw8a+iOkZAak7BVYIcE5DXix2uOjWsh1I4aY="
    key = base64.b64decode(secret_b64)
    iv = bytes.fromhex("00112233445566778899aabb")
    ciphertext = AESGCM(key).encrypt(iv, b"sk-gcm", None)
    payload = base64.b64encode(iv + ciphertext).decode()

    monkeypatch.setattr(crypto_utils, "get_settings", lambda: type("S", (), {"llm_key_encryption_secret": secret_b64})())

    assert crypto_utils.decrypt_task_api_key(payload) == "sk-gcm"


def test_decrypt_task_api_key_falls_back_to_fernet(monkeypatch):
    monkeypatch.setattr(crypto_utils, "get_settings", lambda: type("S", (), {"llm_key_encryption_secret": "dev-secret"})())
    ciphertext = crypto_utils.encrypt_api_key("sk-fernet")

    assert crypto_utils.decrypt_task_api_key(ciphertext) == "sk-fernet"
