"""Зависимости FastAPI: auth, idempotency."""
from typing import Optional

from fastapi import Depends, Header, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt

from app.config import Config
from app.constants import ErrorMessages
from app.core.exceptions import ConflictError, UnauthorizedError
from app.core.idempotency import IdempotencyContext
from app.domain.services import idempotency_service

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


async def require_idempotency_key(
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key"),
) -> Optional[str]:
    return (idempotency_key or "").strip() or None


async def begin_idempotent_request(
    idempotency_key: Optional[str] = Depends(require_idempotency_key),
) -> IdempotencyContext:
    """Вернуть контекст; replay заполнен если запрос уже выполнен."""
    if not idempotency_key:
        return IdempotencyContext()
    cached = await idempotency_service.get_cached_response(idempotency_key)
    if cached and not cached.get("pending"):
        return IdempotencyContext(key=idempotency_key, replay=cached)
    if cached and cached.get("pending"):
        raise ConflictError("Такой запрос уже выполняется — дождитесь завершения")
    reserved = await idempotency_service.reserve_key(idempotency_key)
    if not reserved:
        raise ConflictError("Такой запрос уже выполняется — дождитесь завершения")
    return IdempotencyContext(key=idempotency_key)
