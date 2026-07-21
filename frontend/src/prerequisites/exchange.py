"""Pre-requis exchange centralises par page (issue #13 — multi-exchange)."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from schemas.auth import MockUser


class ExchangeRequirementMode(str, Enum):
    NONE = "none"
    BLOCK_CONTENT = "block_content"
    DISABLE_ACTIONS = "disable_actions"
    READ_ONLY = "read_only"


EXCHANGE_PAGE_POLICY: dict[str, ExchangeRequirementMode] = {
    "portfolio": ExchangeRequirementMode.BLOCK_CONTENT,
    "performance": ExchangeRequirementMode.BLOCK_CONTENT,
    "bot_control": ExchangeRequirementMode.DISABLE_ACTIONS,
    "bot_config": ExchangeRequirementMode.READ_ONLY,
}

EXCHANGE_MISSING_COPY: dict[str, tuple[str, str]] = {
    "portfolio": (
        "Pré-requis exchange manquant",
        "Configurez vos clés d'exchange pour afficher le portefeuille, les ordres et les trades.",
    ),
    "performance": (
        "Pré-requis exchange manquant",
        "Configurez vos clés d'exchange pour consulter les KPI de performance et l'equity curve.",
    ),
    "bot_control": (
        "Pré-requis exchange manquant",
        "Les actions Start/Pause/Stop sont bloquées tant que l'exchange n'est pas configuré.",
    ),
    "bot_config": (
        "Pré-requis exchange manquant",
        "Le paramétrage est en lecture seule tant que l'exchange n'est pas configuré.",
    ),
}


@dataclass(frozen=True)
class ExchangePrerequisiteStatus:
    page_key: str
    mode: ExchangeRequirementMode
    user_is_authenticated: bool
    exchange_configured: bool

    @property
    def missing(self) -> bool:
        if not self.user_is_authenticated:
            return False
        return self.mode != ExchangeRequirementMode.NONE and not self.exchange_configured

    @property
    def should_block_content(self) -> bool:
        return self.missing and self.mode == ExchangeRequirementMode.BLOCK_CONTENT

    @property
    def actions_disabled(self) -> bool:
        return self.missing and self.mode in {
            ExchangeRequirementMode.DISABLE_ACTIONS,
            ExchangeRequirementMode.READ_ONLY,
        }

    @property
    def read_only(self) -> bool:
        return self.missing and self.mode == ExchangeRequirementMode.READ_ONLY


def requirement_mode_for_page(page_key: str) -> ExchangeRequirementMode:
    return EXCHANGE_PAGE_POLICY.get(page_key, ExchangeRequirementMode.NONE)


def page_requires_exchange(page_key: str) -> bool:
    return requirement_mode_for_page(page_key) != ExchangeRequirementMode.NONE


def is_exchange_configured(user: MockUser | None) -> bool:
    if user is None:
        return False
    from state.session import get_exchange_configured, is_exchange_synced

    # Prefere la valeur en session (synchronisee avec le backend) si disponible
    if is_exchange_synced():
        return get_exchange_configured()
    return bool(user.exchange_configured)


def evaluate_exchange_prerequisite(
    page_key: str, user: MockUser | None
) -> ExchangePrerequisiteStatus:
    return ExchangePrerequisiteStatus(
        page_key=page_key,
        mode=requirement_mode_for_page(page_key),
        user_is_authenticated=user is not None,
        exchange_configured=is_exchange_configured(user),
    )


def missing_copy_for_page(page_key: str) -> tuple[str, str]:
    return EXCHANGE_MISSING_COPY.get(
        page_key,
        (
            "Pré-requis exchange manquant",
            "Configurez vos clés d'exchange pour continuer.",
        ),
    )
