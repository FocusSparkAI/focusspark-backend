import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

from app.core.config import (
    LOG_BACKUP_COUNT,
    LOG_FILE,
    LOG_LEVEL,
    LOG_MAX_BYTES,
    LOG_TO_FILE,
)


def configure_logging():
    level = getattr(logging, LOG_LEVEL, logging.INFO)
    formatter = logging.Formatter(
        "%(asctime)s %(levelname)s [%(name)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    root_logger = logging.getLogger()
    root_logger.setLevel(level)
    root_logger.handlers.clear()

    console_handler = logging.StreamHandler()
    console_handler.setLevel(level)
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)

    if LOG_TO_FILE:
        log_path = Path(LOG_FILE)
        log_path.parent.mkdir(parents=True, exist_ok=True)

        file_handler = RotatingFileHandler(
            log_path,
            maxBytes=LOG_MAX_BYTES,
            backupCount=LOG_BACKUP_COUNT,
            encoding="utf-8",
        )
        file_handler.setLevel(level)
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)

    logging.getLogger("focusspark").setLevel(level)
