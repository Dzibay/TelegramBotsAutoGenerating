"""Паузы между обращениями к BotFather — снижает throttle и блокировку аккаунта."""
import asyncio

from app.core.logging import get_logger
from app.domain.services import settings_service

logger = get_logger(__name__)


def _pacing():
    return settings_service.get_botfather_pacing()


async def pace_botfather_op() -> None:
    """Пауза между последовательными командами BotFather для одного бота."""
    delay = _pacing().op_delay_sec
    if delay > 0:
        await asyncio.sleep(delay)


async def pace_before_conversation() -> None:
    """Короткая пауза перед новым диалогом с BotFather."""
    delay = _pacing().conv_delay_sec
    if delay > 0:
        await asyncio.sleep(delay)


def inter_bot_delay_sec() -> int:
    return _pacing().inter_bot_delay_sec


def batch_cooldown_sec() -> int:
    return _pacing().batch_cooldown_sec


def batch_size() -> int:
    return _pacing().batch_size


def post_throttle_delay_sec() -> int:
    return _pacing().post_throttle_delay_sec


def throttle_pause_total_sec(wait_seconds: int = 0) -> int:
    """Суммарная пауза на аккаунт после throttle/timeout: ожидание Telegram + post_throttle."""
    wait = max(0, int(wait_seconds))
    return wait + post_throttle_delay_sec()


def max_server_flood_wait_sec() -> int:
    return _pacing().max_server_flood_wait
