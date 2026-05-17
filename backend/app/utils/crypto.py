"""Шифрование токенов ботов (Fernet)."""
from typing import Optional

from cryptography.fernet import Fernet, InvalidToken

from app.config import Config


def _fernet() -> Optional[Fernet]:
    key = Config.BOT_TOKEN_ENCRYPTION_KEY.strip()
    if not key:
        return None
    return Fernet(key.encode() if isinstance(key, str) else key)


def encrypt_token(token: str) -> Optional[bytes]:
    f = _fernet()
    if not f:
        return token.encode("utf-8")
    return f.encrypt(token.encode("utf-8"))


def decrypt_token(data: bytes) -> str:
    f = _fernet()
    if not f:
        return data.decode("utf-8")
    try:
        return f.decrypt(data).decode("utf-8")
    except InvalidToken:
        return data.decode("utf-8")
