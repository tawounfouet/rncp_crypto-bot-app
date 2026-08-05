"""
Strategy service for managing strategy execution and lifecycle.
"""

import logging
import os
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

import pandas as pd
import requests
from inference.live_features import build_live_feature_frame
from inference.service import InferenceService
from market.service import MarketDataService
from shared.core.exceptions import BusinessLogicError, NotFoundError, ValidationError
from shared.database import get_db_session
from sqlalchemy import and_, or_
from trading.schemas import OrderCreate, OrderSideEnum, OrderTypeEnum
from trading.service import TradingService

from strategy.engine import get_strategy, registry
from strategy.models import Strategy, StrategyDeployment, StrategyState

# from models.order import Order
from strategy.schemas import (
    StrategyCreate,
    StrategyDeploymentCreate,
    StrategyDeploymentResponse,
    StrategyResponse,
    StrategyTypeEnum,
    StrategyUpdate,
)
from utils.trading.signals import VALUE_TO_SIGNAL

logger = logging.getLogger(__name__)


class StrategyService:
    """
    Service for managing trading strategies.

    Handles strategy creation, deployment, execution, and monitoring.
    """

    def __init__(self, market_data_service: MarketDataService):
        self.market_data_service = market_data_service

    async def create_strategy(self, user_id: str, strategy_data: StrategyCreate) -> Strategy:
        """
        Create a new trading strategy.

        Args:
            user_id: User identifier
            strategy_data: Strategy creation data

        Returns:
            Created strategy

        Raises:
            ValidationError: If strategy data is invalid
        """
        # Les strategy_type ML (ml_random_forest, futur ml_lstm) ne passent pas par le
        # registre de regles techniques (strategy/engine/) -- celui-ci n'est conserve que
        # pour un usage futur eventuel, plus expose comme choix produit (decision du
        # 2026-07-24 : seuls les modeles ML sont selectionnables par l'utilisateur).
        if not strategy_data.strategy_type.startswith("ml_"):
            if strategy_data.strategy_type not in registry.list_strategies():
                available_strategies = registry.list_strategies()
                raise ValidationError(
                    f"Unknown strategy type '{strategy_data.strategy_type}'. "
                    f"Available strategies: {', '.join(available_strategies)}"
                )

            is_valid, error_msg = registry.validate_strategy(strategy_data.strategy_type, strategy_data.parameters)
            if not is_valid:
                raise ValidationError(f"Invalid strategy parameters: {error_msg}")

        # Create strategy in database
        with get_db_session() as session:
            strategy = Strategy(
                user_id=user_id,
                name=strategy_data.name,
                description=strategy_data.description,
                strategy_type=strategy_data.strategy_type,
                parameters=strategy_data.parameters,
                asset_class=strategy_data.asset_class,
                is_public=strategy_data.is_public,
                version=strategy_data.version,
            )

            session.add(strategy)
            session.commit()
            session.refresh(strategy)

            # Detach the strategy from the session to avoid DetachedInstanceError
            session.expunge(strategy)

            logger.info(f"Created strategy {strategy.id} for user {user_id}")
            return strategy

    async def update_strategy(self, user_id: str, strategy_id: str, strategy_data: StrategyUpdate) -> Strategy:
        """
        Update an existing strategy.

        Args:
            user_id: User identifier
            strategy_id: Strategy identifier
            strategy_data: Update data

        Returns:
            Updated strategy

        Raises:
            NotFoundError: If strategy not found
            ValidationError: If update data is invalid
        """
        with get_db_session() as session:
            strategy = (
                session.query(Strategy).filter(and_(Strategy.id == strategy_id, Strategy.user_id == user_id)).first()
            )

            if not strategy:
                raise NotFoundError(f"Strategy {strategy_id} not found")

            # Check if strategy has active deployments
            active_deployments = (
                session.query(StrategyDeployment)
                .filter(
                    and_(
                        StrategyDeployment.strategy_id == strategy_id,
                        StrategyDeployment.status == "active",
                    )
                )
                .count()
            )

            if active_deployments > 0 and strategy_data.parameters is not None:
                raise BusinessLogicError("Cannot update parameters of strategy with active deployments")

            # Update fields
            update_data = strategy_data.dict(exclude_unset=True)
            for field, value in update_data.items():
                setattr(strategy, field, value)

            # Validate parameters if updated (types ML : cf. remarque dans create_strategy)
            if strategy_data.parameters is not None and not strategy.strategy_type.startswith("ml_"):
                is_valid, error_msg = registry.validate_strategy(strategy.strategy_type, strategy_data.parameters)
                if not is_valid:
                    raise ValidationError(f"Invalid strategy parameters: {error_msg}")

            strategy.updated_at = datetime.now(UTC)
            session.commit()
            session.refresh(strategy)

            # Detach the strategy from the session
            session.expunge(strategy)

            logger.info(f"Updated strategy {strategy_id}")
            return strategy

    async def deploy_strategy(
        self, user_id: str, deployment_data: StrategyDeploymentCreate
    ) -> StrategyDeploymentResponse:
        """
        Deploy a strategy for live trading.

        Args:
            user_id: User identifier
            deployment_data: Deployment configuration

        Returns:
            Created deployment response

        Raises:
            NotFoundError: If strategy not found
            ValidationError: If deployment data is invalid
        """
        with get_db_session() as session:
            # Verify strategy exists and belongs to user
            strategy = (
                session.query(Strategy)
                .filter(
                    and_(
                        Strategy.id == deployment_data.strategy_id,
                        Strategy.user_id == user_id,
                        Strategy.is_active.is_(True),
                    )
                )
                .first()
            )

            if not strategy:
                raise NotFoundError(f"Strategy {deployment_data.strategy_id} not found or inactive")

            # Check for existing active deployment on same symbol
            existing_deployment = (
                session.query(StrategyDeployment)
                .filter(
                    and_(
                        StrategyDeployment.user_id == user_id,
                        StrategyDeployment.exchange == deployment_data.exchange,
                        StrategyDeployment.symbol == deployment_data.symbol,
                        StrategyDeployment.status == "active",
                    )
                )
                .first()
            )

            if existing_deployment:
                raise BusinessLogicError(
                    f"Active deployment already exists for {deployment_data.symbol} on {deployment_data.exchange}"
                )

            # Create deployment
            deployment = StrategyDeployment(
                strategy_id=deployment_data.strategy_id,
                user_id=user_id,
                exchange=deployment_data.exchange,
                symbol=deployment_data.symbol,
                timeframe=deployment_data.timeframe,
                amount=deployment_data.amount,
                parameters=deployment_data.parameters,
                is_paper=deployment_data.is_paper,
                start_time=datetime.now(UTC),
            )

            session.add(deployment)
            session.commit()
            session.refresh(deployment)

            # Create initial strategy state
            state = StrategyState(
                deployment_id=deployment.id,
                user_id=user_id,
                position="NEUTRAL",
                position_size=Decimal("0"),
                is_active=True,
            )

            session.add(state)
            session.commit()

            # Convert to StrategyDeploymentResponse while still in session
            deployment_response = StrategyDeploymentResponse(
                id=deployment.id,
                strategy_id=deployment.strategy_id,
                user_id=deployment.user_id,
                exchange=deployment.exchange,
                symbol=deployment.symbol,
                timeframe=deployment.timeframe,
                amount=deployment.amount,
                parameters=deployment.parameters,
                is_paper=deployment.is_paper,
                status=deployment.status,
                start_time=deployment.start_time,
                end_time=deployment.end_time,
                created_at=deployment.created_at,
                updated_at=deployment.updated_at,
            )

            logger.info(f"Deployed strategy {deployment_data.strategy_id} as deployment {deployment.id}")
            return deployment_response

    async def execute_strategy(self, deployment_id: str, data: pd.DataFrame | None = None) -> dict[str, Any]:
        """
        Execute a strategy on market data.

        Args:
            deployment_id: Deployment identifier
            data: Market data DataFrame, requis uniquement pour le moteur de règles fixes
                (la branche ML_RANDOM_FOREST va chercher ses propres données live)

        Returns:
            Execution results with signals and metadata

        Raises:
            NotFoundError: If deployment not found
            BusinessLogicError: If execution fails
        """
        with get_db_session() as session:
            # Get deployment and strategy
            deployment = session.query(StrategyDeployment).filter(StrategyDeployment.id == deployment_id).first()

            if not deployment:
                raise NotFoundError(f"Deployment {deployment_id} not found")

            if deployment.status != "active":
                raise BusinessLogicError(f"Deployment {deployment_id} is not active")

            strategy_model = deployment.strategy

            try:
                if strategy_model.strategy_type == StrategyTypeEnum.ML_RANDOM_FOREST:
                    df = build_live_feature_frame(deployment.symbol, deployment.timeframe)
                    latest_row = df.iloc[-1]
                    svc = InferenceService()
                    features = {col: latest_row[col] for col in svc.feature_columns}
                    result = svc.predict(features)
                    latest_signal = result["signal_value"]
                    signal_info = {
                        "timestamp": (latest_row.name if hasattr(latest_row, "name") else None),
                        "price": float(latest_row.get("close", 0)),
                        "confidence": result["confidence"],
                        "probabilities": result["probabilities"],
                    }
                    data_points = len(df)
                else:
                    # Create strategy instance
                    strategy_params = {**strategy_model.parameters}
                    if deployment.parameters:
                        strategy_params.update(deployment.parameters)

                    strategy = get_strategy(strategy_model.strategy_type, strategy_params)

                    # Execute strategy
                    results = strategy.run(data)
                    data_points = len(results)

                    # Get the latest signal
                    latest_signal = 0
                    signal_info = {}

                    if not results.empty and "signal" in results.columns:
                        # Get the last non-zero signal
                        non_zero_signals = results[results["signal"] != 0]
                        if not non_zero_signals.empty:
                            latest_row = non_zero_signals.iloc[-1]
                            latest_signal = latest_row["signal"]
                            signal_info = {
                                "timestamp": (latest_row.name if hasattr(latest_row, "name") else None),
                                "price": float(latest_row.get("close", 0)),
                                "indicators": {
                                    col: float(latest_row[col])
                                    for col in latest_row.index
                                    if col
                                    not in [
                                        "signal",
                                        "open",
                                        "high",
                                        "low",
                                        "close",
                                        "volume",
                                    ]
                                    and pd.notna(latest_row[col])
                                },
                            }

                # Update strategy state
                state = deployment.state
                if state:
                    state.last_signal_time = datetime.now(UTC)
                    state.last_signal = VALUE_TO_SIGNAL.get(latest_signal, "HOLD")
                    session.commit()

                execution_result = {
                    "deployment_id": deployment_id,
                    "strategy_type": strategy_model.strategy_type,
                    "latest_signal": latest_signal,
                    "signal_info": signal_info,
                    "data_points": data_points,
                    "execution_time": datetime.now(UTC).isoformat(),
                }

                logger.info(f"Executed strategy {strategy_model.strategy_type} for deployment {deployment_id}")
                return execution_result

            except Exception as e:
                logger.error(f"Strategy execution failed for deployment {deployment_id}: {e!s}")

                # Update deployment status to error
                deployment.status = "error"
                if deployment.state:
                    deployment.state.is_active = False
                    deployment.state.stop_reason = f"Execution error: {e!s}"

                session.commit()
                raise BusinessLogicError(f"Strategy execution failed: {e!s}") from None

    async def execute_active_deployments(self) -> list[dict[str, Any]]:
        response = list()
        with get_db_session() as session:
            deployments = session.query(StrategyDeployment).filter(StrategyDeployment.status == "active").all()
            for deployment in deployments:
                state = deployment.state
                if state and state.last_signal_time:
                    cooldown = deployment.strategy.parameters.get("cooldown_seconds", 300)
                    last_signal_time = state.last_signal_time
                    if last_signal_time.tzinfo is None:
                        # SQLite (tests, dev) stocke la colonne DateTime sans tzinfo : on
                        # sait qu'elle est toujours ecrite en UTC (cf. plus haut, ligne 347).
                        last_signal_time = last_signal_time.replace(tzinfo=UTC)
                    if timedelta(seconds=cooldown) > (datetime.now(UTC) - last_signal_time):
                        response.append(
                            {
                                "deployment_id": deployment.id,
                                "action": "skipped_cooldown",
                            }
                        )
                        continue
                if state and state.position not in (None, "NEUTRAL"):
                    response.append(
                        {
                            "deployment_id": deployment.id,
                            "action": "skipped_open_position",
                        }
                    )
                    continue
                result = await self.execute_strategy(deployment.id)

                if result and "latest_signal" in result and result["latest_signal"] != 0:
                    price = Decimal(str(result["signal_info"]["price"]))
                    quantity = deployment.amount / price
                    side = OrderSideEnum.BUY if result["latest_signal"] == 1 else OrderSideEnum.SELL
                    order_data = OrderCreate(
                        deployment_id=deployment.id,
                        symbol=deployment.symbol,
                        order_type=OrderTypeEnum.MARKET,
                        side=side,
                        quantity=quantity,
                    )
                    trading_service = TradingService(session)
                    await trading_service.create_order(deployment.user_id, order_data)
                    response.append(
                        {
                            "deployment_id": deployment.id,
                            "action": "order_submitted",
                        }
                    )
                else:
                    response.append(
                        {
                            "deployment_id": deployment.id,
                            "action": "hold",
                        }
                    )
        return response

    def stop_deployment(self, user_id: str, deployment_id: str, reason: str = None) -> StrategyDeploymentResponse:
        """
        Stop a strategy deployment.

        Args:
            user_id: User identifier
            deployment_id: Deployment identifier
            reason: Optional stop reason

        Returns:
            Updated deployment response

        Raises:
            NotFoundError: If deployment not found
        """
        with get_db_session() as session:
            deployment = (
                session.query(StrategyDeployment)
                .filter(
                    and_(
                        StrategyDeployment.id == deployment_id,
                        StrategyDeployment.user_id == user_id,
                    )
                )
                .first()
            )

            if not deployment:
                raise NotFoundError(f"Deployment {deployment_id} not found")

            deployment.stop(reason)
            session.commit()
            session.refresh(deployment)

            # Convert to StrategyDeploymentResponse while still in session
            deployment_response = StrategyDeploymentResponse(
                id=deployment.id,
                user_id=deployment.user_id,
                strategy_id=deployment.strategy_id,
                exchange=deployment.exchange,
                symbol=deployment.symbol,
                timeframe=deployment.timeframe,
                amount=deployment.amount,
                parameters=deployment.parameters,
                is_paper=deployment.is_paper,
                status=deployment.status,
                start_time=deployment.start_time,
                end_time=deployment.end_time,
                created_at=deployment.created_at,
                updated_at=deployment.updated_at,
            )

            logger.info(f"Stopped deployment {deployment_id}")
            return deployment_response

    async def get_user_strategies(self, user_id: str, include_public: bool = True) -> list[StrategyResponse]:
        """
        Get all strategies for a user.

        Args:
            user_id: User identifier
            include_public: Whether to include public strategies

        Returns:
            List of strategy responses
        """
        with get_db_session() as session:
            query = session.query(Strategy)

            query = query.filter(Strategy.is_active.is_(True))
            if include_public:
                query = query.filter(or_(Strategy.user_id == user_id, Strategy.is_public.is_(True)))
            else:
                query = query.filter(Strategy.user_id == user_id)

            strategies = query.order_by(Strategy.created_at.desc()).all()

            # Convert to StrategyResponse objects while still in session
            strategy_responses = []
            for strategy in strategies:
                # Create StrategyResponse object with all required fields
                strategy_response = StrategyResponse(
                    id=strategy.id,
                    user_id=strategy.user_id,
                    name=strategy.name,
                    description=strategy.description,
                    strategy_type=strategy.strategy_type,
                    asset_class=strategy.asset_class,
                    version=strategy.version,
                    parameters=strategy.parameters,
                    parameter_hash=strategy.parameter_hash,
                    is_active=strategy.is_active,
                    is_public=strategy.is_public,
                    created_at=strategy.created_at,
                    updated_at=strategy.updated_at,
                )
                strategy_responses.append(strategy_response)

            return strategy_responses

    async def get_user_deployments(self, user_id: str, active_only: bool = False) -> list[StrategyDeploymentResponse]:
        """
        Get all deployments for a user.

        Args:
            user_id: User identifier
            active_only: Whether to return only active deployments

        Returns:
            List of deployment responses
        """
        with get_db_session() as session:
            query = session.query(StrategyDeployment).filter(StrategyDeployment.user_id == user_id)

            if active_only:
                query = query.filter(StrategyDeployment.status == "active")

            deployments = query.order_by(StrategyDeployment.created_at.desc()).all()

            # Convert to StrategyDeploymentResponse objects while still in session
            deployment_responses = []
            for deployment in deployments:
                deployment_response = StrategyDeploymentResponse(
                    id=deployment.id,
                    user_id=deployment.user_id,
                    strategy_id=deployment.strategy_id,
                    exchange=deployment.exchange,
                    symbol=deployment.symbol,
                    timeframe=deployment.timeframe,
                    amount=deployment.amount,
                    parameters=deployment.parameters,
                    is_paper=deployment.is_paper,
                    status=deployment.status,
                    start_time=deployment.start_time,
                    end_time=deployment.end_time,
                    created_at=deployment.created_at,
                    updated_at=deployment.updated_at,
                )
                deployment_responses.append(deployment_response)

            return deployment_responses

    def get_available_strategies(self) -> dict[str, dict[str, Any]]:
        """
        Get information about all available strategies.

        Returns:
            Dictionary mapping strategy names to their information
        """
        return registry.get_all_strategies_info()

    async def validate_strategy_parameters(
        self, strategy_type: str, parameters: dict[str, Any]
    ) -> tuple[bool, str | None]:
        """
        Validate strategy parameters.

        Args:
            strategy_type: Strategy type name
            parameters: Parameters to validate

        Returns:
            Tuple of (is_valid, error_message)
        """
        return registry.validate_strategy(strategy_type, parameters)

    # ---------------------------------------------------------------------------
    # Backtesting
    # ---------------------------------------------------------------------------

    def _load_ohlcv(self, session, symbol: str, timeframe: str, start_date, end_date) -> pd.DataFrame:
        """Load OHLCV rows from market_data table."""
        from market.models import MarketData

        rows = (
            session.query(MarketData)
            .filter(
                and_(
                    MarketData.symbol == symbol,
                    MarketData.interval_timeframe == timeframe,
                    MarketData.open_time >= start_date,
                    MarketData.open_time <= end_date,
                )
            )
            .order_by(MarketData.open_time.asc())
            .all()
        )
        if not rows:
            return pd.DataFrame()
        data = [
            {
                "timestamp": r.open_time,
                "open": float(r.open_price),
                "high": float(r.high_price),
                "low": float(r.low_price),
                "close": float(r.close_price),
                "volume": float(r.volume),
            }
            for r in rows
        ]
        df = pd.DataFrame(data)
        df.set_index("timestamp", inplace=True)
        return df

    def _simulate_strategy(
        self,
        df: pd.DataFrame,
        strategy_type: str,
        params: dict,
        initial_balance: float,
    ) -> tuple[list[dict], dict]:
        """
        Run a simplified strategy simulation over OHLCV data.

        Returns (trades_list, metrics_dict).
        """
        if df.empty or len(df) < 2:
            return [], {
                "total_return": 0.0,
                "max_drawdown": 0.0,
                "sharpe_ratio": 0.0,
                "win_rate": 0.0,
                "total_trades": 0,
                "profit_factor": 0.0,
            }

        close = df["close"]
        n = len(close)

        # --- Generate signal series ---
        signals = pd.Series(0, index=df.index)

        st = strategy_type.lower()

        if "mean_reversion" in st or "rsi" in st or "bollinger" in st:
            # RSI-based mean reversion
            period = int(params.get("rsi_period", params.get("period", 14)))
            period = min(period, n - 1) or 14
            delta = close.diff()
            gain = delta.clip(lower=0).rolling(period).mean()
            loss = (-delta.clip(upper=0)).rolling(period).mean()
            rs = gain / loss.replace(0, 1e-9)
            rsi = 100 - (100 / (1 + rs))
            oversold = float(params.get("oversold", 30))
            overbought = float(params.get("overbought", 70))
            signals[rsi < oversold] = 1  # BUY
            signals[rsi > overbought] = -1  # SELL

        elif "momentum" in st or "trend" in st or "moving_average" in st or "crossover" in st:
            # MA crossover
            fast = int(params.get("fast_period", params.get("fast_ma", 10)))
            slow = int(params.get("slow_period", params.get("slow_ma", 20)))
            fast = min(fast, n // 2) or 5
            slow = min(slow, n - 1) or 20
            ma_fast = close.rolling(fast).mean()
            ma_slow = close.rolling(slow).mean()
            signals[ma_fast > ma_slow] = 1
            signals[ma_fast <= ma_slow] = -1

        elif "grid" in st:
            # Simple grid: buy at every 2% dip from reference, sell at +2%
            grid_pct = float(params.get("grid_pct", 0.02))
            ref = close.iloc[0]
            for ts, price in close.items():
                if price <= ref * (1 - grid_pct):
                    signals[ts] = 1
                    ref = price
                elif price >= ref * (1 + grid_pct):
                    signals[ts] = -1
                    ref = price

        else:
            # Default: random MA crossover (5/20)
            ma_fast = close.rolling(5).mean()
            ma_slow = close.rolling(20).mean()
            signals[ma_fast > ma_slow] = 1
            signals[ma_fast <= ma_slow] = -1

        # --- Simulate trades ---
        commission = float(params.get("commission", 0.001))
        stop_loss_pct = float(params.get("stop_loss", params.get("stop_loss_pct", 0.02)))
        take_profit_pct = float(params.get("take_profit", params.get("take_profit_pct", 0.04)))

        balance = initial_balance
        position = 0.0  # units held
        entry_price = 0.0
        trades = []
        equity_curve = [balance]

        prev_signal = 0
        for ts, price in close.items():
            sig = signals[ts]

            # Check stop-loss / take-profit if in position
            if position > 0:
                pnl_pct = (price - entry_price) / entry_price
                if pnl_pct <= -stop_loss_pct or pnl_pct >= take_profit_pct:
                    # Force exit
                    proceeds = position * price * (1 - commission)
                    pnl = proceeds - (position * entry_price * (1 + commission))
                    balance += proceeds
                    trades.append(
                        {
                            "entry_price": entry_price,
                            "exit_price": price,
                            "pnl": round(pnl, 4),
                            "pnl_pct": round(pnl_pct * 100, 2),
                            "exit_reason": "stop_loss" if pnl_pct <= -stop_loss_pct else "take_profit",
                            "timestamp": str(ts),
                        }
                    )
                    position = 0.0
                    entry_price = 0.0
                    equity_curve.append(balance)
                    continue

            if sig == 1 and prev_signal != 1 and position == 0 and balance > 0:
                # BUY
                units = (balance * 0.95) / (price * (1 + commission))
                cost = units * price * (1 + commission)
                if cost <= balance:
                    position = units
                    entry_price = price
                    balance -= cost

            elif sig == -1 and position > 0:
                # SELL
                proceeds = position * price * (1 - commission)
                pnl_pct = (price - entry_price) / entry_price
                pnl = proceeds - (position * entry_price * (1 + commission))
                balance += proceeds
                trades.append(
                    {
                        "entry_price": entry_price,
                        "exit_price": price,
                        "pnl": round(pnl, 4),
                        "pnl_pct": round(pnl_pct * 100, 2),
                        "exit_reason": "signal",
                        "timestamp": str(ts),
                    }
                )
                position = 0.0
                entry_price = 0.0

            equity_curve.append(balance + position * price)
            prev_signal = sig

        # Close open position at last price
        if position > 0:
            last_price = float(close.iloc[-1])
            proceeds = position * last_price * (1 - commission)
            pnl_pct = (last_price - entry_price) / entry_price
            pnl = proceeds - (position * entry_price * (1 + commission))
            balance += proceeds
            trades.append(
                {
                    "entry_price": entry_price,
                    "exit_price": last_price,
                    "pnl": round(pnl, 4),
                    "pnl_pct": round(pnl_pct * 100, 2),
                    "exit_reason": "end_of_data",
                    "timestamp": str(close.index[-1]),
                }
            )

        final_balance = balance
        total_return = (final_balance - initial_balance) / initial_balance * 100

        # Max drawdown
        eq = pd.Series(equity_curve)
        running_max = eq.cummax()
        drawdowns = (eq - running_max) / running_max.replace(0, 1e-9)
        max_drawdown = float(drawdowns.min() * 100)

        # Sharpe (simplified, daily returns)
        returns = eq.pct_change().dropna()
        sharpe = float(returns.mean() / returns.std() * (252**0.5)) if returns.std() > 0 else 0.0

        # Win rate
        winning = [t for t in trades if t["pnl"] > 0]
        win_rate = len(winning) / len(trades) * 100 if trades else 0.0

        # Profit factor
        gross_profit = sum(t["pnl"] for t in winning)
        gross_loss = abs(sum(t["pnl"] for t in trades if t["pnl"] < 0))
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else float("inf")

        metrics = {
            "total_return": round(total_return, 2),
            "final_balance": round(final_balance, 2),
            "max_drawdown": round(max_drawdown, 2),
            "sharpe_ratio": round(sharpe, 3),
            "win_rate": round(win_rate, 2),
            "total_trades": len(trades),
            "winning_trades": len(winning),
            "profit_factor": round(min(profit_factor, 999.0), 2),
        }
        return trades, metrics

    async def run_backtest(
        self,
        user_id: str,
        backtest_data,
    ):
        """
        Run a backtest for a strategy using stored OHLCV data.
        Returns a BacktestResult object (committed to DB).
        """
        import uuid

        from strategy.models import BacktestResult

        with get_db_session() as session:
            strategy = (
                session.query(Strategy)
                .filter(
                    and_(
                        Strategy.id == backtest_data.strategy_id,
                        Strategy.user_id == user_id,
                    )
                )
                .first()
            )
            if not strategy:
                raise NotFoundError(f"Strategy {backtest_data.strategy_id} not found")

            df = self._load_ohlcv(
                session,
                symbol=backtest_data.symbol,
                timeframe=backtest_data.timeframe,
                start_date=backtest_data.start_date,
                end_date=backtest_data.end_date,
            )
            if df.empty:
                raise BusinessLogicError(
                    f"Aucune donnée OHLCV pour {backtest_data.symbol}/{backtest_data.timeframe} "
                    f"entre {backtest_data.start_date} et {backtest_data.end_date}. "
                    "Vérifiez que le DAG Airflow a ingéré des données pour cette paire."
                )

            params = {**(strategy.parameters or {})}
            if backtest_data.parameters:
                params.update(backtest_data.parameters)

            trades, metrics = self._simulate_strategy(
                df,
                strategy_type=strategy.strategy_type,
                params=params,
                initial_balance=float(backtest_data.initial_balance),
            )

            bt = BacktestResult(
                id=str(uuid.uuid4()),
                strategy_id=backtest_data.strategy_id,
                user_id=user_id,
                symbol=backtest_data.symbol,
                timeframe=backtest_data.timeframe,
                start_date=backtest_data.start_date,
                end_date=backtest_data.end_date,
                parameters=params,
                results={"equity_final": metrics.get("final_balance")},
                metrics=metrics,
                transactions=trades,
            )
            session.add(bt)
            session.commit()
            session.refresh(bt)

            logger.info(
                "Backtest user=%s strategy=%s symbol=%s: %d trades, return=%.2f%%",
                user_id,
                backtest_data.strategy_id,
                backtest_data.symbol,
                len(trades),
                metrics.get("total_return", 0),
            )

            from strategy.schemas import BacktestResponse

            return BacktestResponse(
                id=bt.id,
                strategy_id=bt.strategy_id,
                user_id=bt.user_id,
                symbol=bt.symbol,
                timeframe=bt.timeframe,
                start_date=bt.start_date,
                end_date=bt.end_date,
                parameters=bt.parameters,
                metrics=bt.metrics,
                transactions=bt.transactions,
                created_at=bt.created_at,
                updated_at=bt.updated_at,
            )

    def get_user_backtests(self, user_id: str) -> list:
        """List all backtest results for a user (no transactions to keep payload small)."""
        from strategy.models import BacktestResult
        from strategy.schemas import BacktestResponse

        with get_db_session() as session:
            rows = (
                session.query(BacktestResult)
                .filter(BacktestResult.user_id == user_id)
                .order_by(BacktestResult.created_at.desc())
                .all()
            )
            return [
                BacktestResponse(
                    id=r.id,
                    strategy_id=r.strategy_id,
                    user_id=r.user_id,
                    symbol=r.symbol,
                    timeframe=r.timeframe,
                    start_date=r.start_date,
                    end_date=r.end_date,
                    parameters=r.parameters,
                    metrics=r.metrics,
                    transactions=None,
                    created_at=r.created_at,
                    updated_at=r.updated_at,
                )
                for r in rows
            ]

    def get_backtest(self, user_id: str, backtest_id: str):
        """Get a specific backtest result with full transactions."""
        from strategy.models import BacktestResult
        from strategy.schemas import BacktestResponse

        with get_db_session() as session:
            r = (
                session.query(BacktestResult)
                .filter(
                    and_(
                        BacktestResult.id == backtest_id,
                        BacktestResult.user_id == user_id,
                    )
                )
                .first()
            )
            if not r:
                raise NotFoundError(f"Backtest {backtest_id} not found")
            return BacktestResponse(
                id=r.id,
                strategy_id=r.strategy_id,
                user_id=r.user_id,
                symbol=r.symbol,
                timeframe=r.timeframe,
                start_date=r.start_date,
                end_date=r.end_date,
                parameters=r.parameters,
                metrics=r.metrics,
                transactions=r.transactions,
                created_at=r.created_at,
                updated_at=r.updated_at,
            )

    def get_available_models(self) -> list[dict[str, Any]]:
        ML_API_URL = os.environ.get("ML_API_URL", "http://crypto-bot-ml-api:8010")

        response = requests.get(
            f"{ML_API_URL}/models",
            timeout=30,
        )
        response.raise_for_status()
        logger.info("get_available_models: %s", response.json())
        return response.json()["models"]
