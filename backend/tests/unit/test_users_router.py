"""Tests unitaires pour la route POST /users/purge-inactive.

Le service est mocke via patch -- ces tests verifient le cablage HTTP
(route, code de statut, mapping des erreurs), pas la logique metier
(deja couverte par les tests de service dans test_user_service.py).
"""

from __future__ import annotations

from unittest.mock import patch

import pytest
from auth.users_router import router
from fastapi import FastAPI
from fastapi.testclient import TestClient


@pytest.fixture
def client() -> TestClient:
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


def test_purge_inactive_users_returns_deleted_count(client: TestClient) -> None:
    with patch(
        "auth.users_router.user_service.delete_inactive_users_older_than",
        return_value=3,
    ) as mock_delete:
        response = client.post("/users/purge-inactive")

    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["data"] == {"deleted": 3}
    mock_delete.assert_called_once_with(days=730)


def test_purge_inactive_users_accepts_custom_days(client: TestClient) -> None:
    with patch(
        "auth.users_router.user_service.delete_inactive_users_older_than",
        return_value=0,
    ) as mock_delete:
        response = client.post("/users/purge-inactive?days=365")

    assert response.status_code == 200
    mock_delete.assert_called_once_with(days=365)


def test_purge_inactive_users_rejects_zero_days(client: TestClient) -> None:
    response = client.post("/users/purge-inactive?days=0")

    assert response.status_code == 422


def test_purge_inactive_users_returns_500_on_service_error(client: TestClient) -> None:
    with patch(
        "auth.users_router.user_service.delete_inactive_users_older_than",
        side_effect=Exception("boom"),
    ):
        response = client.post("/users/purge-inactive")

    assert response.status_code == 500
