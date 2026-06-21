"""
Единый процесс обслуживания активных ботов (aiogram) с периодической синхронизацией БД.

Запуск: python -m app.bot_runner.main
"""
import asyncio
import sys
import time

from dotenv import load_dotenv

load_dotenv()

from app.config import Config
from app.core.logging import get_logger, init_logging
from app.infrastructure.database.pool import close_pool, init_pool

init_logging()
logger = get_logger(__name__)

# Пауза после stop_polling — Telegram освобождает getUpdates не мгновенно
POLLING_STOP_GRACE_SEC = 1.5
RESTART_COOLDOWN_SEC = 3.0


async def _load_active_bots() -> list[dict]:
    from app.domain.services import bot_promo_service
    from app.infrastructure.database import repository as db
    from app.utils.crypto import decrypt_token

    rows = await db.fetch_all(
        """
        SELECT id, token_encrypted, welcome_message, username,
               target_url, link_mode, redirect_slug,
               welcome_button_enabled, welcome_button_text
        FROM bots
        WHERE status = 'active' AND token_encrypted IS NOT NULL
        """
    )
    bots = []
    for row in rows:
        try:
            token = decrypt_token(bytes(row["token_encrypted"]))
            link_mode = bot_promo_service.normalize_link_mode(row.get("link_mode"))
            target = row.get("target_url") or ""
            slug = row.get("redirect_slug")
            public_link = bot_promo_service.resolve_public_link(link_mode, target, slug)
            bots.append(
                {
                    "id": row["id"],
                    "token": token,
                    "welcome_message": row["welcome_message"],
                    "username": row.get("username"),
                    "public_link": public_link,
                    "welcome_button_enabled": bool(row.get("welcome_button_enabled", True)),
                    "welcome_button_text": bot_promo_service.welcome_button_label(
                        row.get("welcome_button_text")
                    ),
                }
            )
        except Exception as exc:
            logger.warning("Skip bot id=%s: %s", row["id"], exc)
    return bots


def _welcome_reply_markup(bot_info: dict):
    from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

    from app.domain.services import bot_promo_service

    if not bot_info.get("welcome_button_enabled"):
        return None
    url = (bot_info.get("public_link") or "").strip()
    if not url.startswith(("http://", "https://")):
        return None
    label = bot_info.get("welcome_button_text") or bot_promo_service.WELCOME_BUTTON_TEXT_DEFAULT
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=label[:64], url=url)],
        ]
    )


async def _send_welcome(message, bot_info: dict) -> None:
    from app.domain.services import bot_promo_service

    markup = _welcome_reply_markup(bot_info)
    text = bot_promo_service.apply_link_placeholder(
        bot_info["welcome_message"],
        bot_info["public_link"],
    )
    await message.answer(text, reply_markup=markup)


async def _graceful_stop_polling(dp, poll_task: asyncio.Task) -> None:
    try:
        await dp.stop_polling()
    except Exception as exc:
        logger.debug("stop_polling: %s", exc)
    poll_task.cancel()
    try:
        await poll_task
    except asyncio.CancelledError:
        pass
    await asyncio.sleep(POLLING_STOP_GRACE_SEC)


async def run_bot_polling(bot_info: dict, stop_event: asyncio.Event) -> None:
    from aiogram import Bot, Dispatcher
    from aiogram.filters import CommandStart
    from aiogram.types import Message

    bot = Bot(token=bot_info["token"])
    dp = Dispatcher()

    @dp.message(CommandStart())
    async def on_start(message: Message) -> None:
        await _send_welcome(message, bot_info)

    @dp.message()
    async def on_any(message: Message) -> None:
        await _send_welcome(message, bot_info)

    logger.info("Polling bot id=%s @%s", bot_info["id"], bot_info.get("username"))
    try:
        await bot.delete_webhook(drop_pending_updates=False)
        poll_task = asyncio.create_task(dp.start_polling(bot, handle_signals=False))
        stop_wait = asyncio.create_task(stop_event.wait())
        done, pending = await asyncio.wait(
            {poll_task, stop_wait},
            return_when=asyncio.FIRST_COMPLETED,
        )
        if stop_wait in done:
            await _graceful_stop_polling(dp, poll_task)
        else:
            for t in pending:
                t.cancel()
            if poll_task in done and not poll_task.cancelled():
                exc = poll_task.exception()
                if exc:
                    raise exc
    except Exception:
        logger.exception("Polling failed bot id=%s @%s", bot_info["id"], bot_info.get("username"))
        raise
    finally:
        try:
            await dp.stop_polling()
        except Exception:
            pass
        await bot.session.close()
    logger.info("Stopped polling bot id=%s", bot_info["id"])


def _bot_runtime_key(bot: dict) -> tuple:
    return (
        bot.get("token"),
        bot.get("welcome_message"),
        bot.get("public_link"),
        bot.get("welcome_button_enabled"),
        bot.get("welcome_button_text"),
    )


class BotRunnerManager:
    def __init__(self) -> None:
        self._tasks: dict[int, asyncio.Task] = {}
        self._stops: dict[int, asyncio.Event] = {}
        self._runtime: dict[int, tuple] = {}
        self._context: dict[int, dict] = {}
        self._restart_after: dict[int, float] = {}
        self._start_stagger_sec = 0.05

    def _cleanup_bot(self, bid: int) -> None:
        self._tasks.pop(bid, None)
        self._stops.pop(bid, None)
        self._runtime.pop(bid, None)
        self._context.pop(bid, None)

    async def _stop_bot(self, bid: int) -> None:
        if bid not in self._tasks:
            return
        task = self._tasks[bid]
        if not task.done():
            self._stops[bid].set()
            try:
                await asyncio.wait_for(task, timeout=15.0)
            except (asyncio.TimeoutError, asyncio.CancelledError):
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
        elif not task.cancelled():
            exc = task.exception()
            if exc:
                logger.warning("Polling stopped bot id=%s: %s", bid, exc)
        self._restart_after[bid] = time.monotonic() + RESTART_COOLDOWN_SEC
        self._cleanup_bot(bid)

    def _hot_reload_bot(self, bot: dict) -> None:
        """Обновить тексты/ссылки без перезапуска getUpdates (избегает TelegramConflictError)."""
        bid = bot["id"]
        ctx = self._context.get(bid)
        if ctx is not None:
            ctx.clear()
            ctx.update(bot)
        self._runtime[bid] = _bot_runtime_key(bot)
        logger.info("Hot-reload bot id=%s @%s", bid, bot.get("username"))

    def _start_bot(self, bot: dict) -> None:
        bid = bot["id"]
        ctx = dict(bot)
        stop_event = asyncio.Event()
        self._stops[bid] = stop_event
        self._context[bid] = ctx
        self._runtime[bid] = _bot_runtime_key(bot)
        self._restart_after.pop(bid, None)
        self._tasks[bid] = asyncio.create_task(
            run_bot_polling(ctx, stop_event),
            name=f"bot-{bid}",
        )

    def _can_restart(self, bid: int) -> bool:
        return time.monotonic() >= self._restart_after.get(bid, 0)

    async def sync(self) -> None:
        active = await _load_active_bots()
        active_ids = {b["id"] for b in active}
        active_map = {b["id"]: b for b in active}

        for bid in list(self._tasks):
            task = self._tasks[bid]
            if bid not in active_ids:
                await self._stop_bot(bid)
            elif task.done():
                await self._stop_bot(bid)
            elif self._runtime.get(bid) != _bot_runtime_key(active_map[bid]):
                old_key = self._runtime.get(bid)
                new_key = _bot_runtime_key(active_map[bid])
                if old_key and old_key[0] == new_key[0]:
                    self._hot_reload_bot(active_map[bid])
                else:
                    await self._stop_bot(bid)

        started = 0
        for bot in active:
            bid = bot["id"]
            if bid in self._tasks:
                continue
            if not self._can_restart(bid):
                continue
            if started:
                await asyncio.sleep(self._start_stagger_sec)
            self._start_bot(bot)
            started += 1

        if started:
            logger.info("Started polling for %s bot(s), total active=%s", started, len(self._tasks))

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
    from app.infrastructure.database.schema_patches import apply_startup_schema_patches
    from app.infrastructure.cache.redis_client import close_redis, get_redis, init_redis
    from app.domain.services import maintenance_service

    await apply_startup_schema_patches()
    await init_redis(Config.REDIS_URL)
    manager = BotRunnerManager()
    stop = asyncio.Event()

    async def _reload_listener() -> None:
        redis = get_redis()
        if not redis:
            return
        pubsub = redis.pubsub()
        await pubsub.subscribe(Config.REDIS_BOT_RUNNER_RELOAD_CHANNEL)
        try:
            while not stop.is_set():
                msg = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
                if msg and msg.get("type") == "message":
                    logger.info("Bot runner reload signal: %s", msg.get("data"))
                    try:
                        await manager.sync()
                    except Exception as exc:
                        logger.exception("Instant sync failed: %s", exc)
        finally:
            try:
                await pubsub.unsubscribe(Config.REDIS_BOT_RUNNER_RELOAD_CHANNEL)
                await pubsub.close()
            except Exception:
                pass

    async def _maintenance_loop() -> None:
        while not stop.is_set():
            try:
                await maintenance_service.run_maintenance_cycle()
            except Exception as exc:
                logger.exception("Maintenance failed: %s", exc)
            try:
                await asyncio.wait_for(stop.wait(), timeout=120)
            except asyncio.TimeoutError:
                pass

    listener_task = asyncio.create_task(_reload_listener())
    maint_task = asyncio.create_task(_maintenance_loop())
    logger.info("Bot runner started (reload every %ss)", Config.BOT_RUNNER_RELOAD_INTERVAL_SEC)
    try:
        await manager.run_forever()
    finally:
        stop.set()
        listener_task.cancel()
        maint_task.cancel()
        await asyncio.gather(listener_task, maint_task, return_exceptions=True)
        await close_pool()
        await close_redis()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        sys.exit(0)
