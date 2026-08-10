"""Tests unitaires pour TradingService.cancel_order."""

from __future__ import annotations

import uuid
from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest
from auth.models import User, UserSettings
from market.clients.base import OrderResult
from shared.core.exceptions import BusinessLogicError
from trading.models import Order
from trading.service import TradingService

# from_user_settings est importe localement dans create_order (import paresseux) :
# il faut patcher le nom sur son module d'origine (market.clients.factory), pas sur
# trading.service, sinon le patch ne matche jamais le nom réellement résolu à l'appel.

def _make_order(session, deployment, status="NEW", exchange_order_id="12345") -> Order:
    order = Order(
        id=str(uuid.uuid4()),
        deployment_id=deployment.id,
        user_id=deployment.user_id,
        exchange=deployment.exchange,
        symbol=deployment.symbol,
        order_type="MARKET",
        side="BUY",
        quantity=Decimal("0.01"),
        status=status,
        exchange_order_id=exchange_order_id,
    )
    session.add(order)
    session.flush()
    return order


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

@pytest.fixture
def mock_from_user_settings():
    with patch("market.clients.factory.from_user_settings") as mock:
        yield mock

@pytest.mark.asyncio
async def test_trading_service_cancel_order_success(
    patch_db_session,
    make_user,
    make_deployment,
    mock_from_user_settings
) -> None:
    user = make_user(patch_db_session)
    deployment = make_deployment(patch_db_session, user)
    _make_settings(patch_db_session, user)
    order = _make_order(patch_db_session, deployment)

    mock_client = MagicMock()
    fake_order_result = OrderResult(
        order_id="12345", symbol="BTCUSDC", side="BUY", order_type="MARKET",
        status="CANCELED", quantity=Decimal("0.01"),
    )
    mock_client.cancel_order.return_value = fake_order_result
    mock_from_user_settings.return_value = mock_client

    service = TradingService(patch_db_session)
    result = await service.cancel_order(order.id, user.id)

    assert result is True

    # patch_db_session est la session elle-meme : on requete a nouveau la table Order
    # avec l'id renvoye par create_order, pour verifier que c'est bien en base
    # (et pas seulement l'objet OrderResponse retourne, deja une copie figee).
    order_in_db = patch_db_session.query(Order).filter(Order.id == order.id).first()
    assert order_in_db.status == "CANCELED"



@pytest.mark.asyncio
async def test_trading_service_cancel_order_without_api_keys(
    patch_db_session,
    make_user,
    make_deployment,
    mock_from_user_settings
) -> None:
    user = make_user(patch_db_session)
    deployment = make_deployment(patch_db_session, user)
    _make_settings(patch_db_session, user, api_keys={"kraken": {}})
    order = _make_order(patch_db_session, deployment)

    service = TradingService(patch_db_session)

    with pytest.raises(BusinessLogicError):
        await service.cancel_order(order.id, user.id)

    mock_from_user_settings.assert_not_called()

@pytest.mark.asyncio
async def test_trading_service_cancel_order_invalid_keys(
    patch_db_session,
    make_user,
    make_deployment,
    mock_from_user_settings
) -> None:
    user = make_user(patch_db_session)
    deployment = make_deployment(patch_db_session, user)
    _make_settings(patch_db_session, user)
    order = _make_order(patch_db_session, deployment)

    mock_from_user_settings.side_effect = ValueError("Clés API invalides")

    service = TradingService(patch_db_session)

    with pytest.raises(BusinessLogicError):
        await service.cancel_order(order.id, user.id)


@pytest.mark.asyncio
async def test_trading_service_cancel_order_exchange_exception(
    patch_db_session,
    make_user,
    make_deployment,
    mock_from_user_settings
) -> None:
    user = make_user(patch_db_session)
    deployment = make_deployment(patch_db_session, user)
    _make_settings(patch_db_session, user)
    order = _make_order(patch_db_session, deployment)

    mock_client = MagicMock()
    mock_client.cancel_order.side_effect = Exception("Testnet unvalaible")
    mock_from_user_settings.return_value = mock_client

    service = TradingService(patch_db_session)

    with pytest.raises(BusinessLogicError):
        await service.cancel_order(order.id, user.id)

    mock_from_user_settings.assert_called_once()

    order_in_db = patch_db_session.query(Order).filter(Order.id == order.id).first()
    assert order_in_db.status == "NEW"
