"""
Единый процесс обслуживания всех активных ботов (aiogram).

Запуск: python -m app.bot_runner.main
"""
import asyncio
import os
import sys

from dotenv import load_dotenv

load_dotenv()

from app.config import Config
from app.core.logging import get_logger, init_logging
from app.infrastructure.database.pool import close_pool, init_pool

init_logging()
logger = get_logger(__name__)


async def _load_active_bots() -> list[dict]:
    from app.infrastructure.database import repository as db
    from app.utils.crypto import decrypt_token

    rows = await db.fetch_all(
        """
        SELECT id, token_encrypted, welcome_message, username
        FROM bots
        WHERE status = 'active' AND token_encrypted IS NOT NULL
        """
    )
    bots = []
    for row in rows:
        try:
            token = decrypt_token(bytes(row["token_encrypted"]))
            bots.append(
                {
                    "id": row["id"],
                    "token": token,
                    "welcome_message": row["welcome_message"],
                    "username": row.get("username"),
                }
            )
        except Exception as exc:
            logger.warning("Skip bot id=%s: %s", row["id"], exc)
    return bots


async def run_bot_polling(bot_info: dict) -> None:
    """Один бот в общем event loop — aiogram 3."""
    from aiogram import Bot, Dispatcher
    from aiogram.filters import CommandStart
    from aiogram.types import Message

    bot = Bot(token=bot_info["token"])
    dp = Dispatcher()
    welcome = bot_info["welcome_message"]

    @dp.message(CommandStart())
    async def on_start(message: Message) -> None:
        await message.answer(welcome)

    @dp.message()
    async def on_any(message: Message) -> None:
        await message.answer(welcome)

    logger.info("Polling bot id=%s @%s", bot_info["id"], bot_info.get("username"))
    await dp.start_polling(bot)


async def main() -> None:
    Config.validate()
    await init_pool()

    bots = await _load_active_bots()
    if not bots:
        logger.info("Нет активных ботов. Ожидание… (перезапуск после создания)")
        await asyncio.sleep(Config.BOT_RUNNER_RELOAD_INTERVAL_SEC)
        await close_pool()
        return

    logger.info("Запуск polling для %s ботов", len(bots))
    await asyncio.gather(*(run_bot_polling(b) for b in bots))


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        sys.exit(0)
