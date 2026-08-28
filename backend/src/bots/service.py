"""Business service for immutable bot templates and user bot instances."""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from decimal import Decimal, InvalidOperation
from typing import Any

from auth.models import UserSettings
from fastapi import HTTPException, status
from inference.live_features import build_live_feature_frame
from market.clients.quotes import get_default_quote
from shared.database.connection import get_db_session
from sqlalchemy.orm import Session

from bots.ai import evaluate_template_model
from bots.execution import BotOrderRequest, MultiExchangeBotGateway
from bots.ml_client import BotMlClient, BotModelUnavailable
from bots.models import BotOrder, BotPosition, BotRun, BotTemplate, BotTrade, TradingDecision, UserBotInstance
from bots.schemas import (
    BotActionResponse,
    BotOrderResponse,
    BotPerformanceContributionResponse,
    BotPerformanceResponse,
    BotPositionResponse,
    BotTemplateResponse,
    BotTradeResponse,
    PerformanceDecisionHistoryResponse,
    PerformanceOrderHistoryResponse,
    PerformancePnlPointResponse,
    PerformanceTradeHistoryResponse,
    PerformanceUnavailableReason,
    TradingDecisionResponse,
    UserBotCreate,
    UserBotResponse,
    UserPerformanceGlobalResponse,
    UserPerformanceSummaryResponse,
)

logger = logging.getLogger(__name__)

# TradingDecision.strategy_signal est un String(20) (bots/models.py) -- "SKIP_MODEL_
# UNAVAILABLE" (22 caracteres) le depasse. SQLite (utilise en test) n'applique pas cette
# contrainte de longueur, contrairement a Postgres (prod/staging) : le bug etait invisible
# en test, decouvert seulement en conditions reelles (StringDataRightTruncation). Le status
# complet reste "SKIP_MODEL_UNAVAILABLE" dans model_output/risk_decision (colonnes non
# contraintes), seul ce libelle-la doit rester court.
MODEL_UNAVAILABLE_STRATEGY_SIGNAL = "SKIP_UNAVAILABLE"

MLFLOW_RSI_MODEL_TYPE = "mlflow_bot_rsi_reversal_v1"
# Nom du modele tel qu'enregistre dans le registre MLflow existant -- pas renomme en
# "...btcusdc..." malgre le template ci-dessous qui trade desormais en BTCUSDC (conformite
# MiCA, cf. commit e2455de) : le modele reste entraine sur des donnees BTCUSDT historiques
# (models/src/training/train_bot_rsi_reversal.py). A reentrainer sur BTCUSDC puis
# ce nom sera aligne -- pas fait ici (entrainement hors scope, decision produit).
MLFLOW_RSI_MODEL_NAME = "bot_rsi_reversal_btcusdt_1h"

# Devise de cotation des templates par defaut : derivee de market.clients.quotes (source
# unique de verite pour ce choix, cf. sa docstring), jamais un litteral "USDC" en dur ici.
_DEFAULT_TEMPLATE_EXCHANGE = "binance"
_DEFAULT_TEMPLATE_QUOTE = get_default_quote(_DEFAULT_TEMPLATE_EXCHANGE)
_RSI_TEMPLATE_SYMBOL = f"BTC{_DEFAULT_TEMPLATE_QUOTE}"
_TREND_TEMPLATE_SYMBOL = f"ETH{_DEFAULT_TEMPLATE_QUOTE}"


DEFAULT_BOT_TEMPLATES: list[dict[str, Any]] = [
    {
        "slug": "ai-rsi-btcusdt-1h-v1",
        "name": f"AI RSI Mean Reversion {_RSI_TEMPLATE_SYMBOL} 1h",
        "description": (
            f"Bot Testnet cle en main utilisant un modele IA MLflow versionne et "
            f"RSI mean reversion sur {_RSI_TEMPLATE_SYMBOL}."
        ),
        "model_type": MLFLOW_RSI_MODEL_TYPE,
        "strategy_type": "rsi_reversal",
        "symbol": _RSI_TEMPLATE_SYMBOL,
        "timeframe": "1h",
        "signal_source": f"mlflow:{MLFLOW_RSI_MODEL_NAME}+rsi_reversal",
        "exchange": _DEFAULT_TEMPLATE_EXCHANGE,
        "environment": "testnet",
        "execution_params": {
            "rsi_period": 14,
            "oversold_threshold": 30,
            "overbought_threshold": 70,
            "confirmation_bars": 1,
            "mlflow_model_name": MLFLOW_RSI_MODEL_NAME,
            "mlflow_model_version": None,
            "ml_feature_schema": "rsi_reversal_v1",
        },
        "risk_limits": {
            "risk_per_trade_pct": 1.0,
            "stop_loss_pct": 2.0,
            "take_profit_pct": 4.0,
            "max_order_quote_quantity": "100",
            "max_open_orders": 1,
            "max_user_open_positions": 3,
            "max_daily_loss_pct": 3.0,
        },
        "order_policy": {
            "order_type": "MARKET",
            "quote_order_quantity": "100",
            "quote_asset": _DEFAULT_TEMPLATE_QUOTE,
            "cooldown_seconds": 3600,
        },
        "version": "1.0",
        # Disabled le 2026-08-28 : masque du catalogue maintenant que des templates ML
        # reellement entraines (chemin B, _generate_ml_templates()) sont disponibles --
        # les instances utilisateur deja creees a partir de ce template continuent de
        # fonctionner normalement (config_snapshot verrouillee, aucun controle de status
        # au start/execute, seul create_user_bot exige "published").
        "status": "disabled",
    },
    {
        "slug": "ai-trend-ethusdt-4h-v1",
        "name": f"AI Trend Following {_TREND_TEMPLATE_SYMBOL} 4h",
        "description": (
            f"Bot Testnet cle en main combinant signal de tendance IA et suivi de tendance {_TREND_TEMPLATE_SYMBOL}."
        ),
        "model_type": "trend_classifier_v1",
        "strategy_type": "moving_average_crossover",
        "symbol": _TREND_TEMPLATE_SYMBOL,
        "timeframe": "4h",
        "signal_source": "trend_classifier_v1+moving_average_crossover",
        "exchange": _DEFAULT_TEMPLATE_EXCHANGE,
        "environment": "testnet",
        "execution_params": {
            "fast_period": 10,
            "slow_period": 30,
            "confirmation_bars": 2,
        },
        "risk_limits": {
            "risk_per_trade_pct": 0.75,
            "stop_loss_pct": 2.5,
            "take_profit_pct": 5.0,
            "max_order_quote_quantity": "75",
            "max_open_orders": 1,
            "max_user_open_positions": 3,
            "max_daily_loss_pct": 2.5,
        },
        "order_policy": {
            "order_type": "MARKET",
            "quote_order_quantity": "75",
            "quote_asset": _DEFAULT_TEMPLATE_QUOTE,
            "cooldown_seconds": 14400,
        },
        "version": "1.0",
        # Disabled le 2026-08-28 : meme raison que ai-rsi-btcusdt-1h-v1 ci-dessus.
        "status": "disabled",
    },
]

# strategy_type place-holder pour les templates generes dynamiquement depuis
# BotMlClient.list_trained_combos() (chemin B, modeles qualifies par paire) -- ce ne sont
# jamais des regles techniques valides pour strategy.engine.registry.get_strategy(), donc
# _compute_template_signal() doit intercepter ce cas AVANT tout appel a _create_strategy().
PAIR_QUALIFIED_ML_STRATEGY_TYPE = "ml_registry_signal"
# Timeframe des modeles entraines par le DAG ml_pipeline (orchestration/dags/ml_pipeline.py::
# INTERVAL) -- a garder synchronise manuellement, comme build_live_feature_frame()
# (inference/live_features.py) l'est deja avec models/config.yaml.
PAIR_QUALIFIED_ML_TIMEFRAME = "1h"


class BotService:
    """Service for bot catalog, user instances, and run decisions."""

    def __init__(
        self,
        execution_gateway: MultiExchangeBotGateway | None = None,
        ml_client: BotMlClient | None = None,
    ) -> None:
        self.execution_gateway = execution_gateway or MultiExchangeBotGateway()
        self.ml_client = ml_client or BotMlClient()

    def ensure_default_templates(self, session: Session) -> None:
        """Create or refresh built-in immutable bot templates."""
        self._upsert_templates(session, DEFAULT_BOT_TEMPLATES)

    def _generate_ml_templates(self) -> list[dict[str, Any]]:
        """Un template par couple (paire, modele) reellement entraine, cf.
        BotMlClient.list_trained_combos() (chemin B, MLflow Model Registry) --
        remplace la necessite d'une liste figee pour ces modeles-la (RF, XGBoost).

        Si le ml-api est injoignable, retourne [] plutot que de faire echouer tout le
        cycle de synchronisation : les templates deja en base restent visibles tels
        quels, juste pas rafraichis pour ce cycle.
        """
        try:
            combos = self.ml_client.list_trained_combos()
        except BotModelUnavailable as exc:
            logger.warning("Could not list trained model combos from ml-api, skipping ML templates: %s", exc)
            return []

        templates = []
        for combo in combos:
            symbol = str(combo["symbol"]).upper()
            model_name = str(combo["model_name"])
            registered_name = str(combo["registered_name"])
            templates.append(
                {
                    "slug": f"ml-{model_name}-{symbol.lower()}-{PAIR_QUALIFIED_ML_TIMEFRAME}-v1",
                    "name": f"{model_name.replace('_', ' ').title()} {symbol} {PAIR_QUALIFIED_ML_TIMEFRAME}",
                    "description": (
                        f"Bot Testnet pilote par le modele {model_name} entraine sur {symbol} "
                        f'(registre MLflow "{registered_name}").'
                    ),
                    "model_type": f"ml_{model_name}",
                    "strategy_type": PAIR_QUALIFIED_ML_STRATEGY_TYPE,
                    "symbol": symbol,
                    "timeframe": PAIR_QUALIFIED_ML_TIMEFRAME,
                    "signal_source": f"mlflow:{registered_name}",
                    "exchange": _DEFAULT_TEMPLATE_EXCHANGE,
                    "environment": "testnet",
                    "execution_params": {"registry_model_name": registered_name},
                    "risk_limits": {
                        "risk_per_trade_pct": 1.0,
                        "stop_loss_pct": 2.0,
                        "take_profit_pct": 4.0,
                        "max_order_quote_quantity": "100",
                        "max_open_orders": 1,
                        "max_user_open_positions": 3,
                        "max_daily_loss_pct": 3.0,
                    },
                    "order_policy": {
                        "order_type": "MARKET",
                        "quote_order_quantity": "100",
                        "quote_asset": _DEFAULT_TEMPLATE_QUOTE,
                        "cooldown_seconds": 3600,
                    },
                    "version": "1.0",
                    "status": "published",
                }
            )
        return templates

    @staticmethod
    def _upsert_templates(session: Session, templates: list[dict[str, Any]]) -> None:
        for template_data in templates:
            template = session.query(BotTemplate).filter(BotTemplate.slug == template_data["slug"]).first()
            if template is None:
                session.add(BotTemplate(**template_data))
                continue
            for key, value in template_data.items():
                setattr(template, key, value)
        session.flush()

    def sync_builtin_templates(self, *, migrate_instances: bool = False) -> dict[str, Any]:
        """Reseed built-in templates and optionally migrate existing instance snapshots.

        The user-facing bot configuration is stored as a snapshot when the user selects a
        template. Product-owned template upgrades therefore need an explicit snapshot
        migration, otherwise active bots keep executing the old deterministic config.

        Les templates ML generes dynamiquement (_generate_ml_templates(), un appel HTTP au
        ml-api) ne sont rafraichis qu'ici -- pas a chaque lecture (ensure_default_templates,
        appele par list_templates/get_template/create_user_bot), pour ne pas coupler tout
        appel de lecture a la disponibilite du ml-api. Ils sont donc a jour au demarrage du
        backend (cf. main.py) et lors d'une resynchronisation explicite, pas en temps reel.
        """
        with get_db_session() as session:
            ml_templates = self._generate_ml_templates()
            all_templates = [*DEFAULT_BOT_TEMPLATES, *ml_templates]
            self._upsert_templates(session, all_templates)
            migrated_instances = self._migrate_builtin_instance_snapshots(session) if migrate_instances else []
            template_count = (
                session.query(BotTemplate)
                .filter(BotTemplate.slug.in_([template["slug"] for template in all_templates]))
                .count()
            )
            session.flush()
            return {
                "templates_synced": template_count,
                "instances_migrated": len(migrated_instances),
                "migrated_instance_ids": migrated_instances,
                "migrate_instances": migrate_instances,
            }

    def _migrate_builtin_instance_snapshots(self, session: Session) -> list[str]:
        templates_by_slug = {
            template.slug: template
            for template in session.query(BotTemplate)
            .filter(BotTemplate.slug.in_([template["slug"] for template in DEFAULT_BOT_TEMPLATES]))
            .all()
        }
        migrated: list[str] = []
        instances = session.query(UserBotInstance).all()
        for instance in instances:
            snapshot = dict(instance.config_snapshot or {})
            snapshot_slug = str(snapshot.get("template_slug") or "")
            template = templates_by_slug.get(snapshot_slug)
            if template is None and instance.template and instance.template.slug in templates_by_slug:
                template = templates_by_slug[instance.template.slug]
            if template is None:
                continue

            updated_snapshot = self._snapshot_template(template)
            if snapshot != updated_snapshot or instance.bot_template_id != template.id:
                instance.bot_template_id = template.id
                instance.config_snapshot = updated_snapshot
                migrated.append(instance.id)
        session.flush()
        return migrated

    def list_templates(self, include_disabled: bool = False) -> list[BotTemplateResponse]:
        with get_db_session() as session:
            self.ensure_default_templates(session)
            query = session.query(BotTemplate)
            if not include_disabled:
                query = query.filter(BotTemplate.status == "published")
            templates = query.order_by(BotTemplate.name.asc()).all()
            return [BotTemplateResponse.model_validate(template) for template in templates]

    def get_template(self, template_id: str) -> BotTemplateResponse:
        with get_db_session() as session:
            self.ensure_default_templates(session)
            template = session.query(BotTemplate).filter(BotTemplate.id == template_id).first()
            if template is None:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Bot template not found")
            return BotTemplateResponse.model_validate(template)

    def create_user_bot(self, user_id: str, payload: UserBotCreate) -> UserBotResponse:
        with get_db_session() as session:
            self.ensure_default_templates(session)
            template = (
                session.query(BotTemplate)
                .filter(
                    BotTemplate.id == payload.bot_template_id,
                    BotTemplate.status == "published",
                )
                .first()
            )
            if template is None:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Published bot template not found")

            existing = (
                session.query(UserBotInstance)
                .filter(
                    UserBotInstance.user_id == user_id,
                    UserBotInstance.bot_template_id == template.id,
                )
                .first()
            )
            if existing is not None:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="This bot is already selected by the user",
                )

            instance = UserBotInstance(
                user_id=user_id,
                bot_template_id=template.id,
                exchange_credential_id=None,
                mode="TESTNET",
                status="STOPPED",
                auto_trade_enabled=False,
                config_snapshot=self._snapshot_template(template),
            )
            session.add(instance)
            session.flush()
            session.refresh(instance)
            return self._instance_response(instance)

    def list_user_bots(self, user_id: str) -> list[UserBotResponse]:
        with get_db_session() as session:
            self.ensure_default_templates(session)
            instances = (
                session.query(UserBotInstance)
                .filter(UserBotInstance.user_id == user_id)
                .order_by(UserBotInstance.created_at.desc())
                .all()
            )
            return [self._instance_response(instance) for instance in instances]

    def get_user_bot(self, user_id: str, instance_id: str) -> UserBotResponse:
        with get_db_session() as session:
            instance = self._get_user_instance(session, user_id, instance_id)
            return self._instance_response(instance)

    def start_user_bot(self, user_id: str, instance_id: str) -> BotActionResponse:
        with get_db_session() as session:
            instance = self._get_user_instance(session, user_id, instance_id)
            exchange = str((instance.config_snapshot or {}).get("exchange", "binance"))
            credential_id = self._active_credential_id(session, user_id, exchange)
            if not credential_id:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"{exchange} credentials are required before starting a bot",
                )

            instance.exchange_credential_id = credential_id
            instance.status = "ACTIVE"
            instance.auto_trade_enabled = True
            self._ensure_running_run(session, instance)
            session.flush()
            session.refresh(instance)
            return BotActionResponse(
                message="Bot started with its locked template configuration.",
                bot=self._instance_response(instance),
            )

    def pause_user_bot(self, user_id: str, instance_id: str) -> BotActionResponse:
        with get_db_session() as session:
            instance = self._get_user_instance(session, user_id, instance_id)
            instance.status = "PAUSED"
            instance.auto_trade_enabled = False
            session.flush()
            session.refresh(instance)
            return BotActionResponse(message="Bot paused.", bot=self._instance_response(instance))

    def stop_user_bot(self, user_id: str, instance_id: str) -> BotActionResponse:
        with get_db_session() as session:
            instance = self._get_user_instance(session, user_id, instance_id)
            instance.status = "STOPPED"
            instance.auto_trade_enabled = False
            now = datetime.now(UTC)
            for run in instance.runs:
                if run.status == "RUNNING" and run.ended_at is None:
                    run.status = "STOPPED"
                    run.ended_at = now
            session.flush()
            session.refresh(instance)
            return BotActionResponse(message="Bot stopped.", bot=self._instance_response(instance))

    def list_decisions(self, user_id: str, instance_id: str) -> list[TradingDecisionResponse]:
        with get_db_session() as session:
            instance = self._get_user_instance(session, user_id, instance_id)
            decisions = (
                session.query(TradingDecision)
                .filter(TradingDecision.user_bot_instance_id == instance.id)
                .order_by(TradingDecision.timestamp.desc())
                .limit(100)
                .all()
            )
            return [TradingDecisionResponse.model_validate(decision) for decision in decisions]

    def list_orders(self, user_id: str, instance_id: str) -> list[BotOrderResponse]:
        with get_db_session() as session:
            instance = self._get_user_instance(session, user_id, instance_id)
            orders = (
                session.query(BotOrder)
                .filter(BotOrder.user_bot_instance_id == instance.id)
                .order_by(BotOrder.created_at.desc())
                .limit(100)
                .all()
            )
            return [BotOrderResponse.model_validate(order) for order in orders]

    def list_trades(self, user_id: str, instance_id: str) -> list[BotTradeResponse]:
        with get_db_session() as session:
            instance = self._get_user_instance(session, user_id, instance_id)
            trades = (
                session.query(BotTrade)
                .filter(BotTrade.user_bot_instance_id == instance.id)
                .order_by(BotTrade.trade_time.desc())
                .limit(100)
                .all()
            )
            return [BotTradeResponse.model_validate(trade) for trade in trades]

    def get_position(self, user_id: str, instance_id: str) -> BotPositionResponse | None:
        with get_db_session() as session:
            instance = self._get_user_instance(session, user_id, instance_id)
            if not instance.position:
                return None
            return BotPositionResponse.model_validate(instance.position)

    def get_performance(self, user_id: str, instance_id: str) -> BotPerformanceResponse:
        with get_db_session() as session:
            instance = self._get_user_instance(session, user_id, instance_id)
            snapshot = dict(instance.config_snapshot or {})
            position = instance.position
            last_decision = (
                session.query(TradingDecision)
                .filter(TradingDecision.user_bot_instance_id == instance.id)
                .order_by(TradingDecision.timestamp.desc())
                .first()
            )
            total_orders = session.query(BotOrder).filter(BotOrder.user_bot_instance_id == instance.id).count()
            total_trades = session.query(BotTrade).filter(BotTrade.user_bot_instance_id == instance.id).count()
            return BotPerformanceResponse(
                user_bot_instance_id=instance.id,
                symbol=str(snapshot.get("symbol") or ""),
                status=instance.status,
                total_orders=total_orders,
                total_trades=total_trades,
                realized_pnl=self._decimal(position.realized_pnl if position else None),
                unrealized_pnl=self._decimal(position.unrealized_pnl if position else None),
                net_position_quantity=self._decimal(position.quantity if position else None),
                average_entry_price=position.average_entry_price if position else None,
                last_signal=last_decision.strategy_signal if last_decision else None,
                last_action=last_decision.final_action if last_decision else None,
                last_decision_at=last_decision.timestamp if last_decision else None,
            )

    def get_user_performance_summary(
        self,
        user_id: str,
        *,
        period_days: int = 30,
        bot_id: str | None = None,
        model_name: str | None = None,
    ) -> UserPerformanceSummaryResponse:
        now = datetime.now(UTC)
        normalized_period_days = max(period_days, 0)
        period_start = None if normalized_period_days == 0 else now - timedelta(days=normalized_period_days)
        period_start_db = self._db_datetime(period_start)
        unavailable: list[PerformanceUnavailableReason] = []
        unavailable_keys: set[tuple[str, str]] = set()

        def add_unavailable(field: str, reason: str) -> None:
            key = (field, reason)
            if key in unavailable_keys:
                return
            unavailable_keys.add(key)
            unavailable.append(PerformanceUnavailableReason(field=field, reason=reason))

        with get_db_session() as session:
            query = session.query(UserBotInstance).filter(UserBotInstance.user_id == user_id)
            if bot_id:
                query = query.filter(UserBotInstance.id == bot_id)
            instances = query.order_by(UserBotInstance.created_at.asc()).all()

            bot_rows: list[BotPerformanceContributionResponse] = []
            decision_rows: list[PerformanceDecisionHistoryResponse] = []
            order_rows: list[PerformanceOrderHistoryResponse] = []
            trade_rows: list[PerformanceTradeHistoryResponse] = []
            trade_points: list[tuple[datetime, str, str, Decimal]] = []
            total_realized = Decimal("0")
            total_unrealized = Decimal("0")
            total_orders = 0
            total_trades = 0
            initial_capital = Decimal("0")
            initial_capital_available = True
            total_pnl_available = True
            win_rate_values: list[Decimal] = []
            ticker_cache: dict[str, Decimal | None] = {}

            for instance in instances:
                snapshot = dict(instance.config_snapshot or {})
                bot_name = str(snapshot.get("name") or instance.id)

                decisions_query = (
                    session.query(TradingDecision)
                    .filter(TradingDecision.user_bot_instance_id == instance.id)
                    .order_by(TradingDecision.timestamp.desc())
                )
                orders_query = (
                    session.query(BotOrder)
                    .filter(BotOrder.user_bot_instance_id == instance.id)
                    .order_by(BotOrder.created_at.desc())
                )
                trades_query = (
                    session.query(BotTrade)
                    .filter(BotTrade.user_bot_instance_id == instance.id)
                    .order_by(BotTrade.trade_time.desc())
                )
                if period_start_db is not None:
                    decisions_query = decisions_query.filter(TradingDecision.timestamp >= period_start_db)
                    orders_query = orders_query.filter(BotOrder.created_at >= period_start_db)
                    trades_query = trades_query.filter(BotTrade.trade_time >= period_start_db)

                decisions = decisions_query.all()
                orders = orders_query.all()
                trades = trades_query.all()
                latest_trace = self._latest_trace_metadata(decisions, snapshot)
                resolved_model_name = latest_trace.get("model_name")
                if model_name and resolved_model_name != model_name:
                    continue

                configured_capital = self._configured_quote_capital(snapshot)
                if configured_capital is None:
                    initial_capital_available = False
                    add_unavailable(
                        "capital_initial",
                        f"Capital initial indisponible pour {bot_name}: aucun montant order_policy.quote_order_quantity.",
                    )
                else:
                    initial_capital += configured_capital

                realized_pnl = Decimal("0")
                for trade in trades:
                    trade_realized = self._trade_realized_pnl(trade)
                    if trade_realized is None:
                        if str(trade.side).upper() == "SELL":
                            add_unavailable(
                                "pnl_realized",
                                f"PnL realise incomplet pour {bot_name}: un trade SELL n'a pas de realized_pnl.",
                            )
                        trade_realized = Decimal("0")
                    else:
                        if trade_realized != 0:
                            win_rate_values.append(trade_realized)
                    realized_pnl += trade_realized
                    trade_points.append((self._utc_datetime(trade.trade_time), instance.id, bot_name, trade_realized))

                unrealized_pnl, unrealized_reason = self._position_unrealized_pnl(
                    instance=instance,
                    snapshot=snapshot,
                    ticker_cache=ticker_cache,
                )
                if unrealized_reason:
                    total_pnl_available = False
                    add_unavailable("pnl_unrealized", f"{bot_name}: {unrealized_reason}")

                bot_total_pnl = realized_pnl + unrealized_pnl if unrealized_pnl is not None else None
                if bot_total_pnl is None:
                    total_pnl_available = False
                else:
                    total_unrealized += unrealized_pnl or Decimal("0")

                confidence_values = [
                    value
                    for value in (self._decision_confidence(decision) for decision in decisions)
                    if value is not None
                ]
                average_confidence = sum(confidence_values) / len(confidence_values) if confidence_values else None
                latest_decision = decisions[0] if decisions else None

                bot_rows.append(
                    BotPerformanceContributionResponse(
                        bot_id=instance.id,
                        bot_name=bot_name,
                        model_name=resolved_model_name,
                        model_version=latest_trace.get("model_version"),
                        pnl_total=bot_total_pnl,
                        pnl_realized=realized_pnl,
                        pnl_unrealized=unrealized_pnl,
                        orders=len(orders),
                        trades=len(trades),
                        last_decision=latest_decision.final_action if latest_decision else None,
                        last_decision_at=(self._utc_datetime(latest_decision.timestamp) if latest_decision else None),
                        last_ai_signal=latest_trace.get("raw_ai_signal") or latest_trace.get("deterministic_signal"),
                        average_confidence=average_confidence,
                    )
                )

                total_realized += realized_pnl
                total_orders += len(orders)
                total_trades += len(trades)

                for decision in decisions:
                    trace = self._decision_trace_metadata(decision, snapshot)
                    decision_rows.append(
                        PerformanceDecisionHistoryResponse(
                            id=decision.id,
                            bot_id=instance.id,
                            bot_name=bot_name,
                            timestamp=self._utc_datetime(decision.timestamp),
                            model_source=trace.get("model_source"),
                            registry_source=trace.get("registry_source"),
                            model_name=trace.get("model_name"),
                            model_version=trace.get("model_version"),
                            confidence=trace.get("confidence"),
                            raw_ai_signal=trace.get("raw_ai_signal"),
                            deterministic_signal=trace.get("deterministic_signal"),
                            final_action=decision.final_action,
                            risk_decision=decision.risk_decision,
                            reason=decision.reason,
                        )
                    )

                for order in orders:
                    order_rows.append(
                        PerformanceOrderHistoryResponse(
                            id=order.id,
                            bot_id=instance.id,
                            bot_name=bot_name,
                            created_at=self._utc_datetime(order.created_at),
                            symbol=order.symbol,
                            side=order.side,
                            order_type=order.order_type,
                            status=order.status,
                            binance_order_id=order.binance_order_id,
                            quote_order_quantity=order.quote_order_quantity,
                            quantity=order.quantity,
                        )
                    )

                for trade in trades:
                    trade_rows.append(
                        PerformanceTradeHistoryResponse(
                            id=trade.id,
                            bot_id=instance.id,
                            bot_name=bot_name,
                            order_id=trade.order_id,
                            trade_time=self._utc_datetime(trade.trade_time),
                            symbol=trade.symbol,
                            side=trade.side,
                            quantity=trade.quantity,
                            price=trade.price,
                            fee=trade.fee,
                            fee_asset=trade.fee_asset,
                            realized_pnl=self._trade_realized_pnl(trade),
                        )
                    )

            if not instances:
                add_unavailable("bots", "Aucun bot utilisateur ne correspond aux filtres.")
            elif not bot_rows:
                add_unavailable("bots", "Aucun bot utilisateur ne correspond au filtre modele.")

            if not win_rate_values:
                win_rate_pct = None
                add_unavailable(
                    "win_rate_pct",
                    "Win rate indisponible: aucun trade ferme avec PnL realise non nul sur la periode.",
                )
            else:
                wins = sum(1 for pnl in win_rate_values if pnl > 0)
                win_rate_pct = wins / len(win_rate_values) * 100

            total_pnl = total_realized + total_unrealized if total_pnl_available else None
            if total_pnl is None:
                add_unavailable(
                    "pnl_total",
                    "PnL total indisponible: au moins une position ouverte ne peut pas etre valorisee.",
                )

            capital_initial_value = initial_capital if initial_capital_available else None
            capital_current = (
                capital_initial_value + total_pnl
                if capital_initial_value is not None and total_pnl is not None
                else None
            )
            if capital_current is None:
                add_unavailable(
                    "capital_current",
                    "Capital actuel indisponible: capital initial ou PnL total incomplet.",
                )

            if total_pnl is not None and total_pnl != 0:
                for row in bot_rows:
                    if row.pnl_total is not None:
                        row.pnl_contribution_pct = float(row.pnl_total / total_pnl * Decimal("100"))

            decision_rows.sort(key=lambda row: row.timestamp, reverse=True)
            order_rows.sort(key=lambda row: row.created_at, reverse=True)
            trade_rows.sort(key=lambda row: row.trade_time, reverse=True)

            pnl_curve = self._build_pnl_curve(
                trade_points=trade_points,
                period_start=period_start,
                period_end=now,
                initial_capital=capital_initial_value,
            )

            return UserPerformanceSummaryResponse(
                generated_at=now,
                period_start=period_start,
                period_end=now,
                period_days=normalized_period_days,
                bot_id=bot_id,
                model_name=model_name,
                unavailable_reasons=unavailable,
                global_performance=UserPerformanceGlobalResponse(
                    capital_initial=capital_initial_value,
                    capital_current=capital_current,
                    pnl_total=total_pnl,
                    pnl_realized=total_realized,
                    pnl_unrealized=total_unrealized if total_pnl_available else None,
                    total_orders=total_orders,
                    total_trades=total_trades,
                    win_rate_pct=win_rate_pct,
                ),
                bots=sorted(bot_rows, key=lambda row: row.bot_name.lower()),
                decisions=decision_rows,
                orders=order_rows,
                trades=trade_rows,
                pnl_curve=pnl_curve,
            )

    def execute_once(self, instance_id: str, *, worker_id: str = "manual-worker") -> TradingDecisionResponse:
        """Execute one locked-template worker pass against the template's exchange."""
        with get_db_session() as session:
            instance = session.query(UserBotInstance).filter(UserBotInstance.id == instance_id).first()
            if instance is None:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User bot not found")
            if instance.status != "ACTIVE":
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Bot is not active")

            run = self._ensure_running_run(session, instance, worker_id=worker_id)
            snapshot = instance.config_snapshot
            now = datetime.now(UTC)
            try:
                return self._execute_locked_instance(session, instance, run, snapshot, now)
            except Exception as exc:
                detail = self._error_detail(exc)
                decision = self._record_decision(
                    session,
                    instance,
                    run,
                    timestamp=now,
                    market_snapshot={},
                    model_output={"error": detail},
                    strategy_signal="ERROR",
                    risk_decision="ERROR",
                    final_action="ERROR",
                    reason=detail,
                )
                run.status = "ERROR"
                run.error_message = detail
                run.ended_at = now
                instance.status = "ERROR"
                instance.auto_trade_enabled = False
                session.flush()
                session.refresh(decision)
                return TradingDecisionResponse.model_validate(decision)

    def execute_active_once(
        self, *, worker_id: str = "manual-worker", limit: int = 100
    ) -> list[TradingDecisionResponse]:
        with get_db_session() as session:
            active_ids = [
                row[0]
                for row in session.query(UserBotInstance.id)
                .filter(
                    UserBotInstance.status == "ACTIVE",
                    UserBotInstance.auto_trade_enabled.is_(True),
                )
                .limit(limit)
                .all()
            ]
        return [self.execute_once(instance_id, worker_id=worker_id) for instance_id in active_ids]

    def _execute_locked_instance(
        self,
        session: Session,
        instance: UserBotInstance,
        run: BotRun,
        snapshot: dict[str, Any],
        now: datetime,
    ) -> TradingDecisionResponse:
        market_snapshot, model_output, strategy_signal, requested_action = self._compute_template_signal(snapshot)
        if model_output.get("status") == "SKIP_MODEL_UNAVAILABLE":
            risk_decision = "SKIP_MODEL_UNAVAILABLE"
            final_action = "HOLD"
            reason = f"Model unavailable: {model_output.get('error') or 'MLflow model cannot be used'}"
        else:
            risk_decision, final_action, reason = self._evaluate_risk(
                session,
                instance,
                snapshot,
                requested_action,
                now,
            )

        decision = self._record_decision(
            session,
            instance,
            run,
            timestamp=now,
            market_snapshot=market_snapshot,
            model_output=model_output,
            strategy_signal=strategy_signal,
            risk_decision=risk_decision,
            final_action=final_action,
            reason=reason,
        )

        if final_action in {"BUY", "SELL"}:
            order_request = self._build_order_request(session, instance, snapshot, final_action, now)
            exchange = str(snapshot.get("exchange", "binance"))
            response = self.execution_gateway.place_order(instance.user_id, order_request, exchange=exchange)
            order = self._record_order(session, instance, snapshot, order_request, response)
            self._record_trades_and_position(session, instance, order, response)
            decision.reason = f"{reason} Order sent to {exchange}."

        instance.last_decision_at = now
        session.flush()
        session.refresh(decision)
        return TradingDecisionResponse.model_validate(decision)

    def _compute_template_signal(self, snapshot: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any], str, str]:
        if str(snapshot.get("strategy_type")) == PAIR_QUALIFIED_ML_STRATEGY_TYPE:
            # Pas de moteur de regles techniques ici (strategy.engine.registry n'a jamais
            # connu PAIR_QUALIFIED_ML_STRATEGY_TYPE) -- le signal vient entierement du
            # modele MLflow qualifie par paire, cf. _compute_pair_qualified_ml_signal().
            return self._compute_pair_qualified_ml_signal(snapshot)

        symbol = str(snapshot["symbol"])
        timeframe = str(snapshot["timeframe"])
        strategy_type = str(snapshot["strategy_type"])
        exchange = str(snapshot.get("exchange", "binance"))
        klines = self.execution_gateway.klines(symbol, timeframe, limit=160, exchange=exchange)
        if len(klines) < 20:
            raise RuntimeError(f"Insufficient market data for {exchange} {symbol} {timeframe}")

        frame = self._klines_to_frame(klines)
        strategy = self._create_strategy(strategy_type, snapshot)
        processed = strategy.pre_process(frame)
        signals = strategy.compute_signals(processed)
        if signals.empty:
            raise RuntimeError(f"Strategy {strategy_type} returned no signal rows")

        last_row = signals.iloc[-1]
        raw_signal = int(self._clean_value(last_row.get("signal", 0)) or 0)
        strategy_action = "BUY" if raw_signal > 0 else "SELL" if raw_signal < 0 else "HOLD"
        indicators = {
            key: self._clean_value(value)
            for key, value in last_row.to_dict().items()
            if key not in {"open", "high", "low", "close", "volume", "signal"}
        }
        market_snapshot = {
            "symbol": symbol,
            "timeframe": timeframe,
            "open_time": self._clean_value(last_row.get("open_time")),
            "open": self._clean_value(last_row.get("open")),
            "high": self._clean_value(last_row.get("high")),
            "low": self._clean_value(last_row.get("low")),
            "close": self._clean_value(last_row.get("close")),
            "volume": self._clean_value(last_row.get("volume")),
        }
        if self._uses_mlflow_rsi_model(snapshot):
            return self._compute_mlflow_rsi_signal(
                snapshot=snapshot,
                processed=processed,
                last_row=last_row,
                market_snapshot=market_snapshot,
                indicators=indicators,
                raw_signal=raw_signal,
                deterministic_signal=strategy_action,
            )

        model_result = evaluate_template_model(str(snapshot["model_type"]), last_row.to_dict(), strategy_action)
        requested_action = strategy_action if model_result["trade_allowed"] else "HOLD"
        model_output = {
            "model_type": snapshot["model_type"],
            "signal_source": snapshot["signal_source"],
            "strategy_type": strategy_type,
            "model_result": model_result,
            "raw_signal": raw_signal,
            "strategy_action": strategy_action,
            "action": requested_action,
            "indicators": indicators,
        }
        return market_snapshot, model_output, strategy_action, requested_action

    def _compute_mlflow_rsi_signal(
        self,
        *,
        snapshot: dict[str, Any],
        processed: Any,
        last_row: Any,
        market_snapshot: dict[str, Any],
        indicators: dict[str, Any],
        raw_signal: int,
        deterministic_signal: str,
    ) -> tuple[dict[str, Any], dict[str, Any], str, str]:
        params = dict(snapshot.get("execution_params") or {})
        model_name = str(params.get("mlflow_model_name") or MLFLOW_RSI_MODEL_NAME)
        configured_version = params.get("mlflow_model_version")
        model_version = str(configured_version) if configured_version else None
        deterministic_model_result = evaluate_template_model(
            "regime_classifier_v1",
            last_row.to_dict(),
            deterministic_signal,
        )

        try:
            features = self._extract_rsi_ml_features(processed, last_row)
            prediction = self.ml_client.predict(
                model_name=model_name,
                model_version=model_version,
                features=features,
            )
            ai_signal = str(prediction.get("signal") or "").upper()
            if ai_signal not in {"BUY", "SELL", "HOLD"}:
                raise BotModelUnavailable(f"Invalid ML signal received: {ai_signal or '<empty>'}")
            requested_action = ai_signal if ai_signal in {"BUY", "SELL"} else "HOLD"
            served_version = str(prediction.get("model_version") or model_version or "unknown")
            confidence = self._clean_value(prediction.get("confidence"))
            model_output = {
                "model_type": snapshot["model_type"],
                "model_source": "ml_api",
                "registry_source": prediction.get("model_source") or "mlflow",
                "model_name": prediction.get("model_name") or model_name,
                "model_version": served_version,
                "signal_source": snapshot["signal_source"],
                "strategy_type": snapshot["strategy_type"],
                "confidence": confidence,
                "probabilities": prediction.get("probabilities") or {},
                "features": features,
                "raw_ai_signal": ai_signal,
                "deterministic_signal": deterministic_signal,
                "deterministic_raw_signal": raw_signal,
                "deterministic_model_result": deterministic_model_result,
                "comparison_mode": True,
                "action": requested_action,
                "indicators": indicators,
            }
            return market_snapshot, model_output, ai_signal, requested_action
        except BotModelUnavailable as exc:
            model_output = {
                "model_type": snapshot["model_type"],
                "model_source": "ml_api",
                "registry_source": "mlflow",
                "model_name": model_name,
                "model_version": model_version,
                "signal_source": snapshot["signal_source"],
                "strategy_type": snapshot["strategy_type"],
                "status": "SKIP_MODEL_UNAVAILABLE",
                "error": str(exc),
                "features": self._safe_rsi_ml_features(processed, last_row),
                "raw_ai_signal": None,
                "deterministic_signal": deterministic_signal,
                "deterministic_raw_signal": raw_signal,
                "deterministic_model_result": deterministic_model_result,
                "comparison_mode": True,
                "action": "HOLD",
                "indicators": indicators,
            }
            return market_snapshot, model_output, MODEL_UNAVAILABLE_STRATEGY_SIGNAL, "HOLD"

    def _compute_pair_qualified_ml_signal(
        self, snapshot: dict[str, Any]
    ) -> tuple[dict[str, Any], dict[str, Any], str, str]:
        """Signal pour un template genere par _generate_ml_templates() (chemin B : modele
        MLflow qualifie par paire, ex. "random_forest_btcusdc"). Contrairement au chemin
        RSI historique, il n'y a pas de strategie technique de reference ici -- le modele
        entraine EST la strategie (decision actee, cf. memoire "strategy/engine archive").

        Les features sont recalculees en direct depuis les klines (build_live_feature_frame,
        deja utilise par backend/src/strategy/service.py pour le chemin A) puis transmises
        telles quelles au ml-api : c'est predict_registered_bot_model() (chemin B) qui filtre
        et ordonne les colonnes selon l'artefact feature_columns.json du run d'entrainement --
        pas de liste de colonnes dupliquee ici.
        """
        symbol = str(snapshot["symbol"])
        timeframe = str(snapshot["timeframe"])
        params = dict(snapshot.get("execution_params") or {})
        registry_model_name = str(params["registry_model_name"])

        frame = build_live_feature_frame(symbol, timeframe)
        if frame.empty:
            raise RuntimeError(f"No live feature data available for {symbol} {timeframe}")
        last_row = frame.iloc[-1]

        market_snapshot = {
            "symbol": symbol,
            "timeframe": timeframe,
            "open_time": self._clean_value(last_row.get("open_time")),
            "open": self._clean_value(last_row.get("open")),
            "high": self._clean_value(last_row.get("high")),
            "low": self._clean_value(last_row.get("low")),
            "close": self._clean_value(last_row.get("close")),
            "volume": self._clean_value(last_row.get("volume")),
        }
        features = {
            column: value
            for column, value in ((col, self._feature_float(last_row.get(col))) for col in frame.columns)
            if value is not None
        }

        try:
            prediction = self.ml_client.predict(model_name=registry_model_name, features=features)
            ai_signal = str(prediction.get("signal") or "").upper()
            if ai_signal not in {"BUY", "SELL", "HOLD"}:
                raise BotModelUnavailable(f"Invalid ML signal received: {ai_signal or '<empty>'}")
            model_output = {
                "model_type": snapshot["model_type"],
                "model_source": "ml_api",
                "registry_source": prediction.get("model_source") or "mlflow",
                "model_name": prediction.get("model_name") or registry_model_name,
                "model_version": prediction.get("model_version"),
                "signal_source": snapshot["signal_source"],
                "strategy_type": snapshot["strategy_type"],
                "confidence": self._clean_value(prediction.get("confidence")),
                "probabilities": prediction.get("probabilities") or {},
                "features": features,
                "action": ai_signal,
                # raw_ai_signal : meme cle que le chemin RSI legacy (_compute_mlflow_rsi_
                # signal), lue par le frontend (04_Performances_Spot.py, colonne "Signal
                # IA") -- sans elle la colonne affiche "Donnee indisponible" pour tout bot
                # de ce chemin, meme quand le modele a bien repondu.
                "raw_ai_signal": ai_signal,
                "indicators": {},
            }
            return market_snapshot, model_output, ai_signal, ai_signal
        except BotModelUnavailable as exc:
            model_output = {
                "model_type": snapshot["model_type"],
                "model_source": "ml_api",
                "registry_source": "mlflow",
                "model_name": registry_model_name,
                "signal_source": snapshot["signal_source"],
                "strategy_type": snapshot["strategy_type"],
                "status": "SKIP_MODEL_UNAVAILABLE",
                "error": str(exc),
                "features": features,
                "action": "HOLD",
                "indicators": {},
            }
            return market_snapshot, model_output, MODEL_UNAVAILABLE_STRATEGY_SIGNAL, "HOLD"

    @staticmethod
    def _uses_mlflow_rsi_model(snapshot: dict[str, Any]) -> bool:
        return (
            str(snapshot.get("model_type")) == MLFLOW_RSI_MODEL_TYPE
            and str(snapshot.get("symbol", "")).upper() == _RSI_TEMPLATE_SYMBOL
            and str(snapshot.get("timeframe")) == "1h"
            and str(snapshot.get("strategy_type")) == "rsi_reversal"
        )

    @classmethod
    def _safe_rsi_ml_features(cls, processed: Any, last_row: Any) -> dict[str, float | None]:
        try:
            return cls._extract_rsi_ml_features(processed, last_row)
        except BotModelUnavailable:
            return {
                "rsi": None,
                "price_change": None,
                "volume": None,
                "sma_short": None,
                "sma_long": None,
            }

    @classmethod
    def _extract_rsi_ml_features(cls, processed: Any, last_row: Any) -> dict[str, float]:
        close = processed["close"]
        features = {
            "rsi": cls._feature_float(last_row.get("rsi")),
            "price_change": cls._feature_float(close.pct_change().iloc[-1]),
            "volume": cls._feature_float(last_row.get("volume")),
            "sma_short": cls._feature_float(close.rolling(10).mean().iloc[-1]),
            "sma_long": cls._feature_float(close.rolling(30).mean().iloc[-1]),
        }
        missing = [name for name, value in features.items() if value is None]
        if missing:
            raise BotModelUnavailable(f"Required ML features missing: {', '.join(missing)}")
        return {name: value for name, value in features.items() if value is not None}

    @staticmethod
    def _feature_float(value: Any) -> float | None:
        cleaned = BotService._clean_value(value)
        if cleaned is None:
            return None
        try:
            return float(cleaned)
        except (TypeError, ValueError):
            return None

    def _evaluate_risk(
        self,
        session: Session,
        instance: UserBotInstance,
        snapshot: dict[str, Any],
        requested_action: str,
        now: datetime,
    ) -> tuple[str, str, str]:
        if requested_action == "HOLD":
            return "PASS", "HOLD", "No actionable signal on this worker pass."

        symbol = str(snapshot["symbol"])
        exchange = str(snapshot.get("exchange", "binance"))
        environment = str(snapshot.get("environment", "testnet")).lower()
        if environment != "testnet":
            return "BLOCKED", "HOLD", "Risk gate blocked: only templates published for testnet are enabled."

        credential_id = instance.exchange_credential_id or self._active_credential_id(
            session, instance.user_id, exchange
        )
        if not credential_id:
            return "BLOCKED", "HOLD", f"Risk gate blocked: {exchange} credentials are required."

        symbol_status = self._symbol_trade_status(symbol, exchange=exchange)
        if not symbol_status["tradeable"]:
            return "BLOCKED", "HOLD", f"Risk gate blocked: {symbol_status['reason']}."

        risk_limits = dict(snapshot.get("risk_limits") or {})
        order_policy = dict(snapshot.get("order_policy") or {})
        max_open_orders = int(risk_limits.get("max_open_orders", 1))
        open_orders = self.execution_gateway.open_orders(instance.user_id, symbol, exchange=exchange)
        if len(open_orders) >= max_open_orders:
            return "BLOCKED", "HOLD", f"Risk gate blocked: max_open_orders={max_open_orders}."

        cooldown_seconds = int(order_policy.get("cooldown_seconds", 0) or 0)
        last_trade_decision = (
            session.query(TradingDecision)
            .filter(
                TradingDecision.user_bot_instance_id == instance.id,
                TradingDecision.final_action.in_(["BUY", "SELL"]),
            )
            .order_by(TradingDecision.timestamp.desc())
            .first()
        )
        if last_trade_decision and cooldown_seconds > 0:
            elapsed_seconds = self._elapsed_seconds(last_trade_decision.timestamp, now)
            if elapsed_seconds < cooldown_seconds:
                return (
                    "BLOCKED",
                    "HOLD",
                    f"Risk gate blocked: cooldown active for {cooldown_seconds - elapsed_seconds:.0f}s.",
                )

        base_asset, quote_asset = self._split_symbol(symbol, str(order_policy.get("quote_asset", "USDT")))
        balances = self.execution_gateway.balances(instance.user_id, non_zero=False, exchange=exchange)
        if requested_action == "BUY":
            quote_order_quantity = self._decimal(order_policy.get("quote_order_quantity"))
            max_order_quote_quantity = self._decimal(risk_limits.get("max_order_quote_quantity"))
            free_quote = self._free_balance(balances, quote_asset)
            position = session.query(BotPosition).filter(BotPosition.user_bot_instance_id == instance.id).first()
            if position and self._decimal(position.quantity) > 0:
                return "BLOCKED", "HOLD", "Risk gate blocked: bot already has an open managed position."
            if quote_order_quantity <= 0:
                return "BLOCKED", "HOLD", "Risk gate blocked: invalid quote order quantity."
            if max_order_quote_quantity > 0 and quote_order_quantity > max_order_quote_quantity:
                return "BLOCKED", "HOLD", "Risk gate blocked: order quantity exceeds template max order size."
            max_user_open_positions = int(risk_limits.get("max_user_open_positions", 0) or 0)
            if max_user_open_positions > 0:
                open_position_count = self._user_open_position_count(session, instance.user_id)
                if open_position_count >= max_user_open_positions:
                    return (
                        "BLOCKED",
                        "HOLD",
                        f"Risk gate blocked: max_user_open_positions={max_user_open_positions}.",
                    )
            daily_loss_status = self._daily_loss_status(
                session,
                instance,
                now,
                risk_limits,
                free_quote,
                quote_asset,
            )
            if not daily_loss_status["allowed"]:
                return "BLOCKED", "HOLD", f"Risk gate blocked: {daily_loss_status['reason']}."
            if free_quote < quote_order_quantity:
                return "BLOCKED", "HOLD", f"Risk gate blocked: insufficient {quote_asset} balance."
            return "PASS", "BUY", "Risk gate passed for BUY."

        sell_quantity = self._sell_quantity(session, instance, snapshot)
        free_base = self._free_balance(balances, base_asset)
        if sell_quantity <= 0:
            return "BLOCKED", "HOLD", f"Risk gate blocked: no bot-managed {base_asset} position to sell."
        if free_base < sell_quantity:
            return "BLOCKED", "HOLD", f"Risk gate blocked: no {base_asset} position to sell."
        return "PASS", "SELL", "Risk gate passed for SELL."

    def _daily_loss_status(
        self,
        session: Session,
        instance: UserBotInstance,
        now: datetime,
        risk_limits: dict[str, Any],
        quote_balance: Decimal,
        quote_asset: str,
    ) -> dict[str, Any]:
        max_daily_loss_pct = self._decimal(risk_limits.get("max_daily_loss_pct"))
        if max_daily_loss_pct <= 0 or quote_balance <= 0:
            return {"allowed": True, "reason": "daily loss limit not configured"}

        loss_limit = quote_balance * max_daily_loss_pct / Decimal("100")
        daily_pnl = self._daily_realized_pnl(session, instance, now)
        if daily_pnl < 0 and abs(daily_pnl) >= loss_limit:
            return {
                "allowed": False,
                "reason": (
                    f"daily loss limit reached ({abs(daily_pnl):.8f} {quote_asset} >= {loss_limit:.8f} {quote_asset})"
                ),
            }
        return {"allowed": True, "reason": "daily loss limit not reached"}

    def _daily_realized_pnl(self, session: Session, instance: UserBotInstance, now: datetime) -> Decimal:
        if now.tzinfo is None:
            day_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        else:
            day_start = now.astimezone(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
        trades = (
            session.query(BotTrade)
            .filter(
                BotTrade.user_bot_instance_id == instance.id,
                BotTrade.side == "SELL",
                BotTrade.trade_time >= day_start,
            )
            .all()
        )
        total = Decimal("0")
        for trade in trades:
            raw_response = trade.raw_response if isinstance(trade.raw_response, dict) else {}
            total += self._decimal(raw_response.get("realized_pnl"))
        return total

    @staticmethod
    def _user_open_position_count(session: Session, user_id: str) -> int:
        positions = session.query(BotPosition).filter(BotPosition.user_id == user_id).all()
        return sum(1 for position in positions if BotService._decimal(position.quantity) > 0)

    @classmethod
    def _latest_trace_metadata(
        cls,
        decisions: list[TradingDecision],
        snapshot: dict[str, Any],
    ) -> dict[str, Any]:
        for decision in decisions:
            trace = cls._decision_trace_metadata(decision, snapshot)
            if trace.get("model_name"):
                return trace
        return cls._snapshot_trace_metadata(snapshot)

    @classmethod
    def _decision_trace_metadata(
        cls,
        decision: TradingDecision,
        snapshot: dict[str, Any],
    ) -> dict[str, Any]:
        model_output = cls._mapping(decision.model_output)
        model_result = cls._mapping(model_output.get("model_result"))
        snapshot_trace = cls._snapshot_trace_metadata(snapshot)
        confidence = cls._float_or_none(model_output.get("confidence"))
        model_source = model_output.get("model_source") or snapshot_trace.get("model_source")
        deterministic_signal = (
            model_output.get("deterministic_signal") or model_output.get("strategy_action") or decision.strategy_signal
        )
        return {
            "model_source": str(model_source) if model_source is not None else None,
            "registry_source": model_output.get("registry_source") or snapshot_trace.get("registry_source"),
            "model_name": (
                model_output.get("model_name")
                or model_output.get("model_type")
                or model_result.get("model_type")
                or snapshot_trace.get("model_name")
            ),
            "model_version": model_output.get("model_version") or snapshot_trace.get("model_version"),
            "confidence": confidence,
            "raw_ai_signal": model_output.get("raw_ai_signal"),
            "deterministic_signal": deterministic_signal,
        }

    @staticmethod
    def _snapshot_trace_metadata(snapshot: dict[str, Any]) -> dict[str, Any]:
        params = dict(snapshot.get("execution_params") or {})
        model_name = params.get("mlflow_model_name") or snapshot.get("model_type")
        registry_source = "mlflow" if params.get("mlflow_model_name") else None
        model_source = "ml_api" if params.get("mlflow_model_name") else "deterministic"
        return {
            "model_source": model_source,
            "registry_source": registry_source,
            "model_name": str(model_name) if model_name is not None else None,
            "model_version": (
                str(params["mlflow_model_version"]) if params.get("mlflow_model_version") is not None else None
            ),
            "confidence": None,
            "raw_ai_signal": None,
            "deterministic_signal": None,
        }

    @classmethod
    def _decision_confidence(cls, decision: TradingDecision) -> float | None:
        model_output = cls._mapping(decision.model_output)
        return cls._float_or_none(model_output.get("confidence"))

    @classmethod
    def _configured_quote_capital(cls, snapshot: dict[str, Any]) -> Decimal | None:
        order_policy = dict(snapshot.get("order_policy") or {})
        value = cls._decimal_or_none(order_policy.get("quote_order_quantity"))
        if value is None or value <= 0:
            return None
        return value

    def _position_unrealized_pnl(
        self,
        *,
        instance: UserBotInstance,
        snapshot: dict[str, Any],
        ticker_cache: dict[str, Decimal | None],
    ) -> tuple[Decimal | None, str | None]:
        position = instance.position
        if position is None:
            return Decimal("0"), None

        quantity = self._decimal(position.quantity)
        if quantity <= 0:
            return Decimal("0"), None

        average_entry_price = self._decimal(position.average_entry_price)
        if average_entry_price <= 0:
            return None, "prix moyen d'entree indisponible pour la position ouverte."

        symbol = str(snapshot.get("symbol") or position.symbol)
        exchange = str(snapshot.get("exchange", "binance"))
        last_price = self._ticker_price(symbol, ticker_cache, exchange=exchange)
        if last_price is None or last_price <= 0:
            return None, f"prix marche indisponible pour {symbol}."
        return (last_price - average_entry_price) * quantity, None

    def _ticker_price(
        self, symbol: str, ticker_cache: dict[str, Decimal | None], *, exchange: str = "binance"
    ) -> Decimal | None:
        normalized_symbol = symbol.strip().upper()
        if normalized_symbol in ticker_cache:
            return ticker_cache[normalized_symbol]
        try:
            ticker = self.execution_gateway.ticker(normalized_symbol, exchange=exchange)
        except Exception:
            ticker_cache[normalized_symbol] = None
            return None
        price = (
            self._decimal_or_none(ticker.get("lastPrice"))
            or self._decimal_or_none(ticker.get("price"))
            or self._decimal_or_none(ticker.get("weightedAvgPrice"))
        )
        ticker_cache[normalized_symbol] = price
        return price

    @classmethod
    def _trade_realized_pnl(cls, trade: BotTrade) -> Decimal | None:
        raw_response = cls._mapping(trade.raw_response)
        if "realized_pnl" not in raw_response:
            return None
        return cls._decimal_or_none(raw_response.get("realized_pnl"))

    @classmethod
    def _build_pnl_curve(
        cls,
        *,
        trade_points: list[tuple[datetime, str, str, Decimal]],
        period_start: datetime | None,
        period_end: datetime,
        initial_capital: Decimal | None,
    ) -> list[PerformancePnlPointResponse]:
        sorted_points = sorted(trade_points, key=lambda item: item[0])
        if not sorted_points:
            return []

        cumulative = Decimal("0")
        rows: list[PerformancePnlPointResponse] = []
        start_timestamp = period_start or sorted_points[0][0]
        rows.append(
            PerformancePnlPointResponse(
                timestamp=cls._utc_datetime(start_timestamp),
                realized_pnl=Decimal("0"),
                cumulative_realized_pnl=Decimal("0"),
                capital_current=initial_capital,
            )
        )
        for timestamp, point_bot_id, bot_name, realized_pnl in sorted_points:
            cumulative += realized_pnl
            rows.append(
                PerformancePnlPointResponse(
                    timestamp=cls._utc_datetime(timestamp),
                    bot_id=point_bot_id,
                    bot_name=bot_name,
                    realized_pnl=realized_pnl,
                    cumulative_realized_pnl=cumulative,
                    capital_current=initial_capital + cumulative if initial_capital is not None else None,
                )
            )
        rows.append(
            PerformancePnlPointResponse(
                timestamp=cls._utc_datetime(period_end),
                realized_pnl=Decimal("0"),
                cumulative_realized_pnl=cumulative,
                capital_current=initial_capital + cumulative if initial_capital is not None else None,
            )
        )
        return rows

    @staticmethod
    def _mapping(value: Any) -> dict[str, Any]:
        return value if isinstance(value, dict) else {}

    @staticmethod
    def _db_datetime(value: datetime | None) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is not None:
            value = value.astimezone(UTC).replace(tzinfo=None)
        return value

    @staticmethod
    def _utc_datetime(value: datetime) -> datetime:
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value.astimezone(UTC)

    @staticmethod
    def _decimal_or_none(value: Any) -> Decimal | None:
        if value is None or value == "":
            return None
        if isinstance(value, Decimal):
            return value
        try:
            return Decimal(str(value))
        except (InvalidOperation, ValueError):
            return None

    @staticmethod
    def _float_or_none(value: Any) -> float | None:
        if value is None or value == "":
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    def _symbol_trade_status(self, symbol: str, *, exchange: str = "binance") -> dict[str, Any]:
        try:
            info = self.execution_gateway.symbol_info(symbol, exchange=exchange)
        except Exception:
            return {"tradeable": True, "reason": "symbol status check unavailable"}
        if str(info.get("status", "TRADING")).upper() != "TRADING":
            return {"tradeable": False, "reason": f"{symbol} status is {info.get('status')}"}
        if info.get("isSpotTradingAllowed") is False:
            return {"tradeable": False, "reason": f"{symbol} spot trading is not allowed"}
        return {"tradeable": True, "reason": "symbol is tradeable"}

    def _build_order_request(
        self,
        session: Session,
        instance: UserBotInstance,
        snapshot: dict[str, Any],
        action: str,
        now: datetime,
    ) -> BotOrderRequest:
        order_policy = dict(snapshot.get("order_policy") or {})
        order_type = str(order_policy.get("order_type", "MARKET")).upper()
        client_order_id = f"bot-{instance.id[:8]}-{int(now.timestamp())}"
        if action == "BUY":
            return BotOrderRequest(
                symbol=str(snapshot["symbol"]),
                side="BUY",
                order_type=order_type,
                quote_order_quantity=self._decimal(order_policy.get("quote_order_quantity")),
                client_order_id=client_order_id,
            )
        return BotOrderRequest(
            symbol=str(snapshot["symbol"]),
            side="SELL",
            order_type=order_type,
            quantity=self._sell_quantity(session, instance, snapshot),
            client_order_id=client_order_id,
        )

    def _record_decision(
        self,
        session: Session,
        instance: UserBotInstance,
        run: BotRun,
        *,
        timestamp: datetime,
        market_snapshot: dict[str, Any],
        model_output: dict[str, Any],
        strategy_signal: str,
        risk_decision: str,
        final_action: str,
        reason: str,
    ) -> TradingDecision:
        snapshot = instance.config_snapshot
        decision = TradingDecision(
            user_bot_instance_id=instance.id,
            run_id=run.id,
            user_id=instance.user_id,
            timestamp=timestamp,
            symbol=str(snapshot["symbol"]),
            timeframe=str(snapshot["timeframe"]),
            market_snapshot=market_snapshot,
            model_output=model_output,
            strategy_signal=strategy_signal,
            risk_decision=risk_decision,
            final_action=final_action,
            reason=reason,
        )
        session.add(decision)
        return decision

    def _record_order(
        self,
        session: Session,
        instance: UserBotInstance,
        snapshot: dict[str, Any],
        order_request: BotOrderRequest,
        response: dict[str, Any],
    ) -> BotOrder:
        order = BotOrder(
            user_id=instance.user_id,
            user_bot_instance_id=instance.id,
            exchange=str(snapshot.get("exchange", "binance")),
            environment=str(snapshot.get("environment", "testnet")),
            symbol=order_request.symbol,
            side=order_request.side,
            order_type=order_request.order_type,
            quantity=order_request.quantity,
            quote_order_quantity=order_request.quote_order_quantity,
            price=order_request.price,
            status=str(response.get("status") or "ACCEPTED"),
            binance_order_id=str(response.get("orderId")) if response.get("orderId") is not None else None,
            client_order_id=str(response.get("clientOrderId") or order_request.client_order_id),
            raw_response=response,
        )
        session.add(order)
        session.flush()
        return order

    def _record_trades_and_position(
        self,
        session: Session,
        instance: UserBotInstance,
        order: BotOrder,
        response: dict[str, Any],
    ) -> None:
        fills = self._normalised_fills(response)
        if not fills:
            return

        position = session.query(BotPosition).filter(BotPosition.user_bot_instance_id == instance.id).first()
        entry_price = self._decimal(position.average_entry_price if position else None)
        remaining_position_quantity = self._decimal(position.quantity if position else None)
        total_quantity = Decimal("0")
        total_quote = Decimal("0")
        now = datetime.now(UTC)
        for fill in fills:
            quantity = self._decimal(fill.get("qty"))
            price = self._decimal(fill.get("price"))
            if quantity <= 0 or price <= 0:
                continue
            clean_fill = dict(fill)
            if order.side == "SELL":
                closed_quantity = min(quantity, remaining_position_quantity)
                realized_pnl = Decimal("0")
                if closed_quantity > 0 and entry_price > 0:
                    realized_pnl = (price - entry_price) * closed_quantity
                    remaining_position_quantity = max(remaining_position_quantity - closed_quantity, Decimal("0"))
                clean_fill["realized_pnl"] = str(realized_pnl)
            total_quantity += quantity
            total_quote += quantity * price
            session.add(
                BotTrade(
                    user_id=instance.user_id,
                    order_id=order.id,
                    user_bot_instance_id=instance.id,
                    symbol=order.symbol,
                    side=order.side,
                    quantity=quantity,
                    price=price,
                    fee=self._decimal(fill.get("commission")),
                    fee_asset=fill.get("commissionAsset"),
                    trade_time=now,
                    raw_response=clean_fill,
                )
            )

        if total_quantity <= 0:
            return
        average_price = total_quote / total_quantity
        self._update_position(session, instance, order.symbol, order.side, total_quantity, average_price)

    def _update_position(
        self,
        session: Session,
        instance: UserBotInstance,
        symbol: str,
        side: str,
        quantity: Decimal,
        price: Decimal,
    ) -> None:
        position = session.query(BotPosition).filter(BotPosition.user_bot_instance_id == instance.id).first()
        if position is None:
            position = BotPosition(
                user_id=instance.user_id,
                user_bot_instance_id=instance.id,
                symbol=symbol,
                quantity=Decimal("0"),
                average_entry_price=None,
                unrealized_pnl=Decimal("0"),
                realized_pnl=Decimal("0"),
            )
            session.add(position)
            session.flush()

        current_quantity = self._decimal(position.quantity)
        current_average = self._decimal(position.average_entry_price)
        if side == "BUY":
            new_quantity = current_quantity + quantity
            total_cost = (current_quantity * current_average) + (quantity * price)
            position.quantity = new_quantity
            position.average_entry_price = total_cost / new_quantity if new_quantity > 0 else None
            return

        closed_quantity = min(quantity, current_quantity)
        if closed_quantity > 0 and current_average > 0:
            position.realized_pnl = self._decimal(position.realized_pnl) + ((price - current_average) * closed_quantity)
        remaining_quantity = max(current_quantity - quantity, Decimal("0"))
        position.quantity = remaining_quantity
        if remaining_quantity == 0:
            position.average_entry_price = None

    @staticmethod
    def _create_strategy(strategy_type: str, snapshot: dict[str, Any]):
        import strategy.engine.implementations  # noqa: F401
        from strategy.engine.registry import get_strategy

        params = dict(snapshot.get("execution_params") or {})
        risk_limits = dict(snapshot.get("risk_limits") or {})
        if "stop_loss_pct" in risk_limits:
            params["stop_loss"] = float(Decimal(str(risk_limits["stop_loss_pct"])) / Decimal("100"))
        if "take_profit_pct" in risk_limits:
            params["take_profit"] = float(Decimal(str(risk_limits["take_profit_pct"])) / Decimal("100"))
        return get_strategy(strategy_type, params)

    @staticmethod
    def _klines_to_frame(klines: list[dict[str, Any]]):
        """Construit le DataFrame OHLCV attendu par les strategies a partir des klines
        normalisees (utils.connectors.exchanges, cf. normalize_ohlcv) -- pas du format
        brut Binance (liste de listes) utilise par l'ex-Testnet lab."""
        import pandas as pd

        rows = []
        for item in klines:
            try:
                rows.append(
                    {
                        "open_time": int(item["open_time"].timestamp() * 1000),
                        "open": float(item["open"]),
                        "high": float(item["high"]),
                        "low": float(item["low"]),
                        "close": float(item["close"]),
                        "volume": float(item["volume"]),
                    }
                )
            except (KeyError, TypeError, ValueError):
                continue
        if not rows:
            raise RuntimeError("Market data source returned no usable kline rows")
        return pd.DataFrame(rows)

    @staticmethod
    def _normalised_fills(response: dict[str, Any]) -> list[dict[str, Any]]:
        fills = response.get("fills")
        if isinstance(fills, list) and fills:
            return [fill for fill in fills if isinstance(fill, dict)]

        executed_quantity = BotService._decimal(response.get("executedQty"))
        cumulative_quote = BotService._decimal(response.get("cummulativeQuoteQty"))
        if executed_quantity <= 0 or cumulative_quote <= 0:
            return []
        return [
            {
                "qty": str(executed_quantity),
                "price": str(cumulative_quote / executed_quantity),
                "commission": "0",
                "commissionAsset": None,
            }
        ]

    @staticmethod
    def _sell_quantity(session: Session, instance: UserBotInstance, snapshot: dict[str, Any]) -> Decimal:
        position = session.query(BotPosition).filter(BotPosition.user_bot_instance_id == instance.id).first()
        if position and BotService._decimal(position.quantity) > 0:
            return BotService._decimal(position.quantity)
        order_policy = dict(snapshot.get("order_policy") or {})
        configured_quantity = BotService._decimal(order_policy.get("quantity"))
        return configured_quantity

    @staticmethod
    def _split_symbol(symbol: str, quote_asset: str) -> tuple[str, str]:
        normalized_symbol = symbol.strip().upper()
        normalized_quote = quote_asset.strip().upper()
        if normalized_symbol.endswith(normalized_quote):
            return normalized_symbol[: -len(normalized_quote)], normalized_quote
        return normalized_symbol[:-4], normalized_symbol[-4:]

    @staticmethod
    def _free_balance(balances: list[dict[str, Any]], asset: str) -> Decimal:
        for balance in balances:
            if str(balance.get("asset", "")).upper() == asset.upper():
                return BotService._decimal(balance.get("free"))
        return Decimal("0")

    @staticmethod
    def _decimal(value: Any) -> Decimal:
        if value is None or value == "":
            return Decimal("0")
        if isinstance(value, Decimal):
            return value
        try:
            return Decimal(str(value))
        except (InvalidOperation, ValueError):
            return Decimal("0")

    @staticmethod
    def _elapsed_seconds(start: datetime, end: datetime) -> float:
        if start.tzinfo is None:
            start = start.replace(tzinfo=UTC)
        if end.tzinfo is None:
            end = end.replace(tzinfo=UTC)
        return max((end - start).total_seconds(), 0)

    @staticmethod
    def _clean_value(value: Any) -> Any:
        if hasattr(value, "item"):
            value = value.item()
        if isinstance(value, Decimal):
            return float(value)
        try:
            import pandas as pd

            if pd.isna(value):
                return None
        except Exception:
            pass
        if isinstance(value, datetime):
            # pandas.Timestamp est une sous-classe de datetime (n'a pas d'attribut .item(),
            # cf. ci-dessus) -- ni l'un ni l'autre n'est serialisable en JSON tel quel
            # (colonnes JSON, cf. bots/models.py). pd.NaT est aussi une instance de datetime
            # mais deja filtre par pd.isna() ci-dessus (value.timestamp() y leverait sinon).
            # Meme convention que _klines_to_frame() (epoch ms) pour rester coherent entre
            # les deux chemins de calcul du signal.
            return int(value.timestamp() * 1000)
        return value

    @staticmethod
    def _error_detail(exc: Exception) -> str:
        if isinstance(exc, HTTPException):
            return str(exc.detail)
        return str(exc)

    def _get_user_instance(self, session: Session, user_id: str, instance_id: str) -> UserBotInstance:
        instance = (
            session.query(UserBotInstance)
            .filter(UserBotInstance.id == instance_id, UserBotInstance.user_id == user_id)
            .first()
        )
        if instance is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User bot not found")
        return instance

    @staticmethod
    def _has_active_credentials(session: Session, user_id: str, exchange: str) -> bool:
        return BotService._active_credential_id(session, user_id, exchange) is not None

    @staticmethod
    def _active_credential_id(session: Session, user_id: str, exchange: str) -> str | None:
        """Identifiant de la credential active pour cet exchange (systeme multi-credential
        de l'utilisateur, cf. auth/models.py::UserSettings), ou None si aucune n'est configuree."""
        settings = session.query(UserSettings).filter(UserSettings.user_id == user_id).first()
        if not settings or not settings.has_credentials_for_exchange(exchange):
            return None
        for credential in settings.get_all_credentials():
            if credential.get("exchange") == exchange:
                return credential.get("id")
        return None

    @staticmethod
    def _snapshot_template(template: BotTemplate) -> dict[str, Any]:
        return {
            "template_id": template.id,
            "template_slug": template.slug,
            "template_version": template.version,
            "name": template.name,
            "model_type": template.model_type,
            "strategy_type": template.strategy_type,
            "symbol": template.symbol,
            "timeframe": template.timeframe,
            "signal_source": template.signal_source,
            "exchange": template.exchange,
            "environment": template.environment,
            "execution_params": dict(template.execution_params or {}),
            "risk_limits": dict(template.risk_limits or {}),
            "order_policy": dict(template.order_policy or {}),
        }

    def _ensure_running_run(
        self,
        session: Session,
        instance: UserBotInstance,
        *,
        worker_id: str | None = None,
    ) -> BotRun:
        run = (
            session.query(BotRun)
            .filter(
                BotRun.user_bot_instance_id == instance.id,
                BotRun.status == "RUNNING",
                BotRun.ended_at.is_(None),
            )
            .first()
        )
        if run is not None:
            if worker_id:
                run.worker_id = worker_id
            return run

        run = BotRun(
            user_bot_instance_id=instance.id,
            user_id=instance.user_id,
            started_at=datetime.now(UTC),
            status="RUNNING",
            worker_id=worker_id,
        )
        session.add(run)
        session.flush()
        return run

    @staticmethod
    def _instance_response(instance: UserBotInstance) -> UserBotResponse:
        template = BotTemplateResponse.model_validate(instance.template) if instance.template else None
        return UserBotResponse(
            id=instance.id,
            user_id=instance.user_id,
            bot_template_id=instance.bot_template_id,
            exchange_credential_id=instance.exchange_credential_id,
            mode=instance.mode,
            status=instance.status,
            auto_trade_enabled=instance.auto_trade_enabled,
            config_snapshot=dict(instance.config_snapshot or {}),
            last_decision_at=instance.last_decision_at,
            created_at=instance.created_at,
            updated_at=instance.updated_at,
            template=template,
        )


bot_service = BotService()
