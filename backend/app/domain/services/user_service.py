from typing import Any, Optional

from app.constants import ErrorMessages
from app.core.exceptions import ConflictError, NotFoundError
from app.extensions import bcrypt
from app.infrastructure.database import repository as db


def _public_user(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": str(row["id"]),
        "email": row["email"],
        "name": row.get("name"),
        "created_at": row["created_at"].isoformat() if row.get("created_at") else None,
    }


async def get_user_by_email(email: str) -> Optional[dict[str, Any]]:
    return await db.fetch_one(
        "SELECT id, email, password_hash, name, created_at FROM users WHERE email = $1",
        email.lower(),
    )


async def get_user_by_id(user_id: str) -> Optional[dict[str, Any]]:
    row = await db.fetch_one(
        "SELECT id, email, password_hash, name, created_at FROM users WHERE id = $1::bigint",
        int(user_id),
    )
    return _public_user(row) if row else None


async def create_user(email: str, password: str, name: str | None = None) -> dict[str, Any]:
    existing = await get_user_by_email(email)
    if existing:
        raise ConflictError(ErrorMessages.USER_ALREADY_EXISTS)

    password_hash = bcrypt.hash(password)
    row = await db.fetch_one(
        """
        INSERT INTO users (email, password_hash, name)
        VALUES ($1, $2, $3)
        RETURNING id, email, name, created_at
        """,
        email.lower(),
        password_hash,
        name,
    )
    return _public_user(row)


async def verify_password(email: str, password: str) -> Optional[dict[str, Any]]:
    user = await get_user_by_email(email)
    if not user or not bcrypt.verify(password, user["password_hash"]):
        return None
    return _public_user(user)


async def update_user_name(user_id: str, name: str) -> dict[str, Any]:
    row = await db.fetch_one(
        """
        UPDATE users SET name = $2, updated_at = NOW()
        WHERE id = $1::bigint
        RETURNING id, email, name, created_at
        """,
        int(user_id),
        name,
    )
    if not row:
        raise NotFoundError(ErrorMessages.USER_NOT_FOUND)
    return _public_user(row)
