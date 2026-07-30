"""Parsing des dates renvoyees par le backend (JSON API)."""

from __future__ import annotations

from datetime import UTC, datetime


def parse_dt(value: object) -> datetime | None:
    """Parse une date ISO backend en datetime aware (UTC).

    Retourne None si value est None ou si le parsing echoue -- a l'appelant de
    decider du fallback (cf. parse_dt_or_now pour le cas "toujours une date").
    """
    parsed: datetime | None = None
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, str):
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            parsed = None

    if parsed is None:
        return None
    if parsed.tzinfo is None:
        # Colonne DateTime backend sans timezone=True : serialisee sans offset,
        # mais toujours ecrite en UTC cote backend.
        parsed = parsed.replace(tzinfo=UTC)
    return parsed


def parse_dt_or_now(value: object) -> datetime:
    """Comme parse_dt, mais retombe sur l'heure courante (UTC) si absent/invalide."""
    return parse_dt(value) or datetime.now(UTC)
