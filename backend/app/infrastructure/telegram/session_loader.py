"""Загрузка Telethon-клиента из папки tdata (opentele)."""
from pathlib import Path
from sqlite3 import OperationalError

from app.config import Config
from app.core.logging import get_logger

logger = get_logger(__name__)


def cleanup_stale_session_journal(session_path: Path) -> bool:
    """Удалить осиротевший .session-journal рядом с session-файлом.

    SQLite оставляет такой rollback-journal после прерванного входа/краша.
    Если он есть при следующем открытии — получаем "database is locked"
    вместо нормального recovery. Вызывать ДО открытия клиента.
    """
    journal = session_path.with_name(session_path.name + "-journal")
    try:
        if journal.exists():
            journal.unlink()
            logger.warning("Удалён осиротевший %s (прерванный прошлый вход)", journal.name)
            return True
    except OSError as exc:
        logger.warning("Не удалось удалить %s: %s", journal.name, exc)
    return False


def find_tdata_folder(extracted_root: Path) -> Path:
    direct = extracted_root / "tdata"
    if direct.is_dir():
        return direct
    for candidate in extracted_root.rglob("tdata"):
        if candidate.is_dir():
            return candidate
    raise FileNotFoundError(f"Папка tdata не найдена в {extracted_root}")


async def load_client_from_tdata(tdata_path: Path, session_path: Path):
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
    session_path.parent.mkdir(parents=True, exist_ok=True)

    tdesk = TDesktop(str(folder))
    if not tdesk.isLoaded():
        raise ValueError(f"Не удалось загрузить tdata из {folder}")

    api = API.TelegramDesktop.Generate()
    try:
        client = await tdesk.ToTelethon(
            session=str(session_path),
            flag=UseCurrentSession,
            api=api,
        )
    except OperationalError:
        cleanup_stale_session_journal(session_path)
        client = await tdesk.ToTelethon(
            session=str(session_path),
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
