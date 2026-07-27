"""Schemas compte utilisateur."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class AccountProfile(BaseModel):
    first_name: str
    last_name: str | None = None
    email: str


class ExchangeCredentialInput(BaseModel):
    exchange: str
    api_key: str
    api_secret: str
    mode: str = "live"


class ExchangeCredentialStatus(BaseModel):
    exchange: str
    configured: bool
    live_configured: bool = False
    sandbox_configured: bool = False
    active_mode: str = "live"
    supports_sandbox: bool = False
    updated_at: datetime | None = None
    api_key_masked: str = ""
    api_secret_masked: str = ""
