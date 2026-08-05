"""Schemas compte utilisateur."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class AccountProfile(BaseModel):
    first_name: str
    last_name: str | None = None
    email: str


class BinanceCredentialInput(BaseModel):
    api_key: str
    api_secret: str


class BinanceCredentialStatus(BaseModel):
    configured: bool
    updated_at: datetime | None = None
    api_key_masked: str = ""
    api_secret_masked: str = ""


class ApiCredentialInput(BaseModel):
    label: str
    exchange: str = "binance"
    api_key: str
    api_secret: str


class ApiCredentialEntry(BaseModel):
    id: str
    exchange: str
    label: str
    api_key_masked: str
    created_at: str | None = None
    is_primary: bool = False
