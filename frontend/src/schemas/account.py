"""Schemas compte utilisateur."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class AccountProfile(BaseModel):
    first_name: str
    last_name: Optional[str] = None
    email: str


class BinanceCredentialInput(BaseModel):
    api_key: str
    api_secret: str
    password_confirmation: str


class BinanceCredentialStatus(BaseModel):
    configured: bool
    updated_at: Optional[datetime] = None
    api_key_masked: str = ""
    api_secret_masked: str = ""
