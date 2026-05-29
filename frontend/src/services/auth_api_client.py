"""HTTP client for the backend authentication endpoints."""

from __future__ import annotations

import json
import os
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any
from urllib import error, parse, request

DEFAULT_TIMEOUT_SECONDS = 30
API_PREFIX = "/api/v1"


@dataclass
class ApiResponse:
    status_code: int
    data: Any = None
    error: str | None = None
    headers: Mapping[str, str] | None = None

    @property
    def success(self) -> bool:
        return self.error is None and self.status_code < 400


class AuthApiClient:
    """Thin client over the existing FastAPI auth endpoints."""

    def __init__(self, base_url: str | None = None, timeout: int = DEFAULT_TIMEOUT_SECONDS) -> None:
        resolved_base_url = (base_url or os.getenv("API_URL", "http://localhost:8009")).rstrip("/")
        self.base_url = resolved_base_url
        self.timeout = timeout

    def register(
        self,
        *,
        email: str,
        username: str,
        password: str,
        first_name: str | None = None,
        last_name: str | None = None,
    ) -> ApiResponse:
        payload: dict[str, Any] = {
            "email": email,
            "username": username,
            "password": password,
        }
        if first_name:
            payload["first_name"] = first_name
        if last_name:
            payload["last_name"] = last_name
        return self._request("POST", f"{API_PREFIX}/auth/register", json_body=payload)

    def login_json(self, *, username: str, password: str) -> ApiResponse:
        return self._request(
            "POST",
            f"{API_PREFIX}/auth/login/json",
            json_body={"username": username, "password": password},
        )

    def login_form(self, *, username: str, password: str) -> ApiResponse:
        return self._request(
            "POST",
            f"{API_PREFIX}/auth/login",
            form_body={"username": username, "password": password},
        )

    def refresh_token(self, refresh_token: str) -> ApiResponse:
        return self._request(
            "POST",
            f"{API_PREFIX}/auth/refresh",
            query_params={"refresh_token": refresh_token},
        )

    def logout(self, refresh_token: str) -> ApiResponse:
        return self._request(
            "POST",
            f"{API_PREFIX}/auth/logout",
            query_params={"refresh_token": refresh_token},
        )

    def get_current_user(self, access_token: str) -> ApiResponse:
        return self._request(
            "GET",
            f"{API_PREFIX}/users/me",
            access_token=access_token,
        )

    def _request(
        self,
        method: str,
        path: str,
        *,
        json_body: Mapping[str, Any] | None = None,
        form_body: Mapping[str, str] | None = None,
        query_params: Mapping[str, str] | None = None,
        access_token: str | None = None,
    ) -> ApiResponse:
        url = self._build_url(path, query_params)
        body: bytes | None = None
        headers = {"Accept": "application/json"}

        if json_body is not None:
            body = json.dumps(dict(json_body)).encode("utf-8")
            headers["Content-Type"] = "application/json"
        elif form_body is not None:
            body = parse.urlencode(dict(form_body)).encode("utf-8")
            headers["Content-Type"] = "application/x-www-form-urlencoded"

        if access_token:
            headers["Authorization"] = f"Bearer {access_token}"

        http_request = request.Request(url=url, data=body, headers=headers, method=method.upper())

        try:
            with request.urlopen(http_request, timeout=self.timeout) as response:
                raw_payload = response.read().decode("utf-8")
                return ApiResponse(
                    status_code=response.status,
                    data=self._decode_payload(raw_payload),
                    headers=dict(response.headers.items()),
                )
        except error.HTTPError as exc:
            raw_payload = exc.read().decode("utf-8")
            return ApiResponse(
                status_code=exc.code,
                data=self._decode_payload(raw_payload),
                headers=dict(exc.headers.items()),
            )
        except error.URLError as exc:
            return ApiResponse(status_code=0, error=f"Connexion API impossible: {exc.reason}")
        except Exception as exc:  # pragma: no cover
            return ApiResponse(status_code=0, error=f"Erreur client auth: {exc}")

    def _build_url(self, path: str, query_params: Mapping[str, str] | None = None) -> str:
        url = f"{self.base_url}{path}"
        if not query_params:
            return url
        return f"{url}?{parse.urlencode(dict(query_params))}"

    @staticmethod
    def _decode_payload(raw_payload: str) -> Any:
        if not raw_payload:
            return None
        try:
            return json.loads(raw_payload)
        except json.JSONDecodeError:
            return raw_payload
