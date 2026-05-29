"""Gestion centralisee du mode de theme."""

from __future__ import annotations

from typing import Literal, cast

from mocks.db import MockStore

ThemeMode = Literal["dark", "light"]
DEFAULT_THEME_MODE: ThemeMode = "dark"
SUPPORTED_THEME_MODES: tuple[ThemeMode, ThemeMode] = ("dark", "light")


def normalize_theme_mode(mode: str | None) -> ThemeMode:
    if mode == "light":
        return "light"
    return DEFAULT_THEME_MODE


def get_store_theme_mode(store: MockStore) -> ThemeMode:
    mode = normalize_theme_mode(store.ui_theme_mode)
    store.ui_theme_mode = mode
    return cast(ThemeMode, mode)


def set_store_theme_mode(store: MockStore, mode: str) -> ThemeMode:
    normalized = normalize_theme_mode(mode)
    store.ui_theme_mode = normalized
    return normalized
