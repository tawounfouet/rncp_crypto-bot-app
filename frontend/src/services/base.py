"""Utilities communes aux services mockes."""

from __future__ import annotations

import time
from datetime import UTC, datetime
from random import Random

from mocks.db import SEED, MockStore


class ServiceError(RuntimeError):
    """Erreur controlee levee par un service mock."""


def simulate_latency(store: MockStore, min_ms: int = 120, max_ms: int = 420) -> None:
    if store.disable_latency:
        return
    rng = Random(SEED + int(datetime.now(UTC).timestamp()))
    delay = rng.uniform(min_ms, max_ms) / 1000
    time.sleep(delay)


def raise_if_forced_error(store: MockStore, key: str, message: str) -> None:
    if store.force_errors.get(key, False):
        raise ServiceError(message)
