"""Optional dependency helpers."""

from __future__ import annotations

from importlib.util import find_spec

from src.config.exceptions import MissingDependencyError


def require_dependency(module_name: str, install_hint: str | None = None) -> None:
    """Raise a clear error when an optional dependency is missing."""
    if find_spec(module_name) is None:
        hint = install_hint or f"Install dependency `{module_name}`."
        raise MissingDependencyError(f"Missing optional dependency `{module_name}`. {hint}")
