from app.config import Config
from app.constants import ErrorMessages
from app.core.exceptions import UnauthorizedError


def verify_admin_password(password: str) -> bool:
    expected = Config.ADMIN_PASSWORD
    if not expected:
        return False
    return password.strip() == expected


def login(password: str) -> dict:
    if not verify_admin_password(password):
        raise UnauthorizedError(ErrorMessages.INVALID_CREDENTIALS)
    return {"id": "admin", "role": "admin"}
