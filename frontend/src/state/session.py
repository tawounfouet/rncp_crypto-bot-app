"""Gestion du state Streamlit pour l'application."""

from __future__ import annotations

import time
from datetime import UTC, datetime
from typing import Any, cast

import streamlit as st

from mocks.db import MockStore, create_mock_store
from mocks.scenarios import MockScenario
from schemas.auth import MockUser
from schemas.common import UserRole, UserStatus
from theme.manager import ThemeMode, get_store_theme_mode, set_store_theme_mode
from utils.constants import DEFAULT_EXCHANGE

STORE_KEY = "app_store"
ACCESS_TOKEN_KEY = "access_token"
REFRESH_TOKEN_KEY = "refresh_token"
USER_DATA_KEY = "user_data"
AUTHENTICATED_KEY = "authenticated"
USER_SYNCED_AT_KEY = "user_synced_at"
USER_SYNCED_TOKEN_KEY = "user_synced_token"
EXCHANGE_CONFIGURED_KEY = "exchange_configured"
EXCHANGE_SYNCED_KEY = "exchange_synced"
SELECTED_EXCHANGE_KEY = "selected_exchange"


def get_store() -> MockStore:
    _ensure_auth_state_keys()
    if STORE_KEY not in st.session_state:
        st.session_state[STORE_KEY] = create_mock_store()
    return cast(MockStore, st.session_state[STORE_KEY])


def reset_store() -> None:
    _ensure_auth_state_keys()
    st.session_state[STORE_KEY] = create_mock_store()
    st.session_state[ACCESS_TOKEN_KEY] = None
    st.session_state[REFRESH_TOKEN_KEY] = None
    st.session_state[USER_DATA_KEY] = None
    st.session_state[AUTHENTICATED_KEY] = False
    _clear_user_sync_metadata()


def set_current_user(email: str | None) -> None:
    store = get_store()
    store.current_user_email = email.lower() if email else None


def get_current_user() -> MockUser | None:
    store = get_store()
    if not store.current_user_email:
        return None
    return store.users.get(store.current_user_email.lower())


def is_authenticated() -> bool:
    return get_current_user() is not None


def is_admin() -> bool:
    user = get_current_user()
    return bool(user and user.role.value == "ADMIN")


def set_scenario(scenario: MockScenario) -> None:
    store = get_store()
    store.scenario = scenario


def get_scenario() -> MockScenario:
    return get_store().scenario


def get_theme_mode() -> ThemeMode:
    return get_store_theme_mode(get_store())


def set_theme_mode(mode: ThemeMode) -> ThemeMode:
    return set_store_theme_mode(get_store(), mode)


def get_access_token() -> str | None:
    _ensure_auth_state_keys()
    return cast(str | None, st.session_state.get(ACCESS_TOKEN_KEY))


def get_refresh_token() -> str | None:
    _ensure_auth_state_keys()
    return cast(str | None, st.session_state.get(REFRESH_TOKEN_KEY))


def set_auth_tokens(access_token: str | None, refresh_token: str | None = None) -> None:
    _ensure_auth_state_keys()
    previous_access_token = cast(str | None, st.session_state.get(ACCESS_TOKEN_KEY))
    st.session_state[ACCESS_TOKEN_KEY] = access_token
    if refresh_token is not None or REFRESH_TOKEN_KEY not in st.session_state:
        st.session_state[REFRESH_TOKEN_KEY] = refresh_token
    if previous_access_token != access_token:
        _clear_user_sync_metadata()
    st.session_state[AUTHENTICATED_KEY] = bool(st.session_state.get(ACCESS_TOKEN_KEY))


def clear_auth_session(store: MockStore | None = None) -> None:
    _ensure_auth_state_keys()
    st.session_state[ACCESS_TOKEN_KEY] = None
    st.session_state[REFRESH_TOKEN_KEY] = None
    st.session_state[USER_DATA_KEY] = None
    st.session_state[AUTHENTICATED_KEY] = False
    st.session_state[EXCHANGE_CONFIGURED_KEY] = False
    st.session_state[EXCHANGE_SYNCED_KEY] = False
    _clear_user_sync_metadata()
    active_store = store or get_store()
    active_store.current_user_email = None


def get_exchange_configured() -> bool:
    return bool(st.session_state.get(EXCHANGE_CONFIGURED_KEY, False))


def set_exchange_configured(configured: bool, store: MockStore | None = None) -> None:
    st.session_state[EXCHANGE_CONFIGURED_KEY] = configured
    st.session_state[EXCHANGE_SYNCED_KEY] = True
    active_store = store or get_store()
    if active_store.current_user_email:
        user = active_store.users.get(active_store.current_user_email)
        if user:
            user.exchange_configured = configured


def is_exchange_synced() -> bool:
    return bool(st.session_state.get(EXCHANGE_SYNCED_KEY, False))


def get_selected_exchange() -> str:
    return cast(str, st.session_state.get(SELECTED_EXCHANGE_KEY, DEFAULT_EXCHANGE))


def set_selected_exchange(exchange: str) -> None:
    previous = st.session_state.get(SELECTED_EXCHANGE_KEY, DEFAULT_EXCHANGE)
    st.session_state[SELECTED_EXCHANGE_KEY] = exchange
    if previous != exchange:
        # Le statut de configuration synchronise concerne l'exchange precedent : on
        # force une resynchro aupres du backend pour l'exchange nouvellement selectionne.
        st.session_state[EXCHANGE_SYNCED_KEY] = False


def has_recent_current_user_sync(access_token: str, *, max_age_seconds: int) -> bool:
    _ensure_auth_state_keys()
    synced_token = cast(str | None, st.session_state.get(USER_SYNCED_TOKEN_KEY))
    synced_at = st.session_state.get(USER_SYNCED_AT_KEY)
    if synced_token != access_token or not isinstance(synced_at, int | float):
        return False
    return (time.time() - float(synced_at)) <= max_age_seconds


def mark_current_user_synced(access_token: str | None = None) -> None:
    _ensure_auth_state_keys()
    resolved_access_token = access_token or cast(str | None, st.session_state.get(ACCESS_TOKEN_KEY))
    if not resolved_access_token:
        _clear_user_sync_metadata()
        return
    st.session_state[USER_SYNCED_TOKEN_KEY] = resolved_access_token
    st.session_state[USER_SYNCED_AT_KEY] = time.time()


def sync_current_user_from_backend(
    user_data: dict[str, Any],
    *,
    store: MockStore | None = None,
    password: str | None = None,
    last_login: datetime | None = None,
    access_token: str | None = None,
) -> MockUser:
    active_store = store or get_store()
    email = str(user_data.get("email", "")).strip().lower()
    if not email:
        raise ValueError("Le backend n'a pas retourne d'email utilisateur.")

    existing_user = active_store.users.get(email)
    resolved_last_name = _resolve_last_name(user_data, existing_user)
    active_store.users[email] = MockUser(
        id=str(user_data.get("id") or (existing_user.id if existing_user else email)),
        first_name=_resolve_first_name(user_data, existing_user, email),
        last_name=resolved_last_name,
        email=email,
        password=(password if password is not None else None)
        or (existing_user.password if existing_user else "")
        or "",
        role=UserRole.ADMIN if bool(user_data.get("is_admin")) else UserRole.USER,
        status=(
            UserStatus.ENABLED if bool(user_data.get("is_active", True)) else UserStatus.DISABLED
        ),
        created_at=_parse_datetime(
            user_data.get("created_at"),
            fallback=existing_user.created_at if existing_user else None,
        ),
        last_login=(
            last_login
            if last_login is not None
            else (existing_user.last_login if existing_user else None)
        ),
        exchange_configured=existing_user.exchange_configured if existing_user else False,
        failed_login_count=existing_user.failed_login_count if existing_user else 0,
    )
    active_store.current_user_email = email
    st.session_state[USER_DATA_KEY] = dict(user_data)
    st.session_state[AUTHENTICATED_KEY] = True
    mark_current_user_synced(access_token)
    return active_store.users[email]


def _ensure_auth_state_keys() -> None:
    if ACCESS_TOKEN_KEY not in st.session_state:
        st.session_state[ACCESS_TOKEN_KEY] = None
    if REFRESH_TOKEN_KEY not in st.session_state:
        st.session_state[REFRESH_TOKEN_KEY] = None
    if USER_DATA_KEY not in st.session_state:
        st.session_state[USER_DATA_KEY] = None
    if AUTHENTICATED_KEY not in st.session_state:
        st.session_state[AUTHENTICATED_KEY] = False
    if USER_SYNCED_AT_KEY not in st.session_state:
        st.session_state[USER_SYNCED_AT_KEY] = None
    if USER_SYNCED_TOKEN_KEY not in st.session_state:
        st.session_state[USER_SYNCED_TOKEN_KEY] = None


def _clear_user_sync_metadata() -> None:
    st.session_state[USER_SYNCED_AT_KEY] = None
    st.session_state[USER_SYNCED_TOKEN_KEY] = None


def _parse_datetime(value: Any, fallback: datetime | None = None) -> datetime:
    parsed: datetime | None = None
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, str):
        normalized = value.replace("Z", "+00:00")
        try:
            parsed = datetime.fromisoformat(normalized)
        except ValueError:
            pass
    if parsed is None:
        parsed = fallback or datetime.now(UTC)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _resolve_first_name(
    user_data: dict[str, Any],
    existing_user: MockUser | None,
    email: str,
) -> str:
    raw_first_name = user_data.get("first_name")
    if raw_first_name and str(raw_first_name).strip():
        return str(raw_first_name).strip()
    if existing_user and existing_user.first_name.strip():
        return existing_user.first_name
    raw_username = user_data.get("username")
    if raw_username and str(raw_username).strip():
        return str(raw_username).strip()
    return email.split("@", 1)[0]


def _resolve_last_name(user_data: dict[str, Any], existing_user: MockUser | None) -> str | None:
    raw_last_name = user_data.get("last_name")
    if raw_last_name and str(raw_last_name).strip():
        return str(raw_last_name).strip()
    if existing_user:
        return existing_user.last_name
    return None
