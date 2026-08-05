"""Tests unitaires pour BackendApiClient : verifient le cablage HTTP (methode,
chemin, query params, payload JSON) de chaque endpoint, via mock de `_request`.

Ne testent pas la logique de `_request`/`AuthApiClient` elle-meme (deja
implicitement exercee par les scenarios de smoke test), seulement que chaque
methode de BackendApiClient construit le bon appel.
"""

from __future__ import annotations

from unittest.mock import patch

from services.api_client import BackendApiClient
from services.auth_api_client import ApiResponse

TOKEN = "token-123"


def _ok(data: object) -> ApiResponse:
    return ApiResponse(status_code=200, data=data)


# ─── Users ───────────────────────────────────────────────────────────────


def test_update_user_sends_only_provided_fields() -> None:
    client = BackendApiClient()

    with patch.object(client, "_request", return_value=_ok({})) as mock_request:
        client.update_user(TOKEN, first_name="Ada", email="ada@test.dev")

    mock_request.assert_called_once_with(
        "PUT",
        "/api/v1/users/me",
        json_body={"first_name": "Ada", "email": "ada@test.dev"},
        access_token=TOKEN,
    )


def test_get_user_settings_calls_correct_endpoint() -> None:
    client = BackendApiClient()

    with patch.object(client, "_request", return_value=_ok({})) as mock_request:
        client.get_user_settings(TOKEN)

    mock_request.assert_called_once_with(
        "GET",
        "/api/v1/users/me/settings",
        access_token=TOKEN,
    )


def test_update_user_settings_sends_only_provided_fields() -> None:
    client = BackendApiClient()

    with patch.object(client, "_request", return_value=_ok({})) as mock_request:
        client.update_user_settings(TOKEN, exchange="binance", mode="live")

    mock_request.assert_called_once_with(
        "PUT",
        "/api/v1/users/me/settings",
        json_body={"exchange": "binance", "mode": "live"},
        access_token=TOKEN,
    )


def test_list_users_calls_correct_endpoint() -> None:
    client = BackendApiClient()

    with patch.object(client, "_request", return_value=_ok([])) as mock_request:
        client.list_users(TOKEN)

    mock_request.assert_called_once_with("GET", "/api/v1/users/", access_token=TOKEN)


def test_get_user_by_id_calls_correct_endpoint() -> None:
    client = BackendApiClient()

    with patch.object(client, "_request", return_value=_ok({})) as mock_request:
        client.get_user_by_id(TOKEN, "user-1")

    mock_request.assert_called_once_with("GET", "/api/v1/users/user-1", access_token=TOKEN)


def test_activate_user_calls_correct_endpoint() -> None:
    client = BackendApiClient()

    with patch.object(client, "_request", return_value=_ok({})) as mock_request:
        client.activate_user(TOKEN, "user-1")

    mock_request.assert_called_once_with("POST", "/api/v1/users/user-1/activate", access_token=TOKEN)


def test_deactivate_user_calls_correct_endpoint() -> None:
    client = BackendApiClient()

    with patch.object(client, "_request", return_value=_ok({})) as mock_request:
        client.deactivate_user(TOKEN, "user-1")

    mock_request.assert_called_once_with("POST", "/api/v1/users/user-1/deactivate", access_token=TOKEN)


# ─── Trading ─────────────────────────────────────────────────────────────


def test_get_portfolio_without_exchange_omits_query_params() -> None:
    client = BackendApiClient()

    with patch.object(client, "_request", return_value=_ok({})) as mock_request:
        client.get_portfolio(TOKEN)

    mock_request.assert_called_once_with(
        "GET",
        "/api/v1/trading/portfolio",
        query_params=None,
        access_token=TOKEN,
    )


def test_get_portfolio_with_exchange_sets_query_params() -> None:
    client = BackendApiClient()

    with patch.object(client, "_request", return_value=_ok({})) as mock_request:
        client.get_portfolio(TOKEN, exchange="binance")

    mock_request.assert_called_once_with(
        "GET",
        "/api/v1/trading/portfolio",
        query_params={"exchange": "binance"},
        access_token=TOKEN,
    )


def test_list_orders_default_params() -> None:
    client = BackendApiClient()

    with patch.object(client, "_request", return_value=_ok([])) as mock_request:
        client.list_orders(TOKEN)

    mock_request.assert_called_once_with(
        "GET",
        "/api/v1/trading/orders",
        query_params={"limit": "50"},
        access_token=TOKEN,
    )


def test_list_orders_with_status_filter() -> None:
    client = BackendApiClient()

    with patch.object(client, "_request", return_value=_ok([])) as mock_request:
        client.list_orders(TOKEN, status="FILLED", limit=10)

    mock_request.assert_called_once_with(
        "GET",
        "/api/v1/trading/orders",
        query_params={"limit": "10", "status": "FILLED"},
        access_token=TOKEN,
    )


def test_cancel_order_calls_correct_endpoint() -> None:
    client = BackendApiClient()

    with patch.object(client, "_request", return_value=_ok({})) as mock_request:
        client.cancel_order(TOKEN, "order-1")

    mock_request.assert_called_once_with("DELETE", "/api/v1/trading/orders/order-1", access_token=TOKEN)


def test_get_trading_stats_default_period() -> None:
    client = BackendApiClient()

    with patch.object(client, "_request", return_value=_ok({})) as mock_request:
        client.get_trading_stats(TOKEN)

    mock_request.assert_called_once_with(
        "GET",
        "/api/v1/trading/stats",
        query_params={"period": "30d"},
        access_token=TOKEN,
    )


def test_list_transactions_default_limit() -> None:
    client = BackendApiClient()

    with patch.object(client, "_request", return_value=_ok([])) as mock_request:
        client.list_transactions(TOKEN)

    mock_request.assert_called_once_with(
        "GET",
        "/api/v1/trading/transactions",
        query_params={"limit": "100"},
        access_token=TOKEN,
    )


# ─── Strategies ──────────────────────────────────────────────────────────


def test_list_strategies_calls_correct_endpoint() -> None:
    client = BackendApiClient()

    with patch.object(client, "_request", return_value=_ok([])) as mock_request:
        client.list_strategies(TOKEN)

    mock_request.assert_called_once_with("GET", "/api/v1/strategies/", access_token=TOKEN)


def test_get_strategy_calls_correct_endpoint() -> None:
    client = BackendApiClient()

    with patch.object(client, "_request", return_value=_ok({})) as mock_request:
        client.get_strategy(TOKEN, "strat-1")

    mock_request.assert_called_once_with("GET", "/api/v1/strategies/strat-1", access_token=TOKEN)


def test_update_strategy_sends_payload_as_is() -> None:
    client = BackendApiClient()
    payload = {"name": "Bot test", "is_active": False}

    with patch.object(client, "_request", return_value=_ok({})) as mock_request:
        client.update_strategy(TOKEN, "strat-1", payload)

    mock_request.assert_called_once_with(
        "PUT",
        "/api/v1/strategies/strat-1",
        json_body=payload,
        access_token=TOKEN,
    )


def test_list_deployments_without_filter_omits_query_params() -> None:
    client = BackendApiClient()

    with patch.object(client, "_request", return_value=_ok([])) as mock_request:
        client.list_deployments(TOKEN)

    mock_request.assert_called_once_with(
        "GET",
        "/api/v1/strategies/deployments/",
        query_params=None,
        access_token=TOKEN,
    )


def test_list_deployments_active_only_sets_query_params() -> None:
    client = BackendApiClient()

    with patch.object(client, "_request", return_value=_ok([])) as mock_request:
        client.list_deployments(TOKEN, active_only=True)

    mock_request.assert_called_once_with(
        "GET",
        "/api/v1/strategies/deployments/",
        query_params={"active_only": "true"},
        access_token=TOKEN,
    )


def test_stop_deployment_calls_correct_endpoint() -> None:
    client = BackendApiClient()

    with patch.object(client, "_request", return_value=_ok({})) as mock_request:
        client.stop_deployment(TOKEN, "dep-1")

    mock_request.assert_called_once_with(
        "POST",
        "/api/v1/strategies/deployments/dep-1/stop",
        access_token=TOKEN,
    )


def test_get_available_models_calls_correct_endpoint() -> None:
    client = BackendApiClient()
    fake_models = [
        {"name": "random_forest", "path": "/registry/rf/best", "available": True},
        {"name": "lstm", "path": "/registry/lstm/best", "available": False},
    ]

    with patch.object(client, "_request", return_value=_ok(fake_models)) as mock_request:
        response = client.get_available_models(TOKEN)

    mock_request.assert_called_once_with(
        "GET",
        "/api/v1/strategies/available-models",
        access_token=TOKEN,
    )
    assert response.success
    assert response.data == fake_models


def test_deploy_strategy_calls_correct_endpoint_with_payload() -> None:
    client = BackendApiClient()

    with patch.object(client, "_request", return_value=_ok({"id": "dep-1"})) as mock_request:
        response = client.deploy_strategy(
            TOKEN,
            "strat-1",
            exchange="binance",
            symbol="BTCUSDT",
            timeframe="1h",
            amount="100",
        )

    mock_request.assert_called_once_with(
        "POST",
        "/api/v1/strategies/strat-1/deploy",
        json_body={
            "strategy_id": "strat-1",
            "exchange": "binance",
            "symbol": "BTCUSDT",
            "timeframe": "1h",
            "amount": "100",
            "is_paper": True,
        },
        access_token=TOKEN,
    )
    assert response.success
    assert response.data == {"id": "dep-1"}


# ─── Marche public (pas d'authentification) ────────────────────────────────


def test_get_public_exchanges_calls_correct_endpoint_without_token() -> None:
    client = BackendApiClient()

    with patch.object(client, "_request", return_value=_ok([])) as mock_request:
        client.get_public_exchanges()

    mock_request.assert_called_once_with("GET", "/api/v1/market/exchanges")


def test_get_public_prices_without_symbols() -> None:
    client = BackendApiClient()

    with patch.object(client, "_request", return_value=_ok({})) as mock_request:
        client.get_public_prices(exchange="binance")

    mock_request.assert_called_once_with(
        "GET",
        "/api/v1/market/public/prices",
        query_params={"exchange": "binance"},
    )


def test_get_public_prices_with_symbols_joins_them() -> None:
    client = BackendApiClient()

    with patch.object(client, "_request", return_value=_ok({})) as mock_request:
        client.get_public_prices(exchange="binance", symbols=["BTCUSDT", "ETHUSDT"])

    mock_request.assert_called_once_with(
        "GET",
        "/api/v1/market/public/prices",
        query_params={"exchange": "binance", "symbols": "BTCUSDT,ETHUSDT"},
    )


def test_get_public_klines_default_params() -> None:
    client = BackendApiClient()

    with patch.object(client, "_request", return_value=_ok({})) as mock_request:
        client.get_public_klines(exchange="binance", symbol="BTCUSDT")

    mock_request.assert_called_once_with(
        "GET",
        "/api/v1/market/public/klines",
        query_params={
            "exchange": "binance",
            "symbols": "BTCUSDT",
            "interval": "1h",
            "limit": "24",
        },
    )
