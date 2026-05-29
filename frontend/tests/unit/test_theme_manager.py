from __future__ import annotations

from theme.manager import (
    DEFAULT_THEME_MODE,
    get_store_theme_mode,
    normalize_theme_mode,
    set_store_theme_mode,
)


def test_normalize_theme_mode_defaults_to_dark_for_unknown_values() -> None:
    assert normalize_theme_mode(None) == DEFAULT_THEME_MODE
    assert normalize_theme_mode("unknown") == DEFAULT_THEME_MODE


def test_store_theme_mode_roundtrip(store) -> None:
    assert get_store_theme_mode(store) == DEFAULT_THEME_MODE

    selected = set_store_theme_mode(store, "light")
    assert selected == "light"
    assert get_store_theme_mode(store) == "light"


def test_store_theme_mode_fallback_to_dark_when_corrupted(store) -> None:
    store.ui_theme_mode = "broken-mode"
    assert get_store_theme_mode(store) == DEFAULT_THEME_MODE
