"""Construction d'un client d'execution a partir des identifiants stockes d'un utilisateur."""

from __future__ import annotations

from typing import TYPE_CHECKING

from .base import ExchangeClient
from .registry import get_exchange_client

if TYPE_CHECKING:
    from auth.models import UserSettings


def from_user_settings(settings: UserSettings, exchange: str) -> ExchangeClient:
    """Cree le client d'execution d'un exchange a partir des cles API enregistrees.

    Args:
        settings: UserSettings de l'utilisateur (cles API chiffrees par exchange).
        exchange: Identifiant d'exchange (ex: "binance", "kraken").

    Raises:
        ValueError: Si les cles API pour cet exchange sont absentes.
    """
    api_key = settings.get_api_key(exchange)
    api_secret = settings.get_api_secret(exchange)
    if not api_key or not api_secret:
        raise ValueError(f"Cles API {exchange} manquantes pour cet utilisateur")

    return get_exchange_client(exchange, api_key=api_key, api_secret=api_secret)
