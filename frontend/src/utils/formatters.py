"""Fonctions de formatage UI."""

from __future__ import annotations

from datetime import datetime


def format_currency(value: float, suffix: str = "USDT") -> str:
    return f"{value:,.2f} {suffix}".replace(",", " ")


def format_pct(value: float) -> str:
    return f"{value:+.2f}%"


def format_datetime(value: datetime | None) -> str:
    if value is None:
        return "-"
    return value.strftime("%Y-%m-%d %H:%M:%S")


def mask_secret(secret: str, visible: int = 4) -> str:
    if not secret:
        return ""
    if len(secret) <= visible * 2:
        return "*" * len(secret)
    return f"{secret[:visible]}{'*' * (len(secret) - visible * 2)}{secret[-visible:]}"


def bool_to_label(value: bool, yes: str = "Oui", no: str = "Non") -> str:
    return yes if value else no
