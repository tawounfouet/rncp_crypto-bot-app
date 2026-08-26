"""Tests unitaires pour les routes de strategy/router.py (hors execute-active,
deja couvert par test_strategy_router_execute_active.py).

Le service est entierement mocke via app.dependency_overrides -- ces tests
verifient le cablage HTTP (routes, codes de statut, mapping des exceptions),
pas la logique metier (deja couverte par les tests de service).
"""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest
from auth.dependencies import get_current_user
from fastapi import FastAPI
from fastapi.testclient import TestClient
from shared.core.exceptions import BusinessLogicError, NotFoundError, ValidationError
from strategy.router import get_strategy_service, router
from strategy.schemas import StrategyResponse


@pytest.fixture
def fake_user() -> MagicMock:
    return MagicMock(id="user-1")


@pytest.fixture
def client(fake_user: MagicMock) -> TestClient:
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_current_user] = lambda: fake_user
    return TestClient(app)


def _fake_strategy(strategy_id: str = "strat-1") -> StrategyResponse:
    now = datetime.now(UTC)
    return StrategyResponse(
        id=strategy_id,
        user_id="user-1",
        name="Bot test",
        description=None,
        strategy_type="ml_random_forest",
        asset_class="crypto",
        is_public=False,
        is_active=True,
        version="1.0",
        created_at=now,
        updated_at=now,
        parameters={},
        parameter_hash=None,
    )


def _fake_deployment(deployment_id: str = "dep-1", strategy_id: str = "strat-1") -> dict:
    now = datetime.now(UTC).isoformat()
    return {
        "id": deployment_id,
        "strategy_id": strategy_id,
        "user_id": "user-1",
        "exchange": "binance",
        "symbol": "BTCUSDC",
        "timeframe": "1h",
        "amount": "100",
        "parameters": {},
        "status": "active",
        "start_time": now,
        "end_time": None,
        "created_at": now,
        "updated_at": now,
    }


def _override_service(client: TestClient, fake_service: MagicMock) -> None:
    client.app.dependency_overrides[get_strategy_service] = lambda: fake_service


# ---------------------------------------------------------------------------
# GET /strategies/available (pas d'auth)
# ---------------------------------------------------------------------------


def test_get_available_strategies_returns_200(client: TestClient) -> None:
    fake_service = MagicMock()
    fake_service.get_available_strategies.return_value = {"ml_random_forest": {"available": True}}
    _override_service(client, fake_service)

    response = client.get("/strategies/available")

    assert response.status_code == 200
    assert response.json() == {"ml_random_forest": {"available": True}}


# ---------------------------------------------------------------------------
# GET /strategies/
# ---------------------------------------------------------------------------


def test_get_user_strategies_returns_200(client: TestClient) -> None:
    fake_service = MagicMock()
    fake_service.get_user_strategies = AsyncMock(return_value=[_fake_strategy()])
    _override_service(client, fake_service)

    response = client.get("/strategies/")

    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert len(data["data"]) == 1
    assert data["data"][0]["id"] == "strat-1"


# ---------------------------------------------------------------------------
# POST /strategies/
# ---------------------------------------------------------------------------


def test_create_strategy_returns_200(client: TestClient) -> None:
    fake_service = MagicMock()
    fake_service.create_strategy = AsyncMock(return_value=_fake_strategy())
    _override_service(client, fake_service)

    response = client.post(
        "/strategies/",
        json={
            "name": "Bot test",
            "strategy_type": "ml_random_forest",
            "asset_class": "crypto",
            "parameters": {},
        },
    )

    assert response.status_code == 200
    assert response.json()["data"]["id"] == "strat-1"


def test_create_strategy_returns_400_on_validation_error(client: TestClient) -> None:
    fake_service = MagicMock()
    fake_service.create_strategy = AsyncMock(side_effect=ValidationError("Invalid parameters"))
    _override_service(client, fake_service)

    response = client.post(
        "/strategies/",
        json={
            "name": "Bot test",
            "strategy_type": "ml_random_forest",
            "asset_class": "crypto",
            "parameters": {},
        },
    )

    assert response.status_code == 400


# ---------------------------------------------------------------------------
# GET /strategies/{strategy_id}
# ---------------------------------------------------------------------------


def test_get_strategy_returns_200(client: TestClient) -> None:
    fake_service = MagicMock()
    fake_service.get_user_strategies = AsyncMock(return_value=[_fake_strategy("strat-1")])
    _override_service(client, fake_service)

    response = client.get("/strategies/strat-1")

    assert response.status_code == 200
    assert response.json()["data"]["id"] == "strat-1"


def test_get_strategy_returns_404_when_not_found(client: TestClient) -> None:
    fake_service = MagicMock()
    fake_service.get_user_strategies = AsyncMock(return_value=[_fake_strategy("other-strat")])
    _override_service(client, fake_service)

    response = client.get("/strategies/strat-1")

    assert response.status_code == 404


# ---------------------------------------------------------------------------
# PUT /strategies/{strategy_id}
# ---------------------------------------------------------------------------


def test_update_strategy_returns_200(client: TestClient) -> None:
    fake_service = MagicMock()
    fake_service.update_strategy = AsyncMock(return_value=_fake_strategy())
    _override_service(client, fake_service)

    response = client.put("/strategies/strat-1", json={"name": "Nouveau nom"})

    assert response.status_code == 200
    assert response.json()["data"]["id"] == "strat-1"


def test_update_strategy_returns_404_when_not_found(client: TestClient) -> None:
    fake_service = MagicMock()
    fake_service.update_strategy = AsyncMock(side_effect=NotFoundError("Strategy not found"))
    _override_service(client, fake_service)

    response = client.put("/strategies/strat-1", json={"name": "Nouveau nom"})

    assert response.status_code == 404


# ---------------------------------------------------------------------------
# DELETE /strategies/{strategy_id}
# ---------------------------------------------------------------------------


def test_delete_strategy_returns_200(client: TestClient) -> None:
    fake_service = MagicMock()
    fake_service.get_user_deployments = AsyncMock(return_value=[])
    fake_service.update_strategy = AsyncMock(return_value=_fake_strategy())
    _override_service(client, fake_service)

    response = client.delete("/strategies/strat-1")

    assert response.status_code == 200
    assert response.json()["success"] is True


def test_delete_strategy_returns_400_when_active_deployments_exist(client: TestClient) -> None:
    fake_service = MagicMock()
    fake_service.get_user_deployments = AsyncMock(
        return_value=[MagicMock(strategy_id="strat-1")]
    )
    _override_service(client, fake_service)

    response = client.delete("/strategies/strat-1")

    assert response.status_code == 400


# ---------------------------------------------------------------------------
# POST /strategies/{strategy_id}/deploy
# ---------------------------------------------------------------------------


def test_deploy_strategy_returns_200(client: TestClient) -> None:
    fake_service = MagicMock()
    fake_service.deploy_strategy = AsyncMock(return_value=_fake_deployment())
    _override_service(client, fake_service)

    response = client.post(
        "/strategies/strat-1/deploy",
        json={
            "strategy_id": "strat-1",
            "exchange": "binance",
            "symbol": "BTCUSDC",
            "timeframe": "1h",
            "amount": "100",
        },
    )

    assert response.status_code == 200
    assert response.json()["data"]["id"] == "dep-1"


def test_deploy_strategy_returns_400_on_business_logic_error(client: TestClient) -> None:
    fake_service = MagicMock()
    fake_service.deploy_strategy = AsyncMock(
        side_effect=BusinessLogicError("Active deployment already exists")
    )
    _override_service(client, fake_service)

    response = client.post(
        "/strategies/strat-1/deploy",
        json={
            "strategy_id": "strat-1",
            "exchange": "binance",
            "symbol": "BTCUSDC",
            "timeframe": "1h",
            "amount": "100",
        },
    )

    assert response.status_code == 400


# ---------------------------------------------------------------------------
# GET /strategies/deployments/
# ---------------------------------------------------------------------------


def test_get_user_deployments_returns_200(client: TestClient) -> None:
    fake_service = MagicMock()
    fake_service.get_user_deployments = AsyncMock(return_value=[_fake_deployment()])
    _override_service(client, fake_service)

    response = client.get("/strategies/deployments/")

    assert response.status_code == 200
    assert len(response.json()["data"]) == 1


# ---------------------------------------------------------------------------
# POST /strategies/deployments/{deployment_id}/stop
# ---------------------------------------------------------------------------


def test_stop_deployment_returns_200(client: TestClient) -> None:
    fake_service = MagicMock()
    fake_service.stop_deployment.return_value = _fake_deployment(deployment_id="dep-1")
    _override_service(client, fake_service)

    response = client.post("/strategies/deployments/dep-1/stop")

    assert response.status_code == 200
    assert response.json()["data"]["id"] == "dep-1"


def test_stop_deployment_returns_404_when_not_found(client: TestClient) -> None:
    fake_service = MagicMock()
    fake_service.stop_deployment.side_effect = NotFoundError("Deployment not found")
    _override_service(client, fake_service)

    response = client.post("/strategies/deployments/dep-1/stop")

    assert response.status_code == 404


# ---------------------------------------------------------------------------
# POST /strategies/validate (pas d'auth)
# ---------------------------------------------------------------------------


def test_validate_strategy_parameters_returns_200_when_valid(client: TestClient) -> None:
    fake_service = MagicMock()
    fake_service.validate_strategy_parameters = AsyncMock(return_value=(True, None))
    _override_service(client, fake_service)

    response = client.post(
        "/strategies/validate",
        params={"strategy_type": "ml_random_forest"},
        json={},
    )

    assert response.status_code == 200
    assert response.json()["success"] is True


def test_validate_strategy_parameters_returns_200_with_success_false_when_invalid(
    client: TestClient,
) -> None:
    fake_service = MagicMock()
    fake_service.validate_strategy_parameters = AsyncMock(return_value=(False, "Missing field"))
    _override_service(client, fake_service)

    response = client.post(
        "/strategies/validate",
        params={"strategy_type": "ml_random_forest"},
        json={},
    )

    assert response.status_code == 200
    assert response.json()["success"] is False


# ---------------------------------------------------------------------------
# POST /strategies/deployments/execute-active (pas d'auth)
# ---------------------------------------------------------------------------


def test_execute_active_deployments_returns_200_without_auth(client: TestClient) -> None:
    fake_service = MagicMock()
    fake_service.execute_active_deployments = AsyncMock(
        return_value=[{"deployment_id": "dep-1", "action": "hold"}]
    )
    _override_service(client, fake_service)

    response = client.post("/strategies/deployments/execute-active")

    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["data"] == [{"deployment_id": "dep-1", "action": "hold"}]


def test_execute_active_deployments_returns_500_on_service_error(client: TestClient) -> None:
    fake_service = MagicMock()
    fake_service.execute_active_deployments = AsyncMock(side_effect=Exception("boom"))
    _override_service(client, fake_service)

    response = client.post("/strategies/deployments/execute-active")

    assert response.status_code == 500


# ---------------------------------------------------------------------------
# GET /strategies/available-models
# ---------------------------------------------------------------------------


def test_get_available_models_returns_200(client: TestClient) -> None:
    fake_service = MagicMock()
    fake_service.get_available_models.return_value = [
        {"name": "random_forest", "path": "/registry/rf/best", "available": True},
        {"name": "lstm", "path": "/registry/lstm/best", "available": False},
    ]
    _override_service(client, fake_service)

    response = client.get("/strategies/available-models")

    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert len(data["data"]) == 2
    assert data["data"][0] == {"name": "random_forest", "path": "/registry/rf/best", "available": True}


def test_get_available_models_returns_502_on_ml_api_error(client: TestClient) -> None:
    fake_service = MagicMock()
    fake_service.get_available_models.side_effect = Exception("ml-api unreachable")
    _override_service(client, fake_service)

    response = client.get("/strategies/available-models")

    assert response.status_code == 502
