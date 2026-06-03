from __future__ import annotations

import pytest

from mocks.db import MockStore, create_mock_store


@pytest.fixture
def store() -> MockStore:
    return create_mock_store(disable_latency=True)
