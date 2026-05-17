from app.config import Config
from app.core.exceptions import UnauthorizedError


def verify_admin_password(password: str) -> bool:
    return bool(Config.ADMIN_PASSWORD) and password == Config.ADMIN_PASSWORD


def login(password: str) -> dict:
    if not verify_admin_password(password):
        raise UnauthorizedError()
    return {"id": "admin", "role": "admin"}
