"""Runtime switches for real backend mode versus local test doubles."""

from __future__ import annotations

import os

TRUE_VALUES = {"1", "true", "yes", "on"}


def _truthy_env(name: str) -> bool:
    return os.getenv(name, "").strip().lower() in TRUE_VALUES


def allow_mock_fallback() -> bool:
    """Return whether services may use local mock data when no backend session exists."""
    if _truthy_env("ALLOW_MOCK_FALLBACK"):
        return True
    return not _truthy_env("DISABLE_MOCK_FALLBACK")


def backend_required_message(area: str) -> str:
    return f"Session backend requise pour charger {area}. Aucun fallback mock n'est actif."
