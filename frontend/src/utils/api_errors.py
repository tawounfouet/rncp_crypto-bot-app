"""Extraction d'un message d'erreur lisible depuis une ApiResponse backend."""

from __future__ import annotations

from services.auth_api_client import ApiResponse


def extract_error(response: ApiResponse) -> str:
    if response.error:
        return response.error
    data = response.data
    if isinstance(data, dict):
        detail = data.get("detail")
        if isinstance(detail, str) and detail:
            return detail
    return f"Erreur backend ({response.status_code})."
