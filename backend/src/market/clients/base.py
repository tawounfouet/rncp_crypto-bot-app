"""Contrat commun aux clients d'execution multi-exchange (issue #13).

Distinct de utils/connectors/exchanges/ (donnees de marche publiques, sans cle) :
ce module couvre les operations authentifiees (comptes, ordres).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class Balance:
    """Solde d'un actif sur un compte exchange."""

    asset: str
    free: Decimal
    locked: Decimal

    @property
    def total(self) -> Decimal:
        return self.free + self.locked


@dataclass(frozen=True)
class Ticker:
    """Dernier prix connu pour une paire, en symbole canonique (ex: BTCUSDC, BTCEUR)."""

    symbol: str
    price: Decimal


@dataclass(frozen=True)
class OrderResult:
    """Reponse normalisee a la creation/annulation d'un ordre."""

    order_id: str
    symbol: str
    side: str
    order_type: str
    status: str
    quantity: Decimal
    price: Decimal | None = None


class ExchangeClient(ABC):
    """Contrat commun a tous les clients d'execution (comptes, ordres)."""

    source: str

    @abstractmethod
    def get_balances(self) -> list[Balance]:
        """Retourne les soldes non nuls du compte."""

    @abstractmethod
    def get_tickers(self, quote: str | None = None) -> list[Ticker]:
        """Retourne les derniers prix connus, filtres sur une devise de cotation si fournie."""

    @abstractmethod
    def place_order(
        self,
        symbol: str,
        side: str,
        order_type: str,
        quantity: Decimal | None = None,
        price: Decimal | None = None,
        quote_quantity: Decimal | None = None,
    ) -> OrderResult:
        """Place un ordre.

        `quantity` (actif de base) et `quote_quantity` (devise de cotation, ex. "depenser
        100 USDC") sont mutuellement exclusifs. `quote_quantity` n'est supporte que pour les
        ordres MARKET BUY -- leve ValueError si l'exchange ou order_type ne le permet pas
        (cf. CcxtClient.place_order).
        """

    @abstractmethod
    def cancel_order(self, symbol: str, order_id: str) -> OrderResult:
        """Annule un ordre existant."""

    @abstractmethod
    def get_open_orders(self, symbol: str | None = None) -> list[OrderResult]:
        """Retourne les ordres ouverts (tous symboles si `symbol` est omis)."""
