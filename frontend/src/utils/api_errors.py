"""Extraction d'un message d'erreur lisible depuis une ApiResponse backend."""

from __future__ import annotations

from services.auth_api_client import ApiResponse


def extract_error(response: ApiResponse) -> str:
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
        return "API indisponible."
    return f"Erreur backend ({response.status_code})."
