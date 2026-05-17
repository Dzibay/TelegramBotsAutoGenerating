from typing import Any

from app.constants import ErrorMessages
from app.core.exceptions import NotFoundError
from app.infrastructure.database import repository as db


def _serialize(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": row["id"],
        "user_id": str(row["user_id"]),
        "title": row["title"],
        "description": row.get("description"),
        "created_at": row["created_at"].isoformat() if row.get("created_at") else None,
        "updated_at": row["updated_at"].isoformat() if row.get("updated_at") else None,
    }


async def list_items(user_id: str) -> list[dict[str, Any]]:
    rows = await db.fetch_all(
        """
        SELECT id, user_id, title, description, created_at, updated_at
        FROM items
        WHERE user_id = $1::bigint
        ORDER BY created_at DESC
        """,
        int(user_id),
    )
    return [_serialize(r) for r in rows]


async def get_item(user_id: str, item_id: int) -> dict[str, Any]:
    row = await db.fetch_one(
        """
        SELECT id, user_id, title, description, created_at, updated_at
        FROM items WHERE id = $1 AND user_id = $2::bigint
        """,
        item_id,
        int(user_id),
    )
    if not row:
        raise NotFoundError(ErrorMessages.ITEM_NOT_FOUND)
    return _serialize(row)


async def create_item(user_id: str, title: str, description: str | None) -> dict[str, Any]:
    row = await db.fetch_one(
        """
        INSERT INTO items (user_id, title, description)
        VALUES ($1::bigint, $2, $3)
        RETURNING id, user_id, title, description, created_at, updated_at
        """,
        int(user_id),
        title,
        description,
    )
    return _serialize(row)


async def update_item(
    user_id: str,
    item_id: int,
    title: str | None,
    description: str | None,
) -> dict[str, Any]:
    current = await get_item(user_id, item_id)
    new_title = title if title is not None else current["title"]
    new_desc = description if description is not None else current["description"]

    row = await db.fetch_one(
        """
        UPDATE items
        SET title = $3, description = $4, updated_at = NOW()
        WHERE id = $1 AND user_id = $2::bigint
        RETURNING id, user_id, title, description, created_at, updated_at
        """,
        item_id,
        int(user_id),
        new_title,
        new_desc,
    )
    if not row:
        raise NotFoundError(ErrorMessages.ITEM_NOT_FOUND)
    return _serialize(row)


async def delete_item(user_id: str, item_id: int) -> None:
    result = await db.execute(
        "DELETE FROM items WHERE id = $1 AND user_id = $2::bigint",
        item_id,
        int(user_id),
    )
    if result == "DELETE 0":
        raise NotFoundError(ErrorMessages.ITEM_NOT_FOUND)
