"""Definitions de scenarios mockes."""

from __future__ import annotations

from enum import Enum


class MockScenario(str, Enum):
    USER_NORMAL = "utilisateur_normal"
    USER_ADMIN = "admin"
    BINANCE_NOT_CONFIGURED = "binance_non_configure"
    PORTFOLIO_EMPTY = "portefeuille_vide"
    PORTFOLIO_RICH = "portefeuille_riche"
    BOT_ERROR = "bot_en_erreur"
    BOT_RUNNING = "bot_en_execution"
    PERFORMANCE_STRONG = "performances_fortes"
    PERFORMANCE_WEAK = "performances_degradees"


SCENARIO_LABELS: dict[MockScenario, str] = {
    MockScenario.USER_NORMAL: "Utilisateur normal",
    MockScenario.USER_ADMIN: "Admin",
    MockScenario.BINANCE_NOT_CONFIGURED: "Binance non configure",
    MockScenario.PORTFOLIO_EMPTY: "Portefeuille vide",
    MockScenario.PORTFOLIO_RICH: "Portefeuille riche",
    MockScenario.BOT_ERROR: "Bot en erreur",
    MockScenario.BOT_RUNNING: "Bot en execution",
    MockScenario.PERFORMANCE_STRONG: "Performances fortes",
    MockScenario.PERFORMANCE_WEAK: "Performances degradees",
}


def scenario_options() -> list[MockScenario]:
    return list(MockScenario)
