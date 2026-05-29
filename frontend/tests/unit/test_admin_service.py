from __future__ import annotations

from schemas.common import UserRole, UserStatus
from services.admin_service import AdminService


def test_admin_list_users(store) -> None:
    store.current_user_email = "admin@cryptobot.dev"
    service = AdminService(store)
    rows = service.list_users()
    assert len(rows) >= 2
    assert any(row.binance_configured for row in rows)


def test_admin_toggle_user_status(store) -> None:
    store.current_user_email = "admin@cryptobot.dev"
    service = AdminService(store)
    ok, _ = service.set_enabled("alice@cryptobot.dev", False)
    assert ok is True
    assert store.users["alice@cryptobot.dev"].status == UserStatus.DISABLED


def test_admin_set_role(store) -> None:
    store.current_user_email = "admin@cryptobot.dev"
    service = AdminService(store)
    ok, _ = service.set_role("alice@cryptobot.dev", UserRole.ADMIN)
    assert ok is True
    assert store.users["alice@cryptobot.dev"].role == UserRole.ADMIN
