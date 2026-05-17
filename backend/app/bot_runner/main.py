"""
Единый процесс обслуживания активных ботов (aiogram) с периодической синхронизацией БД.

Запуск: python -m app.bot_runner.main
"""
import asyncio
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


async def run_bot_polling(bot_info: dict, stop_event: asyncio.Event) -> None:
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
    poll_task = asyncio.create_task(dp.start_polling(bot))
    stop_wait = asyncio.create_task(stop_event.wait())
    done, pending = await asyncio.wait(
        {poll_task, stop_wait},
        return_when=asyncio.FIRST_COMPLETED,
    )
    for t in pending:
        t.cancel()
    if poll_task in done and not poll_task.cancelled():
        exc = poll_task.exception()
        if exc:
            raise exc
    await bot.session.close()
    logger.info("Stopped polling bot id=%s", bot_info["id"])


class BotRunnerManager:
    def __init__(self) -> None:
        self._tasks: dict[int, asyncio.Task] = {}
        self._stops: dict[int, asyncio.Event] = {}

    async def sync(self) -> None:
        active = await _load_active_bots()
        active_ids = {b["id"] for b in active}
        active_map = {b["id"]: b for b in active}

        for bid in list(self._tasks):
            if bid not in active_ids:
                self._stops[bid].set()
                task = self._tasks.pop(bid)
                self._stops.pop(bid, None)
                try:
                    await asyncio.wait_for(task, timeout=10.0)
                except (asyncio.TimeoutError, asyncio.CancelledError):
                    task.cancel()

        for bot in active:
            bid = bot["id"]
            if bid not in self._tasks:
                stop_event = asyncio.Event()
                self._stops[bid] = stop_event
                self._tasks[bid] = asyncio.create_task(
                    run_bot_polling(bot, stop_event),
                    name=f"bot-{bid}",
                )

    async def run_forever(self) -> None:
        while True:
            try:
                await self.sync()
            except Exception as exc:
                logger.exception("Bot sync error: %s", exc)
            await asyncio.sleep(Config.BOT_RUNNER_RELOAD_INTERVAL_SEC)


async def main() -> None:
    Config.validate()
    await init_pool()
    manager = BotRunnerManager()
    logger.info("Bot runner started (reload every %ss)", Config.BOT_RUNNER_RELOAD_INTERVAL_SEC)
    try:
        await manager.run_forever()
    finally:
        await close_pool()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        sys.exit(0)
