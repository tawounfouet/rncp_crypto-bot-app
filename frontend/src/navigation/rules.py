"""Regles centralisees de navigation et de controle d'acces."""

from __future__ import annotations

from dataclasses import dataclass

from schemas.auth import MockUser
from schemas.common import UserRole


@dataclass(frozen=True)
class NavPage:
    key: str
    label: str
    path: str
    requires_auth: bool = False
    requires_admin: bool = False
    show_when_anonymous: bool = False
    show_when_authenticated: bool = False


PAGES: dict[str, NavPage] = {
    "login": NavPage(
        key="login",
        label="Connexion",
        path="app.py",
        show_when_anonymous=True,
    ),
    "signup": NavPage(
        key="signup",
        label="Inscription",
        path="pages/02_Inscription.py",
        show_when_anonymous=True,
    ),
    "portfolio": NavPage(
        key="portfolio",
        label="Portefeuille Spot",
        path="pages/03_Portefeuille_Spot.py",
        requires_auth=True,
        show_when_authenticated=True,
    ),
    "performance": NavPage(
        key="performance",
        label="Performances Spot",
        path="pages/04_Performances_Spot.py",
        requires_auth=True,
        show_when_authenticated=True,
    ),
    "bot_control": NavPage(
        key="bot_control",
        label="Controle Bot Spot",
        path="pages/05_Controle_Bot_Spot.py",
        requires_auth=True,
        show_when_authenticated=True,
    ),
    "bot_config": NavPage(
        key="bot_config",
        label="Catalogue Bots Spot",
        path="pages/06_Parametrage_Bot_Spot.py",
        requires_auth=True,
        show_when_authenticated=True,
    ),
    "account": NavPage(
        key="account",
        label="Gestion de compte",
        path="pages/07_Gestion_de_compte.py",
        requires_auth=True,
        show_when_authenticated=True,
    ),
    "binance_testnet_lab": NavPage(
        key="binance_testnet_lab",
        label="Binance Testnet Lab",
        path="pages/09_Binance_Testnet_Lab.py",
        requires_auth=True,
        show_when_authenticated=True,
    ),
    "admin": NavPage(
        key="admin",
        label="Admin",
        path="pages/08_Admin.py",
        requires_auth=True,
        requires_admin=True,
        show_when_authenticated=True,
    ),
}


def get_page(page_key: str) -> NavPage:
    page = PAGES.get(page_key)
    if page is None:
        raise KeyError(f"Unknown page key: {page_key}")
    return page


def allowed_page_keys_in_sidebar(user: MockUser | None) -> list[str]:
    if user is None:
        return ["login", "signup"]

    keys = [
        "portfolio",
        "performance",
        "bot_control",
        "bot_config",
        "account",
        "binance_testnet_lab",
    ]
    if user.role == UserRole.ADMIN:
        keys.append("admin")
    return keys


def sidebar_entries(user: MockUser | None) -> list[NavPage]:
    return [get_page(key) for key in allowed_page_keys_in_sidebar(user)]


def can_access(page_key: str, user: MockUser | None) -> bool:
    page = get_page(page_key)
    if page.requires_auth and user is None:
        return False
    if page.requires_admin and (user is None or user.role != UserRole.ADMIN):
        return False
    return True
