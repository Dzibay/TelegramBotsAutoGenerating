"""Загрузка Telethon-клиента из папки tdata (opentele)."""
from pathlib import Path

from app.config import Config
from app.core.logging import get_logger

logger = get_logger(__name__)


def find_tdata_folder(extracted_root: Path) -> Path:
    direct = extracted_root / "tdata"
    if direct.is_dir():
        return direct
    for candidate in extracted_root.rglob("tdata"):
        if candidate.is_dir():
            return candidate
    raise FileNotFoundError(f"Папка tdata не найдена в {extracted_root}")


async def load_client_from_tdata(tdata_path: Path):
    if not Config.TELEGRAM_API_ID or not Config.TELEGRAM_API_HASH:
        raise RuntimeError(
            "Задайте TELEGRAM_API_ID и TELEGRAM_API_HASH в .env (my.telegram.org)"
        )

    try:
        from opentele.api import API, UseCurrentSession
        from opentele.td import TDesktop
    except ImportError as exc:
        hint = str(exc).strip() or "pip install opentele telethon"
        if "libgthread" in hint or "PyQt5" in hint:
            raise RuntimeError(
                "opentele не загрузился (PyQt5): в Docker пересоберите образ "
                "(libglib2.0-0). Локально: pip install opentele telethon PyQt5"
            ) from exc
        raise RuntimeError(
            f"Установите opentele и telethon: pip install opentele telethon ({hint})"
        ) from exc

    from telethon import TelegramClient

    folder = find_tdata_folder(Path(tdata_path))

    tdesk = TDesktop(str(folder))
    if not tdesk.isLoaded():
        raise ValueError(f"Не удалось загрузить tdata из {folder}")

    api = API.TelegramDesktop.Generate()
    # session=None → telethon использует in-memory SQLiteSession (':memory:').
    # Auth-key всё равно берётся из tdata (UseCurrentSession), а на диск ничего
    # не пишется — поэтому нет общих .session файлов и cross-process "database is locked".
    client = await tdesk.ToTelethon(
        session=None,
        flag=UseCurrentSession,
        api=api,
    )
    await client.connect()
    if not await client.is_user_authorized():
        await client.disconnect()
        raise ValueError("Сессия tdata не авторизована")

    me = await client.get_me()
    logger.info("Telethon connected as %s", getattr(me, "username", me.id))
    return client, me
