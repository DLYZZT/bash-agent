from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import Optional
from logging.handlers import RotatingFileHandler


class StructuredLogger:

    _instances: dict[str, logging.Logger] = {}

    @classmethod
    def setup(
        cls,
        log_file: Path,
        level: int = logging.INFO,
        max_bytes: int = 10 * 1024 * 1024,  # 10MB
        backup_count: int = 5,
    ) -> None:
        log_file.parent.mkdir(parents=True, exist_ok=True)

        detailed_formatter = logging.Formatter(
            fmt='%(asctime)s | %(levelname)-8s | %(name)-20s | %(funcName)-15s | %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )

        file_handler = RotatingFileHandler(
            log_file,
            maxBytes=max_bytes,
            backupCount=backup_count,
            encoding='utf-8',
        )
        file_handler.setLevel(level)
        file_handler.setFormatter(detailed_formatter)

        root_logger = logging.getLogger()
        root_logger.setLevel(level)

        root_logger.handlers.clear()

        root_logger.addHandler(file_handler)

        # 禁用第三方库的调试日志，避免干扰
        logging.getLogger("httpx").setLevel(logging.WARNING)
        logging.getLogger("httpcore").setLevel(logging.WARNING)
        logging.getLogger("openai").setLevel(logging.WARNING)
        logging.getLogger("urllib3").setLevel(logging.WARNING)

    @classmethod
    def get_logger(cls, name: str) -> logging.Logger:
        if name not in cls._instances:
            cls._instances[name] = logging.getLogger(name)
        return cls._instances[name]


def get_logger(name: str) -> logging.Logger:
    return StructuredLogger.get_logger(name)
