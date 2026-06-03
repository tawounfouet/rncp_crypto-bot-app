"""Validations frontend simples."""

from __future__ import annotations

import re

from utils.constants import DEFAULT_PASSWORD_MIN_LENGTH

EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")


def validate_email(email: str) -> tuple[bool, str]:
    text = email.strip()
    if not text:
        return False, "L'email est requis."
    if not EMAIL_RE.match(text):
        return False, "Format d'email invalide."
    return True, ""


def validate_username(username: str) -> tuple[bool, str]:
    text = username.strip()
    if not text:
        return False, "Le nom d'utilisateur est requis."
    if len(text) < 3:
        return False, "Le nom d'utilisateur doit contenir au moins 3 caracteres."
    return True, ""


def validate_password(password: str) -> tuple[bool, str]:
    if len(password) < DEFAULT_PASSWORD_MIN_LENGTH:
        return False, f"Mot de passe trop court ({DEFAULT_PASSWORD_MIN_LENGTH} caracteres minimum)."
    if not any(char.isupper() for char in password):
        return False, "Le mot de passe doit contenir au moins une majuscule."
    if not any(char.islower() for char in password):
        return False, "Le mot de passe doit contenir au moins une minuscule."
    if not any(char.isdigit() for char in password):
        return False, "Le mot de passe doit contenir au moins un chiffre."
    return True, ""


def validate_confirm_password(password: str, confirm_password: str) -> tuple[bool, str]:
    if password != confirm_password:
        return False, "La confirmation de mot de passe ne correspond pas."
    return True, ""


def validate_required(value: str, field_label: str) -> tuple[bool, str]:
    if not value or not value.strip():
        return False, f"{field_label} est requis."
    return True, ""
