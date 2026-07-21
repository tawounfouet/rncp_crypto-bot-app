"""Schemas page admin."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel
from schemas.common import UserRole, UserStatus


class AdminUserRow(BaseModel):
    email: str
    role: UserRole
    status: UserStatus
    last_login: datetime | None = None
    first_name: str
    last_name: str | None = None
    exchange_configured: bool = False


class AdminUserDetail(AdminUserRow):
    created_at: datetime
    exchange_configured: bool
    failed_login_count: int
