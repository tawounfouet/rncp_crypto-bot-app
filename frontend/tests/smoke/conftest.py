"""Fixtures pour les smoke tests: stub du backend HTTP."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from schemas.common import UserRole
from services.auth_api_client import ApiResponse

_STUB_STRATEGIES = [
    {
        "id": "strat_btc",
        "name": "BTC Scalp",
        "strategy_type": "scalping",
        "is_active": True,
        "updated_at": "2024-01-01T00:00:00Z",
        "parameters": {
            "version": 1, "budget_usdc": 1000.0, "max_open_positions": 3,
            "risk_per_trade_pct": 1.0, "take_profit_pct": 3.0, "stop_loss_pct": 2.0,
            "cooldown_seconds": 300,
        },
    },
    {
        "id": "strat_sol",
        "name": "SOL Trend",
        "strategy_type": "trend",
        "is_active": True,
        "updated_at": "2024-01-01T00:00:00Z",
        "parameters": {
            "version": 2, "budget_usdc": 2000.0, "max_open_positions": 3,
            "risk_per_trade_pct": 1.0, "take_profit_pct": 3.0, "stop_loss_pct": 2.0,
            "cooldown_seconds": 300,
        },
    },
]

_STUB_ADMIN_USERS = [
    {
        "id": "u1", "email": "alice@cryptobot.dev", "first_name": "Alice", "last_name": "Martin",
        "is_active": True, "is_admin": False, "last_active_at": "2024-01-01T00:00:00Z",
    },
    {
        "id": "u2", "email": "admin@cryptobot.dev", "first_name": "Admin", "last_name": "Root",
        "is_active": True, "is_admin": True, "last_active_at": "2024-01-01T00:00:00Z",
    },
]

_STUB_TRANSACTIONS = [
    {
        "id": "tx1", "transaction_type": "TRADE", "asset": "BTC", "quote_asset": "USDC",
        "direction": "IN", "price": 45000.0, "amount": 0.1, "fee_amount": 2.5,
        "timestamp": "2024-01-15T10:00:00Z",
    },
    {
        "id": "tx2", "transaction_type": "TRADE", "asset": "ETH", "quote_asset": "USDC",
        "direction": "OUT", "price": 2500.0, "amount": 1.0, "fee_amount": 1.5,
        "timestamp": "2024-01-16T10:00:00Z",
    },
]


def _get_store_user():
    """Lit l'utilisateur courant depuis le session_state Streamlit si disponible."""
    try:
        import streamlit as st
        store = st.session_state.get("app_store")
        email = getattr(store, "current_user_email", None) if store else None
        return (store, store.users.get(email) if (store and email) else None)
    except Exception:
        return (None, None)


def _stub_request(self, method: str, path: str, **kwargs) -> ApiResponse:
    """Route les reponses stub selon le path et la methode."""

    # ── /market/exchanges (public, pas d'auth) ───────────────────────────────
    if "/market/exchanges" in path:
        return ApiResponse(status_code=200, data={
            "data": [
                {"id": "binance", "label": "Binance"},
                {"id": "kraken", "label": "Kraken"},
            ],
        })

    # ── /market/public/prices (public, pas d'auth) ───────────────────────────
    if "/market/public/prices" in path:
        exchange = (kwargs.get("query_params") or {}).get("exchange", "binance")
        # Prix en string : le backend serialise ses champs Decimal en chaine JSON
        # (comme le fait reellement FastAPI/pydantic), pas en nombre natif.
        return ApiResponse(status_code=200, data={
            "data": [
                {"symbol": "BTCUSDC", "exchange": exchange, "price": "65000.0", "as_of": "2024-01-01T00:00:00Z"},
                {"symbol": "ETHUSDC", "exchange": exchange, "price": "3200.0", "as_of": "2024-01-01T00:00:00Z"},
            ],
            "warnings": [],
        })

    # ── /market/public/klines (public, pas d'auth) ───────────────────────────
    if "/market/public/klines" in path:
        exchange = (kwargs.get("query_params") or {}).get("exchange", "binance")
        symbol = (kwargs.get("query_params") or {}).get("symbols", "BTCUSDC")
        interval = (kwargs.get("query_params") or {}).get("interval", "1h")
        return ApiResponse(status_code=200, data={
            "data": [
                {
                    "symbol": symbol, "exchange": exchange, "interval": interval,
                    "open_time": "2024-01-01T00:00:00Z",
                    "open": "100.0", "high": "110.0", "low": "95.0", "close": "105.0", "volume": "12.5",
                },
                {
                    "symbol": symbol, "exchange": exchange, "interval": interval,
                    "open_time": "2024-01-01T01:00:00Z",
                    "open": "105.0", "high": "115.0", "low": "100.0", "close": "108.0", "volume": "9.0",
                },
            ],
            "warnings": [],
        })

    # ── /users/me/settings (GET ou PUT) ──────────────────────────────────────
    if "/users/me/settings" in path:
        _, user = _get_store_user()
        exchange = getattr(user, "exchange", "binance") if user else "binance"
        configured = bool(getattr(user, "exchange_configured", False)) if user else False
        return ApiResponse(
            status_code=200,
            data={"configured_exchanges": [exchange] if configured else []},
        )

    # ── /users/me/api-keys (multi-credential) ────────────────────────────────
    if "/users/me/api-keys" in path and method == "GET":
        _, user = _get_store_user()
        configured = bool(getattr(user, "binance_configured", False)) if user else False
        if not configured:
            return ApiResponse(status_code=200, data=[])
        return ApiResponse(
            status_code=200,
            data=[
                {
                    "id": "cred_binance_1",
                    "exchange": "binance",
                    "label": "Binance Spot principal",
                    "api_key_masked": "AK_****",
                    "created_at": "2024-01-01T00:00:00Z",
                    "is_primary": True,
                }
            ],
        )

    # ── /users/me (GET ou PUT) ────────────────────────────────────────────────
    if "/users/me" in path:
        _, user = _get_store_user()
        if user:
            # Pour un PUT, le payload peut contenir un nouvel email
            payload = kwargs.get("json_body") or {}
            email = payload.get("email") or user.email
            first_name = payload.get("first_name") or user.first_name
            last_name = payload.get("last_name", user.last_name)
            is_admin = user.role == UserRole.ADMIN
            return ApiResponse(status_code=200, data={
                "id": getattr(user, "id", "u1"),
                "email": email,
                "first_name": first_name,
                "last_name": last_name,
                "is_active": True,
                "is_admin": is_admin,
            })
        return ApiResponse(status_code=200, data={
            "id": "u1", "email": "alice@cryptobot.dev",
            "first_name": "Alice", "last_name": "Martin",
            "is_active": True, "is_admin": False,
        })

    # ── /users/{id}/activate|deactivate ──────────────────────────────────────
    if "/users/" in path and ("activate" in path or "deactivate" in path):
        return ApiResponse(status_code=200, data={"message": "ok"})

    # ── /users/ (liste admin) ─────────────────────────────────────────────────
    if "/users" in path and method == "GET":
        return ApiResponse(status_code=200, data=_STUB_ADMIN_USERS)

    # ── /strategies/available-models ──────────────────────────────────────────
    if "/strategies/available-models" in path:
        return ApiResponse(status_code=200, data={
            "data": [
                {"name": "random_forest", "path": "artifacts/registry/random_forest/best", "available": True},
                {"name": "lstm", "path": "artifacts/registry/lstm/best", "available": False},
            ]
        })

    # ── /strategies/deployments ───────────────────────────────────────────────
    if "/strategies/deployments" in path:
        return ApiResponse(status_code=200, data=[])

    # ── /strategies/{id} et /strategies/ ─────────────────────────────────────
    if "/strategies" in path:
        parts = path.rstrip("/").split("/")
        last = parts[-1]
        if method == "PUT" and last not in ("", "strategies"):
            # Update strategy: retourne la strategie telle quelle
            for s in _STUB_STRATEGIES:
                if s["id"] == last:
                    updated = dict(s)
                    payload = kwargs.get("json_body") or {}
                    if "parameters" in payload:
                        updated["parameters"] = {**updated["parameters"], **payload["parameters"]}
                    return ApiResponse(status_code=200, data=updated)
        if last not in ("", "strategies") and not last.startswith("strat_"):
            pass  # pas un ID connu, fall through
        elif last not in ("", "strategies"):
            for s in _STUB_STRATEGIES:
                if s["id"] == last:
                    return ApiResponse(status_code=200, data=s)
        return ApiResponse(status_code=200, data=_STUB_STRATEGIES)

    # ── /trading/portfolio ────────────────────────────────────────────────────
    if "/trading/portfolio" in path:
        return ApiResponse(status_code=200, data={
            "total_usd_value": 10000.0,
            "balances": [
                {"asset": "USDC", "available": 5000.0, "locked": 0.0, "usd_value": 5000.0},
                {"asset": "BTC", "available": 0.1, "locked": 0.0, "usd_value": 4500.0},
            ],
        })

    # ── /trading/orders ───────────────────────────────────────────────────────
    if "/trading/orders" in path:
        return ApiResponse(status_code=200, data=[])

    # ── /trading/transactions ─────────────────────────────────────────────────
    if "/trading/transactions" in path:
        return ApiResponse(status_code=200, data=_STUB_TRANSACTIONS)

    # ── /trading/stats ────────────────────────────────────────────────────────
    if "/trading/stats" in path:
        return ApiResponse(status_code=200, data={
            "total_trades": 10, "total_profit_loss": 250.0,
            "win_rate": 0.6, "max_drawdown": 0.05,
        })

    return ApiResponse(status_code=200, data={})


@pytest.fixture(autouse=True)
def stub_backend():
    """Intercepte tous les appels HTTP du BackendApiClient pendant les smoke tests."""
    with patch("services.auth_api_client.AuthApiClient._request", _stub_request):
        yield
