"""Меры безопасности Telegram-аккаунта через Telethon."""
from typing import Any

from app.core.logging import get_logger

logger = get_logger(__name__)


async def list_active_sessions(client) -> list[dict[str, Any]]:
    from telethon.tl.functions.account import GetAuthorizationsRequest

    result = await client(GetAuthorizationsRequest())
    sessions = []
    for auth in result.authorizations:
        sessions.append(
            {
                "hash": auth.hash,
                "device": auth.device_model,
                "platform": auth.platform,
                "app": auth.app_name,
                "current": auth.current,
            }
        )
    return sessions


async def terminate_other_sessions(client) -> int:
    """Завершает все сессии кроме текущей. Возвращает число сторонних сессий до сброса."""
    sessions = await list_active_sessions(client)
    others = [s for s in sessions if not s.get("current")]
    from telethon.tl.functions.auth import ResetAuthorizationsRequest

    await client(ResetAuthorizationsRequest())
    return len(others)


async def change_cloud_password(
    client,
    new_password: str,
    current_password: str | None = None,
    hint: str = "",
) -> None:
    """Смена облачного пароля (2FA). Если 2FA не было — current_password можно не указывать."""
    await client.edit_2fa(
        current_password=current_password or None,
        new_password=new_password,
        hint=hint or "security",
    )


async def apply_privacy_restrictions(client) -> list[str]:
    """Ограничивает видимость номера, статуса, приглашений."""
    from telethon.tl.functions.account import SetPrivacyRequest
    from telethon.tl.types import (
        InputPrivacyKeyAddedByPhone,
        InputPrivacyKeyChatInvite,
        InputPrivacyKeyPhoneNumber,
        InputPrivacyKeyStatusTimestamp,
        InputPrivacyValueDisallowAll,
    )

    done = []
    disallow = InputPrivacyValueDisallowAll()
    keys = [
        (InputPrivacyKeyPhoneNumber(), "phone"),
        (InputPrivacyKeyStatusTimestamp(), "last_seen"),
        (InputPrivacyKeyChatInvite(), "invites"),
        (InputPrivacyKeyAddedByPhone(), "added_by_phone"),
    ]
    for key, name in keys:
        try:
            await client(SetPrivacyRequest(key=key, rules=[disallow]))
            done.append(name)
        except Exception as exc:
            logger.warning("Privacy %s failed: %s", name, exc)
    return done


async def run_security_steps(
    client,
    options: dict[str, Any],
    *,
    new_password: str | None = None,
    current_password: str | None = None,
    password_hint: str = "",
) -> list[str]:
    """Выполняет выбранные шаги. Возвращает список выполненных действий."""
    completed: list[str] = []

    if options.get("terminate_sessions", True):
        count = await terminate_other_sessions(client)
        completed.append(f"terminate_sessions:{count}")

    if options.get("change_password") and new_password:
        await change_cloud_password(client, new_password, current_password, password_hint)
        completed.append("change_password")

    if options.get("privacy_restrictions", True):
        priv = await apply_privacy_restrictions(client)
        completed.append(f"privacy:{','.join(priv)}")

    return completed
