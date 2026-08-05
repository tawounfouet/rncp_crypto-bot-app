"""Construction d'un client d'execution a partir des identifiants stockes d'un utilisateur."""

from __future__ import annotations

from typing import TYPE_CHECKING

from .base import ExchangeClient
from .registry import get_exchange_client

if TYPE_CHECKING:
    from auth.models import UserSettings


def from_user_settings(settings: UserSettings, exchange: str) -> ExchangeClient:
    """Cree le client d'execution d'un exchange a partir des cles API enregistrees.

    Resout le mode actif (live/sandbox) de l'utilisateur pour cet exchange. Si le mode
    sandbox est actif mais qu'aucune cle sandbox dediee n'existe (ex: Kraken, qui n'a pas de
    testnet Spot), retombe sur les cles live -- le mode simule s'y traduit uniquement par
    `validate=true` a l'execution des ordres (cf. CcxtClient, docs/testnet-simulation-modes.md),
    jamais par un jeu de cles different.

    Args:
        settings: UserSettings de l'utilisateur (cles API chiffrees par exchange).
        exchange: Identifiant d'exchange (ex: "binance", "kraken").

    Raises:
        ValueError: Si aucune cle API n'est disponible pour cet exchange (ni pour le mode
            actif, ni en repli sur les cles live).
    """
    active_mode = settings.get_active_mode(exchange)
    api_key = settings.get_api_key(exchange, mode=active_mode)
    api_secret = settings.get_api_secret(exchange, mode=active_mode)

    if (api_key is None or api_secret is None) and active_mode != "live":
        api_key = settings.get_api_key(exchange, mode="live")
        api_secret = settings.get_api_secret(exchange, mode="live")

    if not api_key or not api_secret:
        raise ValueError(f"Cles API {exchange} manquantes pour cet utilisateur")

    return get_exchange_client(exchange, api_key=api_key, api_secret=api_secret, sandbox=(active_mode == "sandbox"))
