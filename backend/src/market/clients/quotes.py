"""Devises de cotation par exchange (issue #13).

USDT est restreint sur les fronts regules UE (pas d'agrement EMT, non conforme MiCA) :
on cote donc en USDC (stablecoin conforme) la ou Binance cotait en USDT, et en EUR pour Kraken.
Un seul point de config par exchange, rien de code en dur ailleurs.
"""

from __future__ import annotations

DEFAULT_QUOTE_BY_EXCHANGE: dict[str, str] = {
    "binance": "USDC",
    "binance_us": "USDC",
    "kraken": "EUR",
}

# Devises traitees a parite 1:1 pour valoriser un portefeuille sur cet exchange
# (stablecoins de reference + la devise de cotation par defaut elle-meme).
STABLE_QUOTES_BY_EXCHANGE: dict[str, tuple[str, ...]] = {
    "binance": ("USDC", "BUSD", "TUSD"),
    "binance_us": ("USDC",),
    "kraken": ("EUR", "USDC"),
}


def get_default_quote(exchange: str) -> str:
    """Devise de cotation par defaut pour un exchange."""
    return DEFAULT_QUOTE_BY_EXCHANGE.get(exchange.lower(), "USDC")


def get_stable_quotes(exchange: str) -> tuple[str, ...]:
    """Devises valorisees a parite 1:1 pour cet exchange."""
    return STABLE_QUOTES_BY_EXCHANGE.get(exchange.lower(), (get_default_quote(exchange),))
