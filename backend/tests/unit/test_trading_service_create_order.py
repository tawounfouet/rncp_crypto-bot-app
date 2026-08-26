"""Tests unitaires pour TradingService.create_order."""

from __future__ import annotations

import uuid
from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest
from auth.models import User, UserSettings
from market.clients.base import OrderResult
from strategy.models import StrategyDeployment
from trading.models import Order
from trading.schemas import OrderCreate, OrderSideEnum, OrderTypeEnum
from trading.service import TradingService

# from_user_settings est importe localement dans create_order (import paresseux) :
# il faut patcher le nom sur son module d'origine (market.clients.factory), pas sur
# trading.service, sinon le patch ne matche jamais le nom réellement résolu à l'appel.

def _make_settings(session, user: User, api_keys: dict | None = None) -> UserSettings:
    """Cle "binance" presente par defaut (garde "cles API configurees" satisfaite).

    from_user_settings etant mocke dans les tests qui l'utilisent, le contenu n'a pas
    besoin d'etre une vraie valeur chiffree.
    """
    default_keys = {"binance": {"live": {"api_key": "fake", "api_secret": "fake"}, "active_mode": "live"}}
    settings = UserSettings(id=str(uuid.uuid4()), user_id=user.id, api_keys=api_keys or default_keys)
    session.add(settings)
    session.flush()
    return settings


def _make_order_data(deployment: StrategyDeployment) -> OrderCreate:
    return OrderCreate(
        deployment_id=deployment.id,
        symbol="BTCUSDC",
        order_type=OrderTypeEnum.MARKET,
        side=OrderSideEnum.BUY,
        quantity=Decimal("0.01"),
    )


@pytest.fixture
def mock_from_user_settings():
    with patch("market.clients.factory.from_user_settings") as mock:
        yield mock


@pytest.mark.asyncio
async def test_trading_service_create_order_success(
        patch_db_session,
        make_user,
        make_deployment,
        mock_from_user_settings
    ) -> None:
    user = make_user(patch_db_session)
    deployment = make_deployment(patch_db_session, user)
    _make_settings(patch_db_session, user)
    order_data = _make_order_data(deployment)

    fake_order_result = OrderResult(
        order_id="12345",
        symbol="BTCUSDC",
        side="BUY",
        order_type="MARKET",
        status="FILLED",
        quantity=Decimal("0.01"),
        price=Decimal("50000"),
    )
    mock_client = MagicMock()
    mock_client.place_order.return_value = fake_order_result
    mock_from_user_settings.return_value = mock_client

    service = TradingService(patch_db_session)
    result = await service.create_order(user.id, order_data)

    assert result.status == "FILLED"
    assert result.exchange_order_id == "12345"
    assert result.executed_quantity == Decimal("0.01")

    # patch_db_session est la session elle-meme : on requete a nouveau la table Order
    # avec l'id renvoye par create_order, pour verifier que c'est bien en base
    # (et pas seulement l'objet OrderResponse retourne, deja une copie figee).
    order_in_db = patch_db_session.query(Order).filter(Order.id == result.id).first()
    assert order_in_db.status == "FILLED"
    assert order_in_db.exchange_order_id == "12345"
    assert order_in_db.executed_quantity == Decimal("0.01")


@pytest.mark.asyncio
async def test_trading_service_create_order_without_api_keys(
        patch_db_session,
        make_user,
        make_deployment,
        mock_from_user_settings
    ) -> None:
    user = make_user(patch_db_session)
    deployment = make_deployment(patch_db_session, user)
    _make_settings(patch_db_session, user, api_keys={"kraken": {}})
    order_data = _make_order_data(deployment)

    service = TradingService(patch_db_session)
    result = await service.create_order(user.id, order_data)

    mock_from_user_settings.assert_not_called()
    assert result.status == "REJECTED"


@pytest.mark.asyncio
async def test_trading_service_create_order_invalid_keys(
        patch_db_session,
        make_user,
        make_deployment,
        mock_from_user_settings
    ) -> None:
    user = make_user(patch_db_session)
    deployment = make_deployment(patch_db_session, user)
    _make_settings(patch_db_session, user)
    order_data = _make_order_data(deployment)

    mock_from_user_settings.side_effect = ValueError("Clés API invalides")

    service = TradingService(patch_db_session)
    result = await service.create_order(user.id, order_data)

    assert result.status == "REJECTED"
    order_in_db = patch_db_session.query(Order).filter(Order.id == result.id).first()
    assert order_in_db.status == "REJECTED"


@pytest.mark.asyncio
async def test_trading_service_create_order_tesnet_unvalaible(
        patch_db_session,
        make_user,
        make_deployment,
        mock_from_user_settings
    ) -> None:
    user = make_user(patch_db_session)
    deployment = make_deployment(patch_db_session, user)
    _make_settings(patch_db_session, user)
    order_data = _make_order_data(deployment)

    mock_client = MagicMock()
    mock_client.place_order.side_effect = Exception("Testnet unvalaible")
    mock_from_user_settings.return_value = mock_client

    service = TradingService(patch_db_session)
    result = await service.create_order(user.id, order_data)

    assert result.status == "REJECTED"
    order_in_db = patch_db_session.query(Order).filter(Order.id == result.id).first()
    assert order_in_db.status == "REJECTED"
