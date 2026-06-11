"""Pre-requis Binance centralises par page."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from schemas.auth import MockUser


class BinanceRequirementMode(str, Enum):
    NONE = "none"
    BLOCK_CONTENT = "block_content"
    DISABLE_ACTIONS = "disable_actions"
    READ_ONLY = "read_only"


BINANCE_PAGE_POLICY: dict[str, BinanceRequirementMode] = {
    "portfolio": BinanceRequirementMode.BLOCK_CONTENT,
    "performance": BinanceRequirementMode.BLOCK_CONTENT,
    "bot_control": BinanceRequirementMode.DISABLE_ACTIONS,
    "bot_config": BinanceRequirementMode.READ_ONLY,
}

BINANCE_MISSING_COPY: dict[str, tuple[str, str]] = {
    "portfolio": (
        "Pré-requis Binance manquant",
        "Configurez vos clés Binance pour afficher le portefeuille, les ordres et les trades.",
    ),
    "performance": (
        "Pré-requis Binance manquant",
        "Configurez vos clés Binance pour consulter les KPI de performance et l'equity curve.",
    ),
    "bot_control": (
        "Pré-requis Binance manquant",
        "Les actions Start/Pause/Stop sont bloquées tant que Binance n'est pas configuré.",
    ),
    "bot_config": (
        "Pré-requis Binance manquant",
        "Le paramétrage est en lecture seule tant que Binance n'est pas configuré.",
    ),
}


@dataclass(frozen=True)
class BinancePrerequisiteStatus:
    page_key: str
    mode: BinanceRequirementMode
    user_is_authenticated: bool
    binance_configured: bool

    @property
    def missing(self) -> bool:
        if not self.user_is_authenticated:
            return False
        return self.mode != BinanceRequirementMode.NONE and not self.binance_configured

    @property
    def should_block_content(self) -> bool:
        return self.missing and self.mode == BinanceRequirementMode.BLOCK_CONTENT

    @property
    def actions_disabled(self) -> bool:
        return self.missing and self.mode in {
            BinanceRequirementMode.DISABLE_ACTIONS,
            BinanceRequirementMode.READ_ONLY,
        }

    @property
    def read_only(self) -> bool:
        return self.missing and self.mode == BinanceRequirementMode.READ_ONLY


def requirement_mode_for_page(page_key: str) -> BinanceRequirementMode:
    return BINANCE_PAGE_POLICY.get(page_key, BinanceRequirementMode.NONE)


def page_requires_binance(page_key: str) -> bool:
    return requirement_mode_for_page(page_key) != BinanceRequirementMode.NONE


def is_binance_configured(user: MockUser | None) -> bool:
    if user is None:
        return False
    from state.session import get_binance_configured, is_binance_synced

    # Prefere la valeur en session (synchronisee avec le backend) si disponible
    if is_binance_synced():
        return get_binance_configured()
    return bool(user.binance_configured)


def evaluate_binance_prerequisite(
    page_key: str, user: MockUser | None
) -> BinancePrerequisiteStatus:
    return BinancePrerequisiteStatus(
        page_key=page_key,
        mode=requirement_mode_for_page(page_key),
        user_is_authenticated=user is not None,
        binance_configured=is_binance_configured(user),
    )


def missing_copy_for_page(page_key: str) -> tuple[str, str]:
    return BINANCE_MISSING_COPY.get(
        page_key,
        (
            "Pré-requis Binance manquant",
            "Configurez vos clés Binance pour continuer.",
        ),
    )
