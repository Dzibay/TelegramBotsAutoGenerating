"""Настройки приложения (JSON в storage). Env-переменные — дефолты при первом запуске."""
import json
import threading
from pathlib import Path
from typing import Any

from app.config import Config
from app.domain.models.settings_models import BotfatherPacingSettings

_SETTINGS_FILE = Config.STORAGE_ROOT / "app_settings.json"
_LOCK = threading.Lock()


def _defaults_from_config() -> dict[str, int]:
    return {
        "inter_bot_delay_sec": Config.BOTFATHER_INTER_BOT_DELAY_SEC,
        "op_delay_sec": Config.BOTFATHER_OP_DELAY_SEC,
        "conv_delay_sec": Config.BOTFATHER_CONV_DELAY_SEC,
        "batch_size": Config.BOTFATHER_BATCH_SIZE,
        "batch_cooldown_sec": Config.BOTFATHER_BATCH_COOLDOWN_SEC,
        "post_throttle_delay_sec": Config.BOTFATHER_POST_THROTTLE_DELAY_SEC,
        "max_server_flood_wait": Config.BOTFATHER_MAX_SERVER_FLOOD_WAIT,
    }


def _read_raw() -> dict[str, Any]:
    if not _SETTINGS_FILE.exists():
        return {}
    try:
        data = json.loads(_SETTINGS_FILE.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def _write_raw(data: dict[str, Any]) -> None:
    _SETTINGS_FILE.parent.mkdir(parents=True, exist_ok=True)
    tmp = _SETTINGS_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(_SETTINGS_FILE)


def get_botfather_pacing() -> BotfatherPacingSettings:
    """Текущие паузы BotFather: сохранённые в UI или дефолты из env."""
    defaults = _defaults_from_config()
    with _LOCK:
        saved = _read_raw().get("botfather_pacing") or {}
    merged = {**defaults, **{k: v for k, v in saved.items() if k in defaults}}
    return BotfatherPacingSettings.model_validate(merged)


def update_botfather_pacing(body: BotfatherPacingSettings) -> BotfatherPacingSettings:
    with _LOCK:
        raw = _read_raw()
        raw["botfather_pacing"] = body.model_dump()
        _write_raw(raw)
    return body
