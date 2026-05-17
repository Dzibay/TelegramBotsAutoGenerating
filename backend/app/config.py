"""Централизованная конфигурация из переменных окружения."""
import os
from datetime import timedelta
from pathlib import Path

from dotenv import load_dotenv

_BACKEND_ROOT = Path(__file__).resolve().parent.parent
_PROJECT_ROOT = _BACKEND_ROOT.parent
load_dotenv(_PROJECT_ROOT / ".env")
load_dotenv(_BACKEND_ROOT / ".env")
load_dotenv()


class Config:
    APP_NAME = os.getenv("APP_NAME", "Telegram Bots Generator")

    # Вход на сайт — один пароль из env
    ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "")

    JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "")
    JWT_ALGORITHM = "HS256"
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(
        days=max(1, int(os.getenv("JWT_ACCESS_TOKEN_EXPIRES_DAYS", "7")))
    )

    DB_HOST = os.getenv("DB_HOST", "localhost")
    DB_PORT = int(os.getenv("DB_PORT", "5432"))
    DB_NAME = os.getenv("DB_NAME", "tg_bots")
    DB_USER = os.getenv("DB_USER", "postgres")
    DB_PASSWORD = os.getenv("DB_PASSWORD", "")

    DB_POOL_MIN = max(1, int(os.getenv("DB_POOL_MIN", "1")))
    DB_POOL_MAX = max(1, int(os.getenv("DB_POOL_MAX", "10")))

    REDIS_URL = os.getenv("REDIS_URL", "")
    REDIS_JOB_QUEUE = os.getenv("REDIS_JOB_QUEUE", "tg_bots:creation_jobs")
    REDIS_PREP_QUEUE = os.getenv("REDIS_PREP_QUEUE", "tg_bots:account_prep_jobs")

    CORS_ORIGINS = [
        o.strip() for o in os.getenv("CORS_ORIGINS", "http://localhost:5173").split(",") if o.strip()
    ]
    CORS_SUPPORTS_CREDENTIALS = True
    CORS_METHODS = ["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"]

    FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:5173")
    BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:5000")
    # Базовый URL для трекинг-ссылок /go/{slug} (обычно = FRONTEND_URL)
    PUBLIC_SITE_URL = os.getenv("PUBLIC_SITE_URL", os.getenv("FRONTEND_URL", "http://localhost:5173")).rstrip("/")
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

    # Хранилище tdata и аватаров
    STORAGE_ROOT = Path(os.getenv("STORAGE_ROOT", str(_PROJECT_ROOT / "storage")))
    TDATA_DIR = STORAGE_ROOT / "tdata"
    PREP_TDATA_DIR = STORAGE_ROOT / "prep_tdata"
    PREPARED_TDATA_DIR = STORAGE_ROOT / "prepared_tdata"
    AVATARS_DIR = STORAGE_ROOT / "avatars"

    # Шифрование токенов ботов (Fernet key, base64)
    BOT_TOKEN_ENCRYPTION_KEY = os.getenv("BOT_TOKEN_ENCRYPTION_KEY", "")

    # Лимит ботов на аккаунт (ориентир Telegram)
    MAX_BOTS_PER_ACCOUNT = max(1, int(os.getenv("MAX_BOTS_PER_ACCOUNT", "20")))

    # AI
    AI_TEXT_PROVIDER = os.getenv("AI_TEXT_PROVIDER", "groq").lower()
    # При ошибке Groq/Ollama использовать шаблоны вместо 500
    AI_FALLBACK_ON_ERROR = os.getenv("AI_FALLBACK_ON_ERROR", "true").lower() in (
        "1",
        "true",
        "yes",
    )
    AI_IMAGE_PROVIDER = os.getenv("AI_IMAGE_PROVIDER", "pollinations").lower()
    GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
    GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
    OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.2")

    # Telegram API (для Telethon / BotFather автоматизации)
    TELEGRAM_API_ID = os.getenv("TELEGRAM_API_ID", "")
    TELEGRAM_API_HASH = os.getenv("TELEGRAM_API_HASH", "")

    # Bot runner
    BOT_RUNNER_RELOAD_INTERVAL_SEC = max(10, int(os.getenv("BOT_RUNNER_RELOAD_INTERVAL_SEC", "60")))

    @staticmethod
    def validate() -> None:
        missing = []
        if not Config.ADMIN_PASSWORD:
            missing.append("ADMIN_PASSWORD")
        if not Config.JWT_SECRET_KEY:
            missing.append("JWT_SECRET_KEY")
        if not Config.DB_NAME:
            missing.append("DB_NAME")
        if not Config.DB_USER:
            missing.append("DB_USER")
        if missing:
            raise ValueError(f"Отсутствуют обязательные переменные: {', '.join(missing)}")

        Config.TDATA_DIR.mkdir(parents=True, exist_ok=True)
        Config.PREP_TDATA_DIR.mkdir(parents=True, exist_ok=True)
        Config.PREPARED_TDATA_DIR.mkdir(parents=True, exist_ok=True)
        Config.AVATARS_DIR.mkdir(parents=True, exist_ok=True)
