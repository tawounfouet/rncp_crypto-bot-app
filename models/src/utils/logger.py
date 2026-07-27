"""Project logging utilities."""

from __future__ import annotations

import json
import logging
import sys
from datetime import UTC, datetime
from logging.handlers import RotatingFileHandler
from pathlib import Path

from src.config.settings import AppSettings


LOGGER_NAME = "cryptobot_models"

_RESET = "\033[0m"
_DIM = "\033[2m"
_LEVEL_COLORS = {
    "DEBUG": "\033[36m",  # cyan
    "INFO": "\033[32m",  # green
    "WARNING": "\033[33m",  # yellow
    "ERROR": "\033[31m",  # red
    "CRITICAL": "\033[1;31m",  # bold red
}


class ColoredFormatter(logging.Formatter):
    """Console formatter that colorizes the log level badge."""

    def format(self, record: logging.LogRecord) -> str:
        color = _LEVEL_COLORS.get(record.levelname, "")
        record = logging.makeLogRecord(record.__dict__)
        record.levelname = f"{color}{record.levelname:<8}{_RESET}"
        record.asctime = self.formatTime(record, self.datefmt)
        record.name = f"{_DIM}{record.name}{_RESET}"
        return f"{_DIM}{record.asctime}{_RESET} {record.levelname} {record.name} {record.getMessage()}"


class JsonFormatter(logging.Formatter):
    """Format log records as one JSON object per line."""

    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": datetime.fromtimestamp(record.created, tz=UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str)


def setup_logger(
    name: str = LOGGER_NAME,
    log_dir: str | Path = "logs",
    level: str = "INFO",
    json_logs: bool = False,
    file_logging: bool = True,
    log_file: str = "models-training.log",
    force: bool = False,
) -> logging.Logger:
    """Configure and return the project logger."""
    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, level.upper(), logging.INFO))
    logger.propagate = False

    if logger.handlers:
        if not force:
            return logger
        for handler in list(logger.handlers):
            logger.removeHandler(handler)
            handler.close()

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logger.level)
    use_colors = sys.stdout.isatty()
    if use_colors:
        console_handler.setFormatter(ColoredFormatter(datefmt="%Y-%m-%d %H:%M:%S"))
    else:
        console_format = "%(asctime)s - %(levelname)s - %(name)s - %(message)s"
        console_handler.setFormatter(logging.Formatter(console_format, datefmt="%Y-%m-%d %H:%M:%S"))
    logger.addHandler(console_handler)

    if file_logging:
        log_path = Path(log_dir)
        log_path.mkdir(parents=True, exist_ok=True)
        file_handler = RotatingFileHandler(
            log_path / log_file,
            maxBytes=10 * 1024 * 1024,
            backupCount=5,
            encoding="utf-8",
        )
        file_handler.setLevel(logger.level)
        if json_logs:
            file_handler.setFormatter(JsonFormatter())
        else:
            file_format = "%(asctime)s - %(levelname)s - %(name)s - %(funcName)s:%(lineno)d - %(message)s"
            file_handler.setFormatter(logging.Formatter(file_format, datefmt="%Y-%m-%d %H:%M:%S"))
        logger.addHandler(file_handler)

    return logger


def configure_logging(settings: AppSettings) -> logging.Logger:
    """Configure logging from application settings."""
    return setup_logger(
        log_dir=settings.logging.log_dir,
        level=settings.logging.level,
        json_logs=settings.logging.json_logs,
        file_logging=settings.logging.file_logging,
        force=True,
    )


def get_logger(name: str | None = None) -> logging.Logger:
    """Return a child logger configured for the project."""
    root_logger = logging.getLogger(LOGGER_NAME)
    if not root_logger.handlers:
        setup_logger()
    if name:
        return logging.getLogger(f"{LOGGER_NAME}.{name}")
    return root_logger


class LoggerMixin:
    """Mixin exposing a class-level child logger."""

    @property
    def logger(self) -> logging.Logger:
        return get_logger(self.__class__.__name__)


def log_training_epoch(model_name: str, epoch: int, train_loss: float, validation_loss: float | None = None) -> None:
    """Log one training epoch."""
    message = f"{model_name} epoch={epoch} train_loss={train_loss:.6f}"
    if validation_loss is not None:
        message += f" validation_loss={validation_loss:.6f}"
    get_logger("training").info(message)


def log_model_save(model_name: str, path: str | Path) -> None:
    """Log a saved model artifact."""
    get_logger("artifacts").info("%s saved to %s", model_name, path)


def log_error(error: Exception, context: str = "") -> None:
    """Log an exception with optional context."""
    prefix = f"{context}: " if context else ""
    get_logger("errors").error("%s%s: %s", prefix, type(error).__name__, error, exc_info=True)
