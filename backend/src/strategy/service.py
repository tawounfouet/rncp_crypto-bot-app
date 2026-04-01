"""
Strategy service for managing strategy execution and lifecycle.
"""

import logging
from datetime import datetime
from decimal import Decimal
from typing import Any

import pandas as pd
from market.service import MarketDataService
from shared.core.exceptions import BusinessLogicError, NotFoundError, ValidationError
from shared.database import get_db_session
from sqlalchemy import and_, or_

from strategy.engine import get_strategy, registry
from strategy.models import Strategy, StrategyDeployment, StrategyState

# from models.order import Order
from strategy.schemas import (
    StrategyCreate,
    StrategyDeploymentCreate,
    StrategyDeploymentResponse,
    StrategyResponse,
    StrategyUpdate,
)

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
        # Validate strategy type exists in registry
        if strategy_data.strategy_type not in registry.list_strategies():
            available_strategies = registry.list_strategies()
            raise ValidationError(
                f"Unknown strategy type '{strategy_data.strategy_type}'. "
                f"Available strategies: {', '.join(available_strategies)}"
            )

        # Validate strategy parameters
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

            # Validate parameters if updated
            if strategy_data.parameters is not None:
                is_valid, error_msg = registry.validate_strategy(strategy.strategy_type, strategy_data.parameters)
                if not is_valid:
                    raise ValidationError(f"Invalid strategy parameters: {error_msg}")

            strategy.updated_at = datetime.utcnow()
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
                start_time=datetime.utcnow(),
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
                status=deployment.status,
                start_time=deployment.start_time,
                end_time=deployment.end_time,
                created_at=deployment.created_at,
                updated_at=deployment.updated_at,
            )

            logger.info(f"Deployed strategy {deployment_data.strategy_id} as deployment {deployment.id}")
            return deployment_response

    async def execute_strategy(self, deployment_id: str, data: pd.DataFrame) -> dict[str, Any]:
        """
        Execute a strategy on market data.

        Args:
            deployment_id: Deployment identifier
            data: Market data DataFrame

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
                # Create strategy instance
                strategy_params = {**strategy_model.parameters}
                if deployment.parameters:
                    strategy_params.update(deployment.parameters)

                strategy = get_strategy(strategy_model.strategy_type, strategy_params)

                # Execute strategy
                results = strategy.run(data)

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
                    state.last_execution = datetime.utcnow()
                    state.last_signal = latest_signal
                    session.commit()

                execution_result = {
                    "deployment_id": deployment_id,
                    "strategy_type": strategy_model.strategy_type,
                    "latest_signal": latest_signal,
                    "signal_info": signal_info,
                    "data_points": len(results),
                    "execution_time": datetime.utcnow().isoformat(),
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
