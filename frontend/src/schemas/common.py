"""Schemas communs pour le frontend."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import Enum

from pydantic import BaseModel, Field


class UserRole(str, Enum):
    USER = "USER"
    ADMIN = "ADMIN"


class UserStatus(str, Enum):
    ENABLED = "ENABLED"
    DISABLED = "DISABLED"
    PENDING = "PENDING"


class ServiceHealth(str, Enum):
    OK = "OK"
    WARNING = "WARNING"
    ERROR = "ERROR"


class BotRuntimeStatus(str, Enum):
    RUNNING = "RUNNING"
    STOPPED = "STOPPED"
    PAUSED = "PAUSED"
    ERROR = "ERROR"
    STARTING = "STARTING"
    STOPPING = "STOPPING"


class UiMessage(BaseModel):
    kind: str = Field(default="info")
    text: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
