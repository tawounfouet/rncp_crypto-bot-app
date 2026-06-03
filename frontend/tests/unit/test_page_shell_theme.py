from __future__ import annotations

from types import SimpleNamespace

from layouts import page_shell
from mocks.db import create_mock_store
from schemas.auth import MockUser


def _noop(*args, **kwargs):  # type: ignore[no-untyped-def]
    return None


def test_setup_page_applies_active_theme_for_public_flow(monkeypatch) -> None:
    store = create_mock_store(disable_latency=True)
    captured: dict[str, str] = {}

    monkeypatch.setattr(page_shell.st, "set_page_config", _noop)
    monkeypatch.setattr(page_shell, "apply_global_styles", lambda mode: captured.setdefault("mode", mode))
    monkeypatch.setattr(page_shell, "get_theme_mode", lambda: "light")
    monkeypatch.setattr(page_shell, "get_store", lambda: store)
    monkeypatch.setattr(
        page_shell,
        "AuthService",
        lambda _: SimpleNamespace(ensure_authenticated_user=lambda: None, logout=lambda: None),
    )
    monkeypatch.setattr(page_shell, "render_public_sidebar", _noop)
    monkeypatch.setattr(page_shell, "can_access", lambda page_key, user: True)

    resolved_store, user = page_shell.setup_page("Connexion", "x", "login")

    assert resolved_store is store
    assert user is None
    assert captured["mode"] == "light"


def test_setup_page_applies_active_theme_for_private_flow(monkeypatch) -> None:
    store = create_mock_store(disable_latency=True)
    user: MockUser = store.users["alice@cryptobot.dev"]
    store.current_user_email = user.email
    captured: dict[str, str] = {}

    monkeypatch.setattr(page_shell.st, "set_page_config", _noop)
    monkeypatch.setattr(page_shell, "apply_global_styles", lambda mode: captured.setdefault("mode", mode))
    monkeypatch.setattr(page_shell, "get_theme_mode", lambda: "dark")
    monkeypatch.setattr(page_shell, "get_store", lambda: store)
    monkeypatch.setattr(
        page_shell,
        "AuthService",
        lambda _: SimpleNamespace(ensure_authenticated_user=lambda: user, logout=lambda: None),
    )
    monkeypatch.setattr(page_shell, "render_private_sidebar", lambda st, usr: False)
    monkeypatch.setattr(page_shell, "can_access", lambda page_key, usr: True)

    resolved_store, resolved_user = page_shell.setup_page("Portefeuille", "x", "portfolio")

    assert resolved_store is store
    assert resolved_user is user
    assert captured["mode"] == "dark"
