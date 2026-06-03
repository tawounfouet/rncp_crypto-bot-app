"""Service d'authentification reel branche sur le backend existant."""

from __future__ import annotations

from datetime import UTC, datetime

from mocks.db import MockStore
from schemas.auth import AuthResult, LoginRequest, MockUser, RegisterRequest
from services.auth_api_client import ApiResponse, AuthApiClient
from state.session import (
    clear_auth_session,
    get_access_token,
    get_refresh_token,
    has_recent_current_user_sync,
    set_auth_tokens,
    sync_current_user_from_backend,
)
from utils.validators import (
    validate_confirm_password,
    validate_email,
    validate_password,
    validate_required,
    validate_username,
)


class AuthService:
    CURRENT_USER_SYNC_TTL_SECONDS = 60

    def __init__(self, store: MockStore, client: AuthApiClient | None = None) -> None:
        self.store = store
        self.client = client or AuthApiClient()

    def login(self, payload: LoginRequest) -> AuthResult:
        identifier = payload.email.strip()
        ok, message = validate_email(identifier)
        if not ok:
            return AuthResult(success=False, message=message)
        ok, message = validate_required(payload.password, "Le mot de passe")
        if not ok:
            return AuthResult(success=False, message=message)

        response = self.client.login_json(username=identifier, password=payload.password)
        return self._handle_token_response(
            response,
            success_message="Connexion reussie.",
            password=payload.password,
            last_login=datetime.now(UTC),
        )

    def register(self, payload: RegisterRequest) -> AuthResult:
        username = (payload.username or payload.email.split("@", 1)[0]).strip()
        required_fields = [
            (payload.first_name, "Le prenom"),
            (username, "Le nom d'utilisateur"),
            (payload.email, "L'email"),
            (payload.password, "Le mot de passe"),
        ]
        for value, label in required_fields:
            ok, message = validate_required(value, label)
            if not ok:
                return AuthResult(success=False, message=message)

        ok, message = validate_email(payload.email)
        if not ok:
            return AuthResult(success=False, message=message)
        ok, message = validate_username(username)
        if not ok:
            return AuthResult(success=False, message=message)
        ok, message = validate_password(payload.password)
        if not ok:
            return AuthResult(success=False, message=message)
        ok, message = validate_confirm_password(payload.password, payload.confirm_password)
        if not ok:
            return AuthResult(success=False, message=message)

        response = self.client.register(
            email=payload.email.strip().lower(),
            username=username,
            password=payload.password,
            first_name=payload.first_name.strip(),
            last_name=(payload.last_name or "").strip() or None,
        )
        return self._handle_token_response(
            response,
            success_message="Compte cree. Session ouverte.",
            password=payload.password,
            last_login=datetime.now(UTC),
        )

    def logout(self) -> None:
        refresh_token = get_refresh_token()
        if refresh_token:
            self.client.logout(refresh_token)
        clear_auth_session(store=self.store)

    def ensure_authenticated_user(self) -> MockUser | None:
        local_user = self._local_user()
        access_token = get_access_token()
        if not access_token:
            return local_user
        if local_user is not None and has_recent_current_user_sync(
            access_token,
            max_age_seconds=self.CURRENT_USER_SYNC_TTL_SECONDS,
        ):
            return local_user

        response = self.client.get_current_user(access_token)
        if response.success:
            return self._sync_user_payload(response.data, access_token=access_token)

        if response.status_code == 401 and self._refresh_access_token():
            refreshed_token = get_access_token()
            if refreshed_token:
                retry_response = self.client.get_current_user(refreshed_token)
                if retry_response.success:
                    return self._sync_user_payload(
                        retry_response.data, access_token=refreshed_token
                    )
                if retry_response.status_code in {401, 403}:
                    clear_auth_session(store=self.store)
                    return None

        if response.status_code in {401, 403}:
            clear_auth_session(store=self.store)
            return None

        return local_user

    def _refresh_access_token(self) -> bool:
        refresh_token = get_refresh_token()
        if not refresh_token:
            return False

        response = self.client.refresh_token(refresh_token)
        if not response.success or not isinstance(response.data, dict):
            return False

        new_access_token = response.data.get("access_token")
        if not isinstance(new_access_token, str) or not new_access_token:
            return False

        set_auth_tokens(new_access_token, refresh_token)
        return True

    def _handle_token_response(
        self,
        response: ApiResponse,
        *,
        success_message: str,
        password: str,
        last_login: datetime,
    ) -> AuthResult:
        if not response.success:
            return AuthResult(success=False, message=self._extract_error_message(response))

        if not isinstance(response.data, dict):
            return AuthResult(success=False, message="Reponse backend auth invalide.")

        access_token = response.data.get("access_token")
        refresh_token = response.data.get("refresh_token")
        user_data = response.data.get("user")
        if not isinstance(access_token, str) or not access_token:
            return AuthResult(
                success=False, message="Access token manquant dans la reponse backend."
            )
        if not isinstance(refresh_token, str) or not refresh_token:
            return AuthResult(
                success=False, message="Refresh token manquant dans la reponse backend."
            )
        if not isinstance(user_data, dict):
            return AuthResult(
                success=False, message="Utilisateur manquant dans la reponse backend."
            )

        set_auth_tokens(access_token, refresh_token)
        user = sync_current_user_from_backend(
            user_data,
            store=self.store,
            password=password,
            last_login=last_login,
            access_token=access_token,
        )
        return AuthResult(success=True, message=success_message, user=user)

    def _sync_user_payload(
        self, user_data: object, *, access_token: str | None = None
    ) -> MockUser | None:
        if not isinstance(user_data, dict):
            return self._local_user()
        return sync_current_user_from_backend(
            user_data, store=self.store, access_token=access_token
        )

    def _extract_error_message(self, response: ApiResponse) -> str:
        if response.error:
            return response.error

        payload = response.data
        if isinstance(payload, dict):
            detail = payload.get("detail")
            if isinstance(detail, str) and detail:
                return detail
            message = payload.get("message")
            if isinstance(message, str) and message:
                return message
            details = payload.get("details")
            if isinstance(details, list) and details:
                first_error = details[0]
                if isinstance(first_error, dict):
                    detail_message = first_error.get("msg")
                    if isinstance(detail_message, str) and detail_message:
                        return detail_message
        if isinstance(payload, str) and payload.strip():
            return payload.strip()
        if response.status_code == 0:
            return "API auth indisponible."
        return f"Erreur backend ({response.status_code})."

    def _local_user(self) -> MockUser | None:
        if not self.store.current_user_email:
            return None
        return self.store.users.get(self.store.current_user_email.lower())
