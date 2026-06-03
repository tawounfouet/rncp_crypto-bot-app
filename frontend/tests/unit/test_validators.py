from __future__ import annotations

from utils.validators import (
    validate_confirm_password,
    validate_email,
    validate_password,
    validate_required,
)


def test_validate_email() -> None:
    assert validate_email("alice@crypto.dev")[0] is True
    assert validate_email("invalid-mail")[0] is False


def test_validate_password() -> None:
    assert validate_password("Strong123")[0] is True
    assert validate_password("weak")[0] is False


def test_validate_confirm_password() -> None:
    assert validate_confirm_password("Strong123", "Strong123")[0] is True
    assert validate_confirm_password("Strong123", "Strong124")[0] is False


def test_validate_required() -> None:
    assert validate_required("abc", "Champ")[0] is True
    assert validate_required(" ", "Champ")[0] is False
