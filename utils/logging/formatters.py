from __future__ import annotations

import json
import logging
import sys
from datetime import UTC, datetime

_RESET = "\033[0m"
_DIM = "\033[2m"
_LEVEL_COLORS = {
    "DEBUG": "\033[36m",
    "INFO": "\033[32m",
    "WARNING": "\033[33m",
    "ERROR": "\033[31m",
    "CRITICAL": "\033[1;31m",
}


class ColoredFormatter(logging.Formatter):
    """Console formatter with colorized log level badge.

    Auto-detects TTY; falls back to plain format if output is piped.
    """

    def format(self, record: logging.LogRecord) -> str:
        color = _LEVEL_COLORS.get(record.levelname, "")
        record = logging.makeLogRecord(record.__dict__)
        record.levelname = f"{color}{record.levelname:<8}{_RESET}"
        record.asctime = self.formatTime(record, self.datefmt)
        record.name = f"{_DIM}{record.name}{_RESET}"
        return (
            f"{_DIM}{record.asctime}{_RESET}"
            f" {record.levelname}"
            f" {record.name}"
            f" {record.getMessage()}"
        )


class JsonFormatter(logging.Formatter):
    """Format log records as one JSON object per line.

    Structured output suitable for log aggregation (ELK, Datadog, etc.).
    """

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
