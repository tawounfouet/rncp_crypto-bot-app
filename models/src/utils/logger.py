"""Project logging utilities — thin wrapper over the shared utils.logging package."""

from __future__ import annotations

import logging
from pathlib import Path

from utils.logging.logger import configure_logging as _configure_logging

from src.config.settings import AppSettings

LOGGER_NAME = "cryptobot_models"
DEFAULT_LOG_FILE = "models-training.log"


def setup_logger(
    name: str = LOGGER_NAME,
    log_dir: str | Path = "logs",
    level: str = "INFO",
    json_logs: bool = False,
    file_logging: bool = True,
    log_file: str = DEFAULT_LOG_FILE,
    force: bool = False,
) -> logging.Logger:
    """Configure and return the project logger."""
    return _configure_logging(
        name=name,
        level=level,
        log_dir=log_dir,
        log_file=log_file,
        json_output=json_logs,
        file_logging=file_logging,
        force=force,
    )


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
