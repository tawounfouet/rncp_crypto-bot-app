"""
Strategy router for handling strategy-related API endpoints.
"""

from typing import Any, Generic, TypeVar

from auth.dependencies import get_current_user
from auth.models import User
from fastapi import APIRouter, Depends, HTTPException, Query, status
from market.service import MarketDataService
from shared.core.exceptions import BusinessLogicError, NotFoundError, ValidationError
from shared.schemas.common import BaseResponse

from strategy.schemas import (
    BacktestCreate,
    BacktestResponse,
    MLBacktestCreate,
    MLBacktestResponse,
    ModelInfo,
    StrategyCreate,
    StrategyDeploymentCreate,
    StrategyDeploymentResponse,
    StrategyResponse,
    StrategyUpdate,
)
from strategy.service import StrategyService

# Generic data response model
T = TypeVar("T")


class DataResponse(BaseResponse, Generic[T]):
    """Generic response wrapper with data field."""

    data: T


# Create router
router = APIRouter(prefix="/strategies", tags=["strategies"])


# Initialize services (will be dependency injected)
def get_strategy_service() -> StrategyService:
    """Get strategy service instance."""
    market_data_service = MarketDataService()  # This would be dependency injected in real app
    return StrategyService(market_data_service)


@router.get("/available", response_model=dict[str, dict[str, Any]])
async def get_available_strategies(
    strategy_service: StrategyService = Depends(get_strategy_service),
):
    """
    Get all available strategy types and their information.

    Returns:
        Dictionary mapping strategy names to their metadata
    """
    try:
        strategies = strategy_service.get_available_strategies()
        return strategies
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get available strategies: {e!s}",
        ) from None


@router.get("/available-models", response_model=DataResponse[list[ModelInfo]])
def get_available_models(
    current_user: User = Depends(get_current_user),
    strategy_service: StrategyService = Depends(get_strategy_service),
):
    """
    Get all available-models for the current user.

    Args:
        current_user: Current authenticated user

    Returns:
        List of available models
    """
    try:
        models = strategy_service.get_available_models()

        return DataResponse(
            success=True,
            message=f"Retrieved {len(models)} deployments",
            data=models,
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Failed to get available models: {e!s}",
        ) from None


@router.get("/", response_model=DataResponse[list[StrategyResponse]])
async def get_user_strategies(
    include_public: bool = Query(True, description="Include public strategies"),
    current_user: User = Depends(get_current_user),
    strategy_service: StrategyService = Depends(get_strategy_service),
):
    """
    Get all strategies for the current user.

    Args:
        include_public: Whether to include public strategies
        current_user: Current authenticated user

    Returns:
        List of user strategies
    """
    try:
        strategies = await strategy_service.get_user_strategies(current_user.id, include_public)

        return DataResponse(
            success=True,
            message=f"Retrieved {len(strategies)} strategies",
            data=strategies,
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get strategies: {e!s}",
        ) from None


@router.post("/", response_model=DataResponse[StrategyResponse])
async def create_strategy(
    strategy_data: StrategyCreate,
    current_user: User = Depends(get_current_user),
    strategy_service: StrategyService = Depends(get_strategy_service),
):
    """
    Create a new trading strategy.

    Args:
        strategy_data: Strategy creation data
        current_user: Current authenticated user

    Returns:
        Created strategy
    """
    try:
        strategy = await strategy_service.create_strategy(current_user.id, strategy_data)

        # Convert SQLAlchemy model to Pydantic model and wrap in data response
        strategy_response = StrategyResponse.from_orm(strategy)
        return DataResponse(
            success=True,
            message="Strategy created successfully",
            data=strategy_response,
        )
    except ValidationError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from None
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create strategy: {e!s}",
        ) from None


# NOTE : cette route statique DOIT être déclarée avant la route paramétrée
# ``GET /{strategy_id}`` (ci-dessous), sinon Starlette la capture comme
# ``strategy_id="backtests"`` et renvoie 404 (cf. B4).
@router.get("/backtests", response_model=DataResponse[list[BacktestResponse]])
async def list_backtests(
    current_user: User = Depends(get_current_user),
    strategy_service: StrategyService = Depends(get_strategy_service),
):
    """List all backtest results for the current user."""
    try:
        results = strategy_service.get_user_backtests(current_user.id)
        return DataResponse(success=True, message=f"{len(results)} backtests", data=results)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list backtests: {e!s}",
        ) from None


@router.get("/{strategy_id}", response_model=DataResponse[StrategyResponse])
async def get_strategy(
    strategy_id: str,
    current_user: User = Depends(get_current_user),
    strategy_service: StrategyService = Depends(get_strategy_service),
):
    """
    Get a specific strategy by ID.

    Args:
        strategy_id: Strategy identifier
        current_user: Current authenticated user

    Returns:
        Strategy details
    """
    try:
        strategies = await strategy_service.get_user_strategies(current_user.id)
        strategy = next((s for s in strategies if s.id == strategy_id), None)

        if not strategy:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Strategy {strategy_id} not found",
            )

        return DataResponse(success=True, message="Strategy retrieved successfully", data=strategy)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get strategy: {e!s}",
        ) from None


@router.put("/{strategy_id}", response_model=DataResponse[StrategyResponse])
async def update_strategy(
    strategy_id: str,
    strategy_data: StrategyUpdate,
    current_user: User = Depends(get_current_user),
    strategy_service: StrategyService = Depends(get_strategy_service),
):
    """
    Update an existing strategy.

    Args:
        strategy_id: Strategy identifier
        strategy_data: Strategy update data
        current_user: Current authenticated user

    Returns:
        Updated strategy
    """
    try:
        strategy = await strategy_service.update_strategy(current_user.id, strategy_id, strategy_data)

        return DataResponse(success=True, message="Strategy updated successfully", data=strategy)
    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from None
    except (ValidationError, BusinessLogicError) as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from None
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update strategy: {e!s}",
        ) from None


@router.delete("/{strategy_id}", response_model=BaseResponse)
async def delete_strategy(
    strategy_id: str,
    current_user: User = Depends(get_current_user),
    strategy_service: StrategyService = Depends(get_strategy_service),
):
    """
    Delete a strategy.

    Args:
        strategy_id: Strategy identifier
        current_user: Current authenticated user

    Returns:
        Success response
    """
    try:
        # Check if strategy has active deployments
        deployments = await strategy_service.get_user_deployments(current_user.id, active_only=True)
        active_deployments = [d for d in deployments if d.strategy_id == strategy_id]

        if active_deployments:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot delete strategy with active deployments",
            )

        # For now, just mark as inactive (soft delete)
        # In a real implementation, you'd add a delete method to the service
        await strategy_service.update_strategy(current_user.id, strategy_id, StrategyUpdate(is_active=False))

        return BaseResponse(success=True, message="Strategy deleted successfully")
    except HTTPException:
        raise
    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from None
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete strategy: {e!s}",
        ) from None


@router.post("/{strategy_id}/deploy", response_model=DataResponse[StrategyDeploymentResponse])
async def deploy_strategy(
    strategy_id: str,
    deployment_data: StrategyDeploymentCreate,
    current_user: User = Depends(get_current_user),
    strategy_service: StrategyService = Depends(get_strategy_service),
):
    """
    Deploy a strategy for live trading.

    Args:
        strategy_id: Strategy identifier
        deployment_data: Deployment configuration
        current_user: Current authenticated user

    Returns:
        Created deployment
    """
    try:
        # Ensure strategy_id matches the one in the URL
        deployment_data.strategy_id = strategy_id

        deployment = await strategy_service.deploy_strategy(current_user.id, deployment_data)

        return DataResponse(success=True, message="Strategy deployed successfully", data=deployment)
    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from None
    except (ValidationError, BusinessLogicError) as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from None
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to deploy strategy: {e!s}",
        ) from None


@router.get("/deployments/", response_model=DataResponse[list[StrategyDeploymentResponse]])
async def get_user_deployments(
    active_only: bool = Query(False, description="Return only active deployments"),
    current_user: User = Depends(get_current_user),
    strategy_service: StrategyService = Depends(get_strategy_service),
):
    """
    Get all deployments for the current user.

    Args:
        active_only: Whether to return only active deployments
        current_user: Current authenticated user

    Returns:
        List of user deployments
    """
    try:
        deployments = await strategy_service.get_user_deployments(current_user.id, active_only)

        return DataResponse(
            success=True,
            message=f"Retrieved {len(deployments)} deployments",
            data=deployments,
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get deployments: {e!s}",
        ) from None


@router.post(
    "/deployments/{deployment_id}/stop",
    response_model=DataResponse[StrategyDeploymentResponse],
)
async def stop_deployment(
    deployment_id: str,
    reason: str | None = Query(None, description="Reason for stopping"),
    current_user: User = Depends(get_current_user),
    strategy_service: StrategyService = Depends(get_strategy_service),
):
    """
    Stop a strategy deployment.

    Args:
        deployment_id: Deployment identifier
        reason: Optional reason for stopping
        current_user: Current authenticated user

    Returns:
        Updated deployment
    """
    try:
        deployment = strategy_service.stop_deployment(current_user.id, deployment_id, reason)

        return DataResponse(success=True, message="Deployment stopped successfully", data=deployment)
    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from None
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to stop deployment: {e!s}",
        ) from None


@router.post("/backtests", response_model=DataResponse[BacktestResponse], status_code=201)
async def create_backtest(
    backtest_data: BacktestCreate,
    current_user: User = Depends(get_current_user),
    strategy_service: StrategyService = Depends(get_strategy_service),
):
    """Run a backtest for a strategy using stored OHLCV data (market_data table)."""
    try:
        result = await strategy_service.run_backtest(current_user.id, backtest_data)
        return DataResponse(success=True, message="Backtest terminé", data=result)
    except Exception as e:
        from shared.core.exceptions import BusinessLogicError, NotFoundError

        if isinstance(e, NotFoundError):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from None
        if isinstance(e, BusinessLogicError):
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e)) from None
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Backtest failed: {e!s}",
        ) from None


@router.post("/backtests/ml", response_model=DataResponse[MLBacktestResponse], status_code=201)
async def create_ml_backtest(
    backtest_data: MLBacktestCreate,
    current_user: User = Depends(get_current_user),
    strategy_service: StrategyService = Depends(get_strategy_service),
):
    """Run a backtest for a trained ML model (RF/XGBoost/MLP), completing missing
    historical data via Airflow first if needed."""
    try:
        result = await strategy_service.run_ml_backtest(current_user.id, backtest_data)
        return DataResponse(success=True, message="Backtest ML terminé", data=result)
    except Exception as e:
        if isinstance(e, NotFoundError):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from None
        if isinstance(e, BusinessLogicError):
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e)) from None
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"ML backtest failed: {e!s}",
        ) from None


@router.get("/backtests/{backtest_id}", response_model=DataResponse[BacktestResponse])
async def get_backtest(
    backtest_id: str,
    current_user: User = Depends(get_current_user),
    strategy_service: StrategyService = Depends(get_strategy_service),
):
    """Get a specific backtest result with full trade list."""
    try:
        result = strategy_service.get_backtest(current_user.id, backtest_id)
        return DataResponse(success=True, message="Backtest récupéré", data=result)
    except Exception as e:
        from shared.core.exceptions import NotFoundError

        if isinstance(e, NotFoundError):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from None
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get backtest: {e!s}",
        ) from None


@router.post("/deployments/execute-active", response_model=DataResponse[list[dict[str, Any]]])
async def execute_active_deployments(strategy_service: StrategyService = Depends(get_strategy_service)):
    """
    Declenche l'execution de tous les deployments actifs (tous utilisateurs).

    Plus appele automatiquement depuis le 2026-08-28 : le DAG Airflow qui le declenchait
    (orchestration/dags/bot_execution.py) a ete supprime, plus rien ne cree de
    StrategyDeployment depuis le remplacement de ce flux par le module bots/ (cf.
    docs/07-bot-strategy-architecture.md §4.7). Endpoint garde tel quel (module strategy/
    gele, pas supprime) -- pas d'authentification si jamais rappele manuellement, meme
    principe que POST /inference/predict-live.
    """
    try:
        results = await strategy_service.execute_active_deployments()
        return DataResponse(success=True, message=f"Executed {len(results)} deployments", data=results)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to execute active deployments: {e!s}",
        ) from None


@router.post("/validate", response_model=BaseResponse)
async def validate_strategy_parameters(
    strategy_type: str,
    parameters: dict[str, Any],
    strategy_service: StrategyService = Depends(get_strategy_service),
):
    """
    Validate strategy parameters.

    Args:
        strategy_type: Strategy type name
        parameters: Parameters to validate

    Returns:
        Validation result
    """
    try:
        is_valid, error_message = await strategy_service.validate_strategy_parameters(strategy_type, parameters)

        if is_valid:
            return BaseResponse(success=True, message="Parameters are valid")
        else:
            return BaseResponse(success=False, message=f"Parameter validation failed: {error_message}")
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to validate parameters: {e!s}",
        ) from None
