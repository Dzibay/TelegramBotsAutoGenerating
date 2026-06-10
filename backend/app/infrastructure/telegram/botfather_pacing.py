"""Паузы между обращениями к BotFather — снижает throttle и блокировку аккаунта."""
import asyncio

from app.config import Config
from app.core.logging import get_logger

logger = get_logger(__name__)


async def pace_botfather_op() -> None:
    """Пауза между последовательными командами BotFather для одного бота."""
    delay = Config.BOTFATHER_OP_DELAY_SEC
    if delay > 0:
        await asyncio.sleep(delay)


async def pace_before_conversation() -> None:
    """Короткая пауза перед новым диалогом с BotFather."""
    delay = Config.BOTFATHER_CONV_DELAY_SEC
    if delay > 0:
        await asyncio.sleep(delay)


def inter_bot_delay_sec() -> int:
    return Config.BOTFATHER_INTER_BOT_DELAY_SEC


def batch_cooldown_sec() -> int:
    return Config.BOTFATHER_BATCH_COOLDOWN_SEC


def batch_size() -> int:
    return Config.BOTFATHER_BATCH_SIZE


def post_throttle_delay_sec() -> int:
    return Config.BOTFATHER_POST_THROTTLE_DELAY_SEC
