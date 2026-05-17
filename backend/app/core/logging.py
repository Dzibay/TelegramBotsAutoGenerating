import logging
import os
import sys
from typing import Optional

from app.config import Config


_initialized = False


def init_logging(log_level: Optional[str] = None) -> None:
    global _initialized
    if _initialized:
        return

    level_name = (log_level or Config.LOG_LEVEL or "INFO").upper()
    level = getattr(logging, level_name, logging.INFO)

    fmt = "%(asctime)s %(levelname)-5s [%(name)s] %(message)s"
    formatter = logging.Formatter(fmt, datefmt="%Y-%m-%dT%H:%M:%S")

    root = logging.getLogger()
    root.setLevel(level)
    root.handlers.clear()

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)
    root.addHandler(handler)

    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    _initialized = True


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
