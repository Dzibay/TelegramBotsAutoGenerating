from datetime import datetime, timezone

from jose import jwt

from app.config import Config


def create_access_token(subject: str = "admin", role: str = "admin") -> str:
    expire = datetime.now(timezone.utc) + Config.JWT_ACCESS_TOKEN_EXPIRES
    payload = {
        "sub": subject,
        "role": role,
        "exp": expire,
    }
    return jwt.encode(payload, Config.JWT_SECRET_KEY, algorithm=Config.JWT_ALGORITHM)
