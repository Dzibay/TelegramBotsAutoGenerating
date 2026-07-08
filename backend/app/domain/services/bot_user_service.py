"""Учёт пользователей, которые пишут в ботов (любое сообщение, включая /start)."""
from typing import Any

from app.core.logging import get_logger
from app.infrastructure.database import repository as db

logger = get_logger(__name__)


async def record_interaction(bot_id: int, user: Any) -> None:
    """Зафиксировать взаимодействие пользователя с ботом (upsert по паре bot_id+user_id)."""
    if user is None:
        return
    try:
        await db.execute(
            """
            INSERT INTO bot_users (bot_id, user_id, username, first_name, last_name, message_count)
            VALUES ($1, $2, $3, $4, $5, 1)
            ON CONFLICT (bot_id, user_id) DO UPDATE SET
                username      = EXCLUDED.username,
                first_name    = EXCLUDED.first_name,
                last_name     = EXCLUDED.last_name,
                message_count = bot_users.message_count + 1,
                last_seen     = NOW()
            """,
            bot_id,
            user.id,
            user.username,
            user.first_name,
            user.last_name,
        )
    except Exception as exc:
        logger.warning("Failed to record bot user bot_id=%s user_id=%s: %s", bot_id, getattr(user, "id", None), exc)