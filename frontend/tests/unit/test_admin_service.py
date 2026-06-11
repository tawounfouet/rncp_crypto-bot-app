from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from schemas.common import UserRole
from services.admin_service import AdminService
from services.api_client import BackendApiClient
from services.auth_api_client import ApiResponse


MOCK_USERS = [
    {
        "id": "u1",
        "email": "alice@cryptobot.dev",
        "first_name": "Alice",
        "last_name": "Martin",
        "is_active": True,
        "is_admin": False,
        "last_active_at": None,
    },
    {
        "id": "u2",
        "email": "admin@cryptobot.dev",
        "first_name": "Admin",
        "last_name": None,
        "is_active": True,
        "is_admin": True,
        "last_active_at": None,
    },
]


def _ok(data: object) -> ApiResponse:
    return ApiResponse(status_code=200, data=data)


@pytest.fixture(autouse=True)
def _mock_token():
    with patch("services.admin_service.get_access_token", return_value="fake-token"):
        yield


def test_admin_list_users(store) -> None:
    store.current_user_email = "admin@cryptobot.dev"
    client = MagicMock(spec=BackendApiClient)
    client.list_users.return_value = _ok(MOCK_USERS)
    service = AdminService(store, client=client)
    rows = service.list_users()
    assert len(rows) == 2
    assert any(r.email == "alice@cryptobot.dev" for r in rows)


def test_admin_toggle_user_status(store) -> None:
    store.current_user_email = "admin@cryptobot.dev"
    client = MagicMock(spec=BackendApiClient)
    client.list_users.return_value = _ok(MOCK_USERS)
    client.deactivate_user.return_value = _ok({"message": "deactivated"})
    service = AdminService(store, client=client)
    service.list_users()  # populate _user_list
    ok, _ = service.set_enabled("alice@cryptobot.dev", False)
    assert ok is True
    client.deactivate_user.assert_called_once_with("fake-token", "u1")


def test_admin_activate_user(store) -> None:
    store.current_user_email = "admin@cryptobot.dev"
    client = MagicMock(spec=BackendApiClient)
    client.list_users.return_value = _ok(MOCK_USERS)
    client.activate_user.return_value = _ok({"message": "activated"})
    service = AdminService(store, client=client)
    service.list_users()
    ok, _ = service.set_enabled("alice@cryptobot.dev", True)
    assert ok is True
    client.activate_user.assert_called_once_with("fake-token", "u1")


def test_admin_set_role_not_available(store) -> None:
    store.current_user_email = "admin@cryptobot.dev"
    service = AdminService(store, client=MagicMock())
    ok, message = service.set_role("alice@cryptobot.dev", UserRole.ADMIN)
    assert ok is False
    assert "non disponible" in message
