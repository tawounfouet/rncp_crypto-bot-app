from __future__ import annotations

import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

from utils.logging.formatters import ColoredFormatter, JsonFormatter

LOGGER_NAME = "cryptobot"


def configure_logging(
    name: str = LOGGER_NAME,
    level: str = "INFO",
    *,
    log_dir: str | Path = "logs",
    log_file: str | None = None,
    json_output: bool = False,
    file_logging: bool = True,
    max_bytes: int = 10 * 1024 * 1024,
    backup_count: int = 5,
    force: bool = False,
) -> logging.Logger:
    """Configure and return the project logger.

    Args:
        name: Logger namespace (default: "cryptobot")
        level: Log level string (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_dir: Directory for log files
        log_file: Log filename (defaults to f"{name}.log")
        json_output: Use JSON format for file handler
        file_logging: Enable file logging (rotating)
        max_bytes: Max size per log file before rotation
        backup_count: Number of rotated log files to keep
        force: Reconfigure even if handlers already exist

    Returns:
        Configured logger instance
    """
    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, level.upper(), logging.INFO))
    logger.propagate = False

    if logger.handlers:
        if not force:
            return logger
        for handler in list(logger.handlers):
            logger.removeHandler(handler)
            handler.close()

    _add_console_handler(logger, level)

    if file_logging:
        _add_file_handler(logger, level, Path(log_dir), log_file or f"{name}.log", json_output, max_bytes, backup_count)

    return logger


def _add_console_handler(logger: logging.Logger, level: str) -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(logger.level)
    if sys.stdout.isatty():
        handler.setFormatter(ColoredFormatter(datefmt="%Y-%m-%d %H:%M:%S"))
    else:
        fmt = "%(asctime)s - %(levelname)s - %(name)s - %(message)s"
        handler.setFormatter(logging.Formatter(fmt, datefmt="%Y-%m-%d %H:%M:%S"))
    logger.addHandler(handler)


def _add_file_handler(
    logger: logging.Logger,
    level: str,
    log_dir: Path,
    log_file: str,
    json_output: bool,
    max_bytes: int,
    backup_count: int,
) -> None:
    log_dir.mkdir(parents=True, exist_ok=True)
    handler = RotatingFileHandler(
        log_dir / log_file,
        maxBytes=max_bytes,
        backupCount=backup_count,
        encoding="utf-8",
    )
    handler.setLevel(logger.level)
    if json_output:
        handler.setFormatter(JsonFormatter())
    else:
        fmt = "%(asctime)s - %(levelname)s - %(name)s - %(funcName)s:%(lineno)d - %(message)s"
        handler.setFormatter(logging.Formatter(fmt, datefmt="%Y-%m-%d %H:%M:%S"))
    logger.addHandler(handler)


def get_logger(name: str | None = None, root: str = LOGGER_NAME) -> logging.Logger:
    """Return a child logger configured for the project.

    Auto-initialises the root logger on first call if no handlers exist.

    Args:
        name: Child logger name (e.g. "connectors.minio" → "cryptobot.connectors.minio")
        root: Root logger namespace (default: "cryptobot")

    Returns:
        Logger instance
    """
    root_logger = logging.getLogger(root)
    if not root_logger.handlers:
        configure_logging(name=root)
    if name:
        return logging.getLogger(f"{root}.{name}")
    return root_logger


class LoggerMixin:
    """Mixin exposing a class-level child logger.

    Usage:
        class MyClass(LoggerMixin):
            def do_stuff(self):
                self.logger.info("doing stuff")
    """

    @property
    def logger(self) -> logging.Logger:
        return get_logger(self.__class__.__name__)
