"""Integration tests for immutable bot templates and user bot instances."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from pydantic import ValidationError


def _create_user() -> str:
    from auth.schemas import UserCreate
    from auth.user_service import UserService

    user = UserService().create_user(
        UserCreate(
            email="bot-user@example.com",
            username="botuser",
            password="SecurePass123!",  # noqa: S106
        )
    )
    return user.id


def _grant_binance_credentials(session, user_id: str, monkeypatch) -> None:
    """Configure des cles binance (live) via le systeme multi-credential reel,
    a la place de l'ancien TESTNET_CREDENTIAL_KEY du Binance Testnet lab.

    EXCHANGE_ENC_KEY n'est jamais defini globalement (cf. les autres tests
    d'integration/unitaires de ce depot) -- chaque test qui chiffre des
    identifiants le pose lui-meme via monkeypatch."""
    import base64
    import os

    from auth.models import UserSettings

    monkeypatch.setenv("EXCHANGE_ENC_KEY", base64.b64encode(os.urandom(32)).decode())
    settings = session.query(UserSettings).filter(UserSettings.user_id == user_id).first()
    settings.set_api_credentials("binance", "AK_TEST_PUBLIC_1234", "AS_TEST_SECRET_9876", mode="live")
    session.flush()


def _republish_template(monkeypatch, slug: str) -> None:
    """Republie temporairement un template desactive (ai-rsi-btcusdt-1h-v1, ai-trend-
    ethusdt-4h-v1 -- masques du catalogue par defaut depuis le 2026-08-28, cf.
    DEFAULT_BOT_TEMPLATES) pour que create_user_bot() accepte de creer une instance dessus
    dans les tests qui exercent leur mecanique specifique (RSI/mlflow, trend deterministe),
    sans changer le comportement produit reel (create_user_bot exige "published").

    Monkeypatch le dict source (DEFAULT_BOT_TEMPLATES), pas la ligne BotTemplate en base :
    ensure_default_templates() est appele de facon defensive a chaque lecture/ecriture
    (list_templates, create_user_bot...) et reecrase TOUS les champs -- dont status -- a
    partir de ce dict a chaque appel, donc modifier seulement la ligne DB serait annule
    des le prochain appel."""
    from bots.service import DEFAULT_BOT_TEMPLATES

    template_data = next(item for item in DEFAULT_BOT_TEMPLATES if item["slug"] == slug)
    monkeypatch.setitem(template_data, "status", "published")


def _fake_klines(rows: int = 180, *, base_price: float = 50000.0) -> list[dict]:
    """Klines normalisees (cf. utils.connectors.exchanges.base.normalize_ohlcv), pas le
    format brut Binance (liste de listes) de l'ancien Testnet lab."""
    klines = []
    open_time = datetime(2023, 11, 14, tzinfo=UTC)
    price = base_price
    for index in range(rows):
        drift = 35 if index % 5 else -20
        open_price = price
        close_price = max(1, price + drift)
        high = max(open_price, close_price) + 15
        low = min(open_price, close_price) - 15
        volume = 100 + index
        klines.append(
            {
                "open_time": open_time + timedelta(hours=index),
                "open": open_price,
                "high": high,
                "low": low,
                "close": close_price,
                "volume": volume,
            }
        )
        price = close_price
    return klines


class TestBotService:
    def test_list_templates_seeds_preconfigured_bots(self, patch_db_session):
        from bots.service import BotService

        templates = BotService().list_templates(include_disabled=True)

        assert len(templates) >= 2
        first = templates[0]
        assert first.symbol
        assert first.timeframe
        assert first.execution_params
        assert first.risk_limits
        assert first.order_policy

    def test_legacy_static_templates_are_disabled_and_hidden_by_default(self, patch_db_session):
        """Les 2 templates figes (RSI, trend) sont masques du catalogue par defaut depuis le
        2026-08-28, maintenant que des templates ML reellement entraines existent -- restent
        crees en base (status="disabled") pour ne pas casser les instances utilisateur deja
        verrouillees dessus, mais ne doivent plus apparaitre dans un list_templates() normal."""
        from bots.service import BotService

        service = BotService()
        published = {item.slug for item in service.list_templates()}
        all_templates = {item.slug for item in service.list_templates(include_disabled=True)}

        assert "ai-rsi-btcusdt-1h-v1" not in published
        assert "ai-trend-ethusdt-4h-v1" not in published
        assert {"ai-rsi-btcusdt-1h-v1", "ai-trend-ethusdt-4h-v1"} <= all_templates

    def test_user_bot_create_rejects_user_supplied_configuration(self, patch_db_session):
        from bots.schemas import UserBotCreate
        from bots.service import BotService

        template = BotService().list_templates(include_disabled=True)[0]

        with pytest.raises(ValidationError):
            UserBotCreate(
                bot_template_id=template.id,
                symbol="ETHUSDC",
                timeframe="1m",
                risk_limits={"risk_per_trade_pct": 99},
            )

    def test_create_user_bot_locks_template_snapshot(self, patch_db_session, monkeypatch):
        from bots.models import BotTemplate, UserBotInstance
        from bots.schemas import UserBotCreate
        from bots.service import BotService

        user_id = _create_user()
        service = BotService()
        _republish_template(monkeypatch, "ai-rsi-btcusdt-1h-v1")
        template = next(item for item in service.list_templates() if item.slug == "ai-rsi-btcusdt-1h-v1")

        instance = service.create_user_bot(user_id, UserBotCreate(bot_template_id=template.id))

        assert instance.config_snapshot["template_id"] == template.id
        assert instance.config_snapshot["symbol"] == template.symbol
        assert instance.config_snapshot["timeframe"] == template.timeframe
        assert instance.config_snapshot["risk_limits"] == template.risk_limits

        db_template = patch_db_session.query(BotTemplate).filter(BotTemplate.id == template.id).first()
        db_template.symbol = "ETHUSDC"
        patch_db_session.flush()

        db_instance = (
            patch_db_session.query(UserBotInstance)
            .filter(UserBotInstance.id == instance.id)
            .first()
        )
        assert db_instance.config_snapshot["symbol"] == template.symbol
        assert db_instance.config_snapshot["symbol"] != db_template.symbol

    def test_start_user_bot_requires_binance_testnet_credentials(self, patch_db_session, monkeypatch):
        from bots.schemas import UserBotCreate
        from bots.service import BotService
        from fastapi import HTTPException

        user_id = _create_user()
        service = BotService()
        _republish_template(monkeypatch, "ai-rsi-btcusdt-1h-v1")
        template = next(item for item in service.list_templates() if item.slug == "ai-rsi-btcusdt-1h-v1")
        instance = service.create_user_bot(user_id, UserBotCreate(bot_template_id=template.id))

        with pytest.raises(HTTPException) as exc_info:
            service.start_user_bot(user_id, instance.id)

        assert exc_info.value.status_code == 400
        assert "credentials" in str(exc_info.value.detail)

    def test_start_user_bot_creates_running_run_when_credentials_exist(self, patch_db_session, monkeypatch):
        from bots.models import BotRun
        from bots.schemas import UserBotCreate
        from bots.service import BotService

        user_id = _create_user()
        _grant_binance_credentials(patch_db_session, user_id, monkeypatch)

        service = BotService()
        _republish_template(monkeypatch, "ai-rsi-btcusdt-1h-v1")
        template = next(item for item in service.list_templates() if item.slug == "ai-rsi-btcusdt-1h-v1")
        instance = service.create_user_bot(user_id, UserBotCreate(bot_template_id=template.id))

        result = service.start_user_bot(user_id, instance.id)

        assert result.bot.status == "ACTIVE"
        assert result.bot.auto_trade_enabled is True
        assert result.bot.exchange_credential_id == "binance"
        run = patch_db_session.query(BotRun).filter(BotRun.user_bot_instance_id == instance.id).first()
        assert run is not None
        assert run.status == "RUNNING"

    def test_execute_once_places_testnet_order_and_records_position(self, patch_db_session, monkeypatch):
        from bots.models import BotOrder, BotPosition, BotTrade
        from bots.schemas import UserBotCreate
        from bots.service import BotService

        class FakeExecutionGateway:
            def __init__(self):
                self.orders = []

            def klines(self, symbol, interval, *, limit=160, exchange="binance"):
                return _fake_klines(limit)

            def open_orders(self, user_id, symbol, *, exchange="binance"):
                return []

            def balances(self, user_id, *, non_zero=True, exchange="binance"):
                return [
                    {"asset": "USDC", "free": "1000", "locked": "0"},
                    {"asset": "BTC", "free": "1", "locked": "0"},
                ]

            def place_order(self, user_id, order, *, exchange="binance"):
                self.orders.append(order)
                return {
                    "symbol": order.symbol,
                    "orderId": 10001,
                    "clientOrderId": order.client_order_id,
                    "status": "FILLED",
                    "executedQty": "0.002",
                    "cummulativeQuoteQty": "100",
                    "fills": [
                        {
                            "price": "50000",
                            "qty": "0.002",
                            "commission": "0.000001",
                            "commissionAsset": "BTC",
                        }
                    ],
                }

        user_id = _create_user()
        _grant_binance_credentials(patch_db_session, user_id, monkeypatch)

        fake_binance = FakeExecutionGateway()
        service = BotService(execution_gateway=fake_binance)
        _republish_template(monkeypatch, "ai-rsi-btcusdt-1h-v1")
        template = next(item for item in service.list_templates() if item.slug == "ai-rsi-btcusdt-1h-v1")
        instance = service.create_user_bot(user_id, UserBotCreate(bot_template_id=template.id))
        service.start_user_bot(user_id, instance.id)
        service._compute_template_signal = lambda snapshot: (
            {"symbol": snapshot["symbol"], "close": 50000},
            {"model_type": snapshot["model_type"], "action": "BUY"},
            "BUY",
            "BUY",
        )

        decision = service.execute_once(instance.id, worker_id="test-worker")

        assert decision.final_action == "BUY"
        assert decision.risk_decision == "PASS"
        assert fake_binance.orders
        order = patch_db_session.query(BotOrder).filter(BotOrder.user_bot_instance_id == instance.id).first()
        trade = patch_db_session.query(BotTrade).filter(BotTrade.user_bot_instance_id == instance.id).first()
        position = patch_db_session.query(BotPosition).filter(BotPosition.user_bot_instance_id == instance.id).first()
        assert order is not None
        assert order.status == "FILLED"
        assert trade is not None
        assert position is not None
        assert position.quantity == Decimal("0.00200000")

        performance = service.get_performance(user_id, instance.id)
        assert performance.total_orders == 1
        assert performance.total_trades == 1
        assert performance.net_position_quantity == Decimal("0.00200000")
        assert performance.last_action == "BUY"

    def test_user_performance_summary_distinguishes_bots_and_filters_model(self, patch_db_session, monkeypatch):
        from bots.models import BotOrder, BotTrade, TradingDecision
        from bots.schemas import UserBotCreate
        from bots.service import BotService, MLFLOW_RSI_MODEL_NAME

        user_id = _create_user()
        service = BotService()
        _republish_template(monkeypatch, "ai-rsi-btcusdt-1h-v1")
        _republish_template(monkeypatch, "ai-trend-ethusdt-4h-v1")
        templates = service.list_templates()
        rsi_template = next(item for item in templates if item.slug == "ai-rsi-btcusdt-1h-v1")
        trend_template = next(item for item in templates if item.slug == "ai-trend-ethusdt-4h-v1")
        rsi_bot = service.create_user_bot(user_id, UserBotCreate(bot_template_id=rsi_template.id))
        trend_bot = service.create_user_bot(user_id, UserBotCreate(bot_template_id=trend_template.id))
        now = datetime.now(UTC)

        rsi_order = BotOrder(
            user_id=user_id,
            user_bot_instance_id=rsi_bot.id,
            exchange="binance",
            environment="testnet",
            symbol="BTCUSDC",
            side="SELL",
            order_type="MARKET",
            status="FILLED",
            created_at=now - timedelta(days=20),
            updated_at=now - timedelta(days=20),
            raw_response={},
        )
        trend_order = BotOrder(
            user_id=user_id,
            user_bot_instance_id=trend_bot.id,
            exchange="binance",
            environment="testnet",
            symbol="ETHUSDC",
            side="SELL",
            order_type="MARKET",
            status="FILLED",
            created_at=now - timedelta(days=5),
            updated_at=now - timedelta(days=5),
            raw_response={},
        )
        patch_db_session.add_all([rsi_order, trend_order])
        patch_db_session.flush()
        patch_db_session.add_all(
            [
                BotTrade(
                    user_id=user_id,
                    order_id=rsi_order.id,
                    user_bot_instance_id=rsi_bot.id,
                    symbol="BTCUSDC",
                    side="SELL",
                    quantity=Decimal("0.001"),
                    price=Decimal("51000"),
                    fee=Decimal("0.1"),
                    fee_asset="USDT",
                    trade_time=now - timedelta(days=20),
                    raw_response={"realized_pnl": "25"},
                ),
                BotTrade(
                    user_id=user_id,
                    order_id=trend_order.id,
                    user_bot_instance_id=trend_bot.id,
                    symbol="ETHUSDC",
                    side="SELL",
                    quantity=Decimal("0.01"),
                    price=Decimal("3000"),
                    fee=Decimal("0.1"),
                    fee_asset="USDT",
                    trade_time=now - timedelta(days=5),
                    raw_response={"realized_pnl": "-5"},
                ),
                TradingDecision(
                    user_id=user_id,
                    user_bot_instance_id=rsi_bot.id,
                    timestamp=now - timedelta(days=20, minutes=1),
                    symbol="BTCUSDC",
                    timeframe="1h",
                    model_output={
                        "model_source": "ml_api",
                        "registry_source": "mlflow",
                        "model_name": MLFLOW_RSI_MODEL_NAME,
                        "model_version": "3",
                        "confidence": 0.8,
                        "raw_ai_signal": "BUY",
                        "deterministic_signal": "HOLD",
                    },
                    strategy_signal="BUY",
                    risk_decision="PASS",
                    final_action="BUY",
                    reason="Risk gate passed for BUY.",
                ),
                TradingDecision(
                    user_id=user_id,
                    user_bot_instance_id=trend_bot.id,
                    timestamp=now - timedelta(days=5, minutes=1),
                    symbol="ETHUSDC",
                    timeframe="4h",
                    model_output={
                        "model_type": "trend_classifier_v1",
                        "strategy_action": "SELL",
                    },
                    strategy_signal="SELL",
                    risk_decision="PASS",
                    final_action="SELL",
                    reason="Risk gate passed for SELL.",
                ),
            ]
        )
        patch_db_session.flush()

        summary = service.get_user_performance_summary(user_id, period_days=30)

        assert summary.global_performance.capital_initial == Decimal("175")
        assert summary.global_performance.pnl_realized == Decimal("20")
        assert summary.global_performance.pnl_unrealized == Decimal("0")
        assert summary.global_performance.pnl_total == Decimal("20")
        assert summary.global_performance.capital_current == Decimal("195")
        assert summary.global_performance.total_orders == 2
        assert summary.global_performance.total_trades == 2
        assert summary.global_performance.win_rate_pct == 50
        assert {row.bot_name: row.pnl_realized for row in summary.bots} == {
            "AI RSI Mean Reversion BTCUSDC 1h": Decimal("25"),
            "AI Trend Following ETHUSDC 4h": Decimal("-5"),
        }
        rsi_row = next(row for row in summary.bots if row.bot_id == rsi_bot.id)
        trend_row = next(row for row in summary.bots if row.bot_id == trend_bot.id)
        assert rsi_row.model_name == MLFLOW_RSI_MODEL_NAME
        assert rsi_row.model_version == "3"
        assert rsi_row.average_confidence == 0.8
        assert rsi_row.pnl_contribution_pct == 125
        assert trend_row.model_name == "trend_classifier_v1"
        assert trend_row.pnl_contribution_pct == -25
        assert len(summary.decisions) == 2
        assert len(summary.orders) == 2
        assert len(summary.trades) == 2
        assert summary.pnl_curve[-1].cumulative_realized_pnl == Decimal("20")

        ml_only = service.get_user_performance_summary(
            user_id,
            period_days=30,
            model_name=MLFLOW_RSI_MODEL_NAME,
        )

        assert len(ml_only.bots) == 1
        assert ml_only.bots[0].bot_id == rsi_bot.id
        assert ml_only.global_performance.pnl_realized == Decimal("25")
        assert ml_only.global_performance.total_orders == 1

    def test_execute_once_blocks_buy_when_daily_loss_limit_is_reached(self, patch_db_session, monkeypatch):
        from bots.models import BotOrder, BotTrade, UserBotInstance
        from bots.schemas import UserBotCreate
        from bots.service import BotService

        class FakeExecutionGateway:
            def klines(self, symbol, interval, *, limit=160, exchange="binance"):
                return _fake_klines(limit)

            def open_orders(self, user_id, symbol, *, exchange="binance"):
                return []

            def balances(self, user_id, *, non_zero=True, exchange="binance"):
                return [
                    {"asset": "USDC", "free": "1000", "locked": "0"},
                    {"asset": "BTC", "free": "0", "locked": "0"},
                ]

            def place_order(self, user_id, order, *, exchange="binance"):
                raise AssertionError("Risk manager should block the order")

        user_id = _create_user()
        _grant_binance_credentials(patch_db_session, user_id, monkeypatch)

        service = BotService(execution_gateway=FakeExecutionGateway())
        _republish_template(monkeypatch, "ai-rsi-btcusdt-1h-v1")
        template = next(item for item in service.list_templates() if item.slug == "ai-rsi-btcusdt-1h-v1")
        instance = service.create_user_bot(user_id, UserBotCreate(bot_template_id=template.id))
        snapshot = dict(instance.config_snapshot)
        snapshot["risk_limits"] = {**snapshot["risk_limits"], "max_daily_loss_pct": 1.0}
        service.start_user_bot(user_id, instance.id)
        instance_row = patch_db_session.query(UserBotInstance).filter_by(id=instance.id).first()
        instance_row.config_snapshot = snapshot
        order = BotOrder(
            user_id=user_id,
            user_bot_instance_id=instance.id,
            exchange="binance",
            environment="testnet",
            symbol=snapshot["symbol"],
            side="SELL",
            order_type="MARKET",
            status="FILLED",
            raw_response={},
        )
        patch_db_session.add(order)
        patch_db_session.flush()
        patch_db_session.add(
            BotTrade(
                user_id=user_id,
                order_id=order.id,
                user_bot_instance_id=instance.id,
                symbol=snapshot["symbol"],
                side="SELL",
                quantity=Decimal("0.001"),
                price=Decimal("49000"),
                fee=Decimal("0"),
                fee_asset="USDT",
                trade_time=datetime.now(UTC),
                raw_response={"realized_pnl": "-20"},
            )
        )
        patch_db_session.flush()
        service._compute_template_signal = lambda locked_snapshot: (
            {"symbol": locked_snapshot["symbol"], "close": 50000},
            {"model_type": locked_snapshot["model_type"], "action": "BUY"},
            "BUY",
            "BUY",
        )

        decision = service.execute_once(instance.id, worker_id="test-worker")

        assert decision.final_action == "HOLD"
        assert decision.risk_decision == "BLOCKED"
        assert "daily loss limit" in decision.reason

    def test_rsi_bot_uses_ml_api_and_records_model_trace(self, patch_db_session, monkeypatch):
        from bots.schemas import UserBotCreate
        from bots.service import BotService, MLFLOW_RSI_MODEL_NAME

        class FakeExecutionGateway:
            def __init__(self):
                self.orders = []

            def klines(self, symbol, interval, *, limit=160, exchange="binance"):
                return _fake_klines(limit)

            def open_orders(self, user_id, symbol, *, exchange="binance"):
                return []

            def balances(self, user_id, *, non_zero=True, exchange="binance"):
                return [
                    {"asset": "USDC", "free": "1000", "locked": "0"},
                    {"asset": "BTC", "free": "0", "locked": "0"},
                ]

            def place_order(self, user_id, order, *, exchange="binance"):
                self.orders.append(order)
                return {
                    "symbol": order.symbol,
                    "orderId": 20001,
                    "clientOrderId": order.client_order_id,
                    "status": "FILLED",
                    "executedQty": "0.002",
                    "cummulativeQuoteQty": "100",
                }

        class FakeMlClient:
            def __init__(self):
                self.calls = []

            def predict(self, *, model_name, features, model_version=None):
                self.calls.append({"model_name": model_name, "features": features, "model_version": model_version})
                return {
                    "model_source": "mlflow",
                    "model_name": model_name,
                    "model_version": "7",
                    "signal": "BUY",
                    "confidence": 0.91,
                    "probabilities": {"BUY": 0.91, "SELL": 0.03, "HOLD": 0.06},
                    "features": features,
                    "generated_at": "2026-06-27T00:00:00+00:00",
                }

        user_id = _create_user()
        _grant_binance_credentials(patch_db_session, user_id, monkeypatch)

        fake_binance = FakeExecutionGateway()
        fake_ml = FakeMlClient()
        service = BotService(execution_gateway=fake_binance, ml_client=fake_ml)
        _republish_template(monkeypatch, "ai-rsi-btcusdt-1h-v1")
        template = next(item for item in service.list_templates() if item.slug == "ai-rsi-btcusdt-1h-v1")
        instance = service.create_user_bot(user_id, UserBotCreate(bot_template_id=template.id))
        service.start_user_bot(user_id, instance.id)

        decision = service.execute_once(instance.id, worker_id="test-worker")

        assert fake_ml.calls
        assert fake_ml.calls[0]["model_name"] == MLFLOW_RSI_MODEL_NAME
        assert decision.final_action == "BUY"
        assert decision.risk_decision == "PASS"
        assert fake_binance.orders
        assert decision.model_output["model_source"] == "ml_api"
        assert decision.model_output["registry_source"] == "mlflow"
        assert decision.model_output["model_name"] == MLFLOW_RSI_MODEL_NAME
        assert decision.model_output["model_version"] == "7"
        assert decision.model_output["confidence"] == 0.91
        assert decision.model_output["raw_ai_signal"] == "BUY"
        assert decision.model_output["deterministic_signal"] in {"BUY", "SELL", "HOLD"}
        assert set(decision.model_output["features"]) == {"rsi", "price_change", "volume", "sma_short", "sma_long"}

    def test_missing_ml_model_records_skip_and_sends_no_order(self, patch_db_session, monkeypatch):
        from bots.ml_client import BotModelUnavailable
        from bots.schemas import UserBotCreate
        from bots.service import BotService

        class FakeExecutionGateway:
            def klines(self, symbol, interval, *, limit=160, exchange="binance"):
                return _fake_klines(limit)

            def place_order(self, user_id, order, *, exchange="binance"):
                raise AssertionError("Model unavailable must never send an order")

        class MissingModelClient:
            def predict(self, *, model_name, features, model_version=None):
                raise BotModelUnavailable("MLflow model not found in registry")

        user_id = _create_user()
        _grant_binance_credentials(patch_db_session, user_id, monkeypatch)

        service = BotService(execution_gateway=FakeExecutionGateway(), ml_client=MissingModelClient())
        _republish_template(monkeypatch, "ai-rsi-btcusdt-1h-v1")
        template = next(item for item in service.list_templates() if item.slug == "ai-rsi-btcusdt-1h-v1")
        instance = service.create_user_bot(user_id, UserBotCreate(bot_template_id=template.id))
        service.start_user_bot(user_id, instance.id)

        decision = service.execute_once(instance.id, worker_id="test-worker")

        assert decision.final_action == "HOLD"
        assert decision.risk_decision == "SKIP_MODEL_UNAVAILABLE"
        # strategy_signal est un String(20) (bots/models.py) : SQLite (ce test) n'applique
        # pas cette contrainte de longueur contrairement a Postgres (prod/staging), d'ou
        # l'assertion de longueur explicite -- sinon une regression ne serait visible qu'en
        # conditions reelles (StringDataRightTruncation), comme ca a ete le cas une fois.
        assert decision.strategy_signal == "SKIP_UNAVAILABLE"
        assert len(decision.strategy_signal) <= 20
        assert decision.model_output["status"] == "SKIP_MODEL_UNAVAILABLE"
        assert "MLflow model not found" in decision.model_output["error"]

    def test_sync_builtin_templates_migrates_existing_rsi_snapshot_to_ml_api(self, patch_db_session, monkeypatch):
        from bots.models import UserBotInstance
        from bots.schemas import UserBotCreate
        from bots.service import BotService, MLFLOW_RSI_MODEL_NAME, MLFLOW_RSI_MODEL_TYPE

        user_id = _create_user()
        service = BotService()
        _republish_template(monkeypatch, "ai-rsi-btcusdt-1h-v1")
        template = next(item for item in service.list_templates() if item.slug == "ai-rsi-btcusdt-1h-v1")
        instance = service.create_user_bot(user_id, UserBotCreate(bot_template_id=template.id))

        row = patch_db_session.query(UserBotInstance).filter(UserBotInstance.id == instance.id).first()
        old_snapshot = dict(row.config_snapshot)
        old_snapshot["model_type"] = "regime_classifier_v1"
        old_snapshot["signal_source"] = "regime_classifier_v1+rsi_reversal"
        old_snapshot["execution_params"] = {
            "rsi_period": 14,
            "oversold_threshold": 30,
            "overbought_threshold": 70,
            "confirmation_bars": 1,
        }
        row.config_snapshot = old_snapshot
        row.status = "ACTIVE"
        row.auto_trade_enabled = True
        patch_db_session.flush()

        result = service.sync_builtin_templates(migrate_instances=True)
        patch_db_session.expire_all()
        migrated = patch_db_session.query(UserBotInstance).filter(UserBotInstance.id == instance.id).first()

        assert result["instances_migrated"] >= 1
        assert migrated.config_snapshot["model_type"] == MLFLOW_RSI_MODEL_TYPE
        assert migrated.config_snapshot["signal_source"] == f"mlflow:{MLFLOW_RSI_MODEL_NAME}+rsi_reversal"
        assert migrated.config_snapshot["execution_params"]["mlflow_model_name"] == MLFLOW_RSI_MODEL_NAME

    def test_other_bot_still_uses_deterministic_model(self, patch_db_session, monkeypatch):
        from bots.schemas import UserBotCreate
        from bots.service import BotService

        class FakeExecutionGateway:
            def klines(self, symbol, interval, *, limit=160, exchange="binance"):
                return _fake_klines(limit, base_price=3000.0)

        class FailingMlClient:
            def predict(self, *, model_name, features, model_version=None):
                raise AssertionError("ETH deterministic bot must not call ML API")

        user_id = _create_user()
        service = BotService(execution_gateway=FakeExecutionGateway(), ml_client=FailingMlClient())
        _republish_template(monkeypatch, "ai-trend-ethusdt-4h-v1")
        template = next(item for item in service.list_templates() if item.slug == "ai-trend-ethusdt-4h-v1")
        instance = service.create_user_bot(user_id, UserBotCreate(bot_template_id=template.id))

        market_snapshot, model_output, strategy_signal, requested_action = service._compute_template_signal(
            instance.config_snapshot
        )

        assert market_snapshot["symbol"] == "ETHUSDC"
        assert model_output["model_type"] == "trend_classifier_v1"
        assert model_output["model_result"]["model_type"] == "trend_classifier_v1"
        assert strategy_signal in {"BUY", "SELL", "HOLD"}
        assert requested_action in {"BUY", "SELL", "HOLD"}

    def test_generate_ml_templates_builds_one_template_per_trained_combo(self, patch_db_session):
        from bots.service import PAIR_QUALIFIED_ML_STRATEGY_TYPE, BotService

        class FakeMlClient:
            def list_trained_combos(self):
                return [
                    {"symbol": "BTCUSDC", "model_name": "random_forest", "registered_name": "random_forest_btcusdc"},
                    {"symbol": "ETHUSDC", "model_name": "xgboost", "registered_name": "xgboost_ethusdc"},
                ]

        service = BotService(ml_client=FakeMlClient())
        templates = service._generate_ml_templates()

        assert {template["slug"] for template in templates} == {
            "ml-random_forest-btcusdc-1h-v1",
            "ml-xgboost-ethusdc-1h-v1",
        }
        rf_template = next(item for item in templates if item["slug"] == "ml-random_forest-btcusdc-1h-v1")
        assert rf_template["symbol"] == "BTCUSDC"
        assert rf_template["model_type"] == "ml_random_forest"
        assert rf_template["strategy_type"] == PAIR_QUALIFIED_ML_STRATEGY_TYPE
        assert rf_template["signal_source"] == "mlflow:random_forest_btcusdc"
        assert rf_template["execution_params"]["registry_model_name"] == "random_forest_btcusdc"

    def test_generate_ml_templates_returns_empty_when_ml_api_unavailable(self, patch_db_session):
        from bots.ml_client import BotModelUnavailable
        from bots.service import BotService

        class UnavailableMlClient:
            def list_trained_combos(self):
                raise BotModelUnavailable("ML API unavailable: connection refused")

        service = BotService(ml_client=UnavailableMlClient())

        assert service._generate_ml_templates() == []

    def test_sync_builtin_templates_seeds_ml_templates_from_trained_combos(self, patch_db_session):
        from bots.service import BotService

        class FakeMlClient:
            def list_trained_combos(self):
                return [
                    {"symbol": "BTCUSDC", "model_name": "random_forest", "registered_name": "random_forest_btcusdc"},
                ]

        service = BotService(ml_client=FakeMlClient())
        result = service.sync_builtin_templates()

        assert result["templates_synced"] >= 3  # 2 templates figes + 1 template ML genere
        templates = service.list_templates(include_disabled=True)
        assert any(item.slug == "ml-random_forest-btcusdc-1h-v1" for item in templates)

    def test_pair_qualified_ml_bot_computes_signal_from_live_features(self, patch_db_session, monkeypatch):
        import pandas as pd
        from bots.schemas import UserBotCreate
        from bots.service import BotService

        class FakeExecutionGateway:
            def __init__(self):
                self.orders = []

            def open_orders(self, user_id, symbol, *, exchange="binance"):
                return []

            def balances(self, user_id, *, non_zero=True, exchange="binance"):
                return [{"asset": "USDC", "free": "1000", "locked": "0"}]

            def place_order(self, user_id, order, *, exchange="binance"):
                self.orders.append(order)
                return {
                    "symbol": order.symbol,
                    "orderId": 30001,
                    "clientOrderId": order.client_order_id,
                    "status": "FILLED",
                    "executedQty": "0.002",
                    "cummulativeQuoteQty": "100",
                }

        class FakeMlClient:
            def __init__(self):
                self.calls = []

            def list_trained_combos(self):
                return [
                    {"symbol": "BTCUSDC", "model_name": "random_forest", "registered_name": "random_forest_btcusdc"},
                ]

            def predict(self, *, model_name, features, model_version=None):
                self.calls.append({"model_name": model_name, "features": features})
                return {
                    "model_source": "mlflow",
                    "model_name": model_name,
                    "model_version": "2",
                    "signal": "BUY",
                    "confidence": 0.77,
                    "probabilities": {"BUY": 0.77, "SELL": 0.13, "HOLD": 0.10},
                    "features": features,
                    "generated_at": "2026-06-27T00:00:00+00:00",
                }

        # open_time est un vrai datetime (pas un int) pour reproduire fidelement
        # build_live_feature_frame() : une fois passe par pd.DataFrame(...), pandas le
        # convertit en Timestamp -- pas serialisable en JSON tel quel, cf. bug reel corrige
        # dans _clean_value() (StrategyDeployment/decision.market_snapshot est une colonne
        # JSON, bots/models.py).
        fake_frame = pd.DataFrame(
            [
                {
                    "open_time": datetime(2026, 8, 28, 12, 0, tzinfo=UTC),
                    "open": 100.0,
                    "high": 101.0,
                    "low": 99.0,
                    "close": 100.5,
                    "volume": 10.0,
                    "rsi_14": 55.0,
                }
            ]
        )
        monkeypatch.setattr("bots.service.build_live_feature_frame", lambda symbol, timeframe: fake_frame)

        user_id = _create_user()
        _grant_binance_credentials(patch_db_session, user_id, monkeypatch)
        fake_binance = FakeExecutionGateway()
        fake_ml = FakeMlClient()
        service = BotService(execution_gateway=fake_binance, ml_client=fake_ml)
        service.sync_builtin_templates()
        template = next(item for item in service.list_templates() if item.slug == "ml-random_forest-btcusdc-1h-v1")
        instance = service.create_user_bot(user_id, UserBotCreate(bot_template_id=template.id))
        service.start_user_bot(user_id, instance.id)

        decision = service.execute_once(instance.id, worker_id="test-worker")

        assert fake_ml.calls
        assert fake_ml.calls[0]["model_name"] == "random_forest_btcusdc"
        assert fake_ml.calls[0]["features"]["rsi_14"] == 55.0
        assert decision.final_action == "BUY"
        assert decision.model_output["model_source"] == "ml_api"
        assert decision.model_output["model_version"] == "2"
        # Regression : open_time est un pandas.Timestamp cote build_live_feature_frame(),
        # pas serialisable en JSON tel quel -- decision.market_snapshot est une colonne
        # JSON (bots/models.py), donc un int confirme que _clean_value() l'a bien converti
        # avant l'ecriture en base (sinon l'ecriture aurait leve, testee de bout en bout ici).
        assert isinstance(decision.market_snapshot["open_time"], int)

    def test_pair_qualified_ml_bot_records_skip_when_model_unavailable(self, patch_db_session, monkeypatch):
        """Regression pour le StringDataRightTruncation constate en Postgres reel : le
        decision.strategy_signal ecrit ici doit tenir dans String(20) (bots/models.py),
        contrainte que SQLite (ce test) n'applique pas -- assertion de longueur explicite."""
        import pandas as pd
        from bots.ml_client import BotModelUnavailable
        from bots.schemas import UserBotCreate
        from bots.service import BotService

        class FakeExecutionGateway:
            def place_order(self, user_id, order, *, exchange="binance"):
                raise AssertionError("Model unavailable must never send an order")

        class MissingModelClient:
            def list_trained_combos(self):
                return [
                    {"symbol": "BTCUSDC", "model_name": "random_forest", "registered_name": "random_forest_btcusdc"},
                ]

            def predict(self, *, model_name, features, model_version=None):
                raise BotModelUnavailable("MLflow model not found in registry")

        fake_frame = pd.DataFrame(
            [
                {
                    "open_time": datetime(2026, 8, 28, 12, 0, tzinfo=UTC),
                    "open": 100.0,
                    "high": 101.0,
                    "low": 99.0,
                    "close": 100.5,
                    "volume": 10.0,
                }
            ]
        )
        monkeypatch.setattr("bots.service.build_live_feature_frame", lambda symbol, timeframe: fake_frame)

        user_id = _create_user()
        _grant_binance_credentials(patch_db_session, user_id, monkeypatch)
        service = BotService(execution_gateway=FakeExecutionGateway(), ml_client=MissingModelClient())
        service.sync_builtin_templates()
        template = next(item for item in service.list_templates() if item.slug == "ml-random_forest-btcusdc-1h-v1")
        instance = service.create_user_bot(user_id, UserBotCreate(bot_template_id=template.id))
        service.start_user_bot(user_id, instance.id)

        decision = service.execute_once(instance.id, worker_id="test-worker")

        assert decision.final_action == "HOLD"
        assert decision.strategy_signal == "SKIP_UNAVAILABLE"
        assert len(decision.strategy_signal) <= 20
        assert decision.model_output["status"] == "SKIP_MODEL_UNAVAILABLE"

    def test_user_creates_two_bots_with_different_trained_combos_start_stop_and_results(
        self, patch_db_session, monkeypatch
    ):
        """Parcours utilisateur (etape 9 du plan, sans vraie stack Docker/testnet) : cle
        Binance -> creer un bot (BTCUSDC/RF) -> start -> execution -> stop -> resultats ->
        creer un 2e bot (ETHUSDC/XGBoost) -> start -> execution -> stop -> resultats
        consolides sur les deux bots. La verification "en reel" (vraie cle testnet, vraie
        UI) reste faite par Nathalie -- ce test couvre le meme parcours cote backend avec
        des fakes, pour qu'une regression soit attrapee sans avoir a relancer la stack."""
        import pandas as pd
        from bots.schemas import UserBotCreate
        from bots.service import BotService

        class FakeExecutionGateway:
            def __init__(self):
                self.orders = []

            def open_orders(self, user_id, symbol, *, exchange="binance"):
                return []

            def balances(self, user_id, *, non_zero=True, exchange="binance"):
                return [{"asset": "USDC", "free": "1000", "locked": "0"}]

            def place_order(self, user_id, order, *, exchange="binance"):
                self.orders.append(order)
                return {
                    "symbol": order.symbol,
                    "orderId": 40000 + len(self.orders),
                    "clientOrderId": order.client_order_id,
                    "status": "FILLED",
                    "executedQty": "0.002",
                    "cummulativeQuoteQty": "100",
                }

        class FakeMlClient:
            def __init__(self):
                self.calls = []

            def list_trained_combos(self):
                return [
                    {"symbol": "BTCUSDC", "model_name": "random_forest", "registered_name": "random_forest_btcusdc"},
                    {"symbol": "ETHUSDC", "model_name": "xgboost", "registered_name": "xgboost_ethusdc"},
                ]

            def predict(self, *, model_name, features, model_version=None):
                self.calls.append(model_name)
                return {
                    "model_source": "mlflow",
                    "model_name": model_name,
                    "model_version": "1",
                    "signal": "BUY",
                    "confidence": 0.8,
                    "probabilities": {"BUY": 0.8, "SELL": 0.1, "HOLD": 0.1},
                    "features": features,
                    "generated_at": "2026-06-27T00:00:00+00:00",
                }

        fake_frame = pd.DataFrame(
            [
                {
                    "open_time": datetime(2026, 8, 28, 12, 0, tzinfo=UTC),
                    "open": 100.0,
                    "high": 101.0,
                    "low": 99.0,
                    "close": 100.5,
                    "volume": 10.0,
                }
            ]
        )
        monkeypatch.setattr("bots.service.build_live_feature_frame", lambda symbol, timeframe: fake_frame)

        user_id = _create_user()
        _grant_binance_credentials(patch_db_session, user_id, monkeypatch)
        fake_binance = FakeExecutionGateway()
        fake_ml = FakeMlClient()
        service = BotService(execution_gateway=fake_binance, ml_client=fake_ml)
        service.sync_builtin_templates()
        templates = {item.slug: item for item in service.list_templates()}

        # Bot 1 : BTCUSDC / random_forest
        bot1 = service.create_user_bot(
            user_id, UserBotCreate(bot_template_id=templates["ml-random_forest-btcusdc-1h-v1"].id)
        )
        service.start_user_bot(user_id, bot1.id)
        decision1 = service.execute_once(bot1.id, worker_id="test-worker")
        stop1 = service.stop_user_bot(user_id, bot1.id)
        performance1 = service.get_performance(user_id, bot1.id)

        assert decision1.final_action == "BUY"
        assert stop1.bot.status == "STOPPED"
        assert performance1.total_orders == 1

        # Bot 2 : ETHUSDC / xgboost, cree apres coup, independant du premier
        bot2 = service.create_user_bot(user_id, UserBotCreate(bot_template_id=templates["ml-xgboost-ethusdc-1h-v1"].id))
        service.start_user_bot(user_id, bot2.id)
        decision2 = service.execute_once(bot2.id, worker_id="test-worker")
        stop2 = service.stop_user_bot(user_id, bot2.id)
        performance2 = service.get_performance(user_id, bot2.id)

        assert decision2.final_action == "BUY"
        assert stop2.bot.status == "STOPPED"
        assert performance2.total_orders == 1

        assert set(fake_ml.calls) == {"random_forest_btcusdc", "xgboost_ethusdc"}

        all_bots = service.list_user_bots(user_id)
        assert {bot.id for bot in all_bots} == {bot1.id, bot2.id}

        summary = service.get_user_performance_summary(user_id)
        assert summary.global_performance.total_orders == 2
        assert summary.global_performance.total_trades == 2
        assert {row.bot_name for row in summary.bots} == {
            templates["ml-random_forest-btcusdc-1h-v1"].name,
            templates["ml-xgboost-ethusdc-1h-v1"].name,
        }
