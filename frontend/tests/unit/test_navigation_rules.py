from __future__ import annotations

from navigation.rules import allowed_page_keys_in_sidebar, can_access, sidebar_entries


def test_sidebar_entries_when_anonymous() -> None:
    labels = [entry.label for entry in sidebar_entries(None)]
    assert labels == ["Connexion", "Inscription"]


def test_sidebar_entries_when_authenticated_standard_user(store) -> None:
    user = store.users["alice@cryptobot.dev"]
    keys = allowed_page_keys_in_sidebar(user)
    assert "signup" not in keys
    assert "admin" not in keys
    assert keys == ["portfolio", "performance", "bot_control", "bot_config", "backtesting", "account"]


def test_sidebar_entries_when_authenticated_admin(store) -> None:
    user = store.users["admin@cryptobot.dev"]
    keys = allowed_page_keys_in_sidebar(user)
    assert "admin" in keys


def test_admin_page_access_blocked_for_standard_user(store) -> None:
    user = store.users["alice@cryptobot.dev"]
    assert can_access("admin", user) is False
    assert can_access("admin", None) is False


def test_admin_page_access_allowed_for_admin(store) -> None:
    user = store.users["admin@cryptobot.dev"]
    assert can_access("admin", user) is True
