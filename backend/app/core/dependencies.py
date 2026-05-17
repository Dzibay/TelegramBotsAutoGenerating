from typing import Optional

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt

from app.config import Config
from app.constants import ErrorMessages
from app.core.exceptions import UnauthorizedError

security = HTTPBearer(auto_error=False)

ADMIN_USER = {"id": "admin", "role": "admin"}


def _extract_token(request: Request, credentials: Optional[HTTPAuthorizationCredentials]) -> Optional[str]:
    if credentials and credentials.scheme.lower() == "bearer":
        return credentials.credentials
    auth = request.headers.get("Authorization") or request.headers.get("authorization")
    if auth:
        parts = auth.split(maxsplit=1)
        if len(parts) == 2 and parts[0].lower() == "bearer":
            return parts[1]
    return None


async def get_current_user(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
) -> dict:
    token = _extract_token(request, credentials)
    if not token:
        raise UnauthorizedError()

    try:
        payload = jwt.decode(token, Config.JWT_SECRET_KEY, algorithms=[Config.JWT_ALGORITHM])
        if payload.get("sub") != "admin" or payload.get("role") != "admin":
            raise UnauthorizedError()
    except JWTError:
        raise UnauthorizedError(ErrorMessages.INVALID_CREDENTIALS)

    return dict(ADMIN_USER)
