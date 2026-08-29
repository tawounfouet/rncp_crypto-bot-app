"""Routes for bot templates and user bot instances."""

from __future__ import annotations

from auth.dependencies import get_current_user
from auth.models import User
from fastapi import APIRouter, Depends, Query

from bots.schemas import (
    BotActionResponse,
    BotOrderResponse,
    BotPerformanceResponse,
    BotPositionResponse,
    BotTemplateResponse,
    BotTradeResponse,
    TradingDecisionResponse,
    UserBotCreate,
    UserBotResponse,
    UserPerformanceSummaryResponse,
)
from bots.service import BotService, bot_service

router = APIRouter(tags=["Bots"])

# Route interne, non authentifiee, mirroir de /internal/pipeline/* cote ml-api :
# appelee uniquement depuis le reseau docker (Airflow, cf. orchestration/dags/ml_pipeline.py),
# jamais montee sous API_PREFIX ni exposee publiquement.
internal_router = APIRouter(tags=["Bots (internal)"])


def get_bot_service() -> BotService:
    return bot_service


@internal_router.post("/internal/bot-templates/sync")
async def sync_bot_templates(
    service: BotService = Depends(get_bot_service),
) -> dict:
    """Resynchronise les templates ML (BotService.sync_builtin_templates()).

    Appelee par le DAG Airflow ``cryptobot_ml_pipeline`` juste apres le
    deploiement des modeles, pour que le catalogue reflete les modeles
    fraichement entraines sans attendre un redemarrage du backend (cf.
    lifespan() dans main.py, qui ne resynchronise qu'au demarrage).
    """
    return service.sync_builtin_templates(migrate_instances=False)


@router.get("/bot-templates", response_model=list[BotTemplateResponse])
async def list_bot_templates(
    include_disabled: bool = Query(False, description="Include disabled templates"),
    service: BotService = Depends(get_bot_service),
) -> list[BotTemplateResponse]:
    """List preconfigured bots available to users."""
    return service.list_templates(include_disabled=include_disabled)


@router.get("/bot-templates/{template_id}", response_model=BotTemplateResponse)
async def get_bot_template(
    template_id: str,
    service: BotService = Depends(get_bot_service),
) -> BotTemplateResponse:
    """Get a preconfigured bot template."""
    return service.get_template(template_id)


@router.post("/user-bots", response_model=UserBotResponse)
async def create_user_bot(
    payload: UserBotCreate,
    current_user: User = Depends(get_current_user),
    service: BotService = Depends(get_bot_service),
) -> UserBotResponse:
    """Select a complete bot template for the current user.

    The payload intentionally accepts no strategy, symbol, timeframe, signal, or risk fields --
    quote_order_quantity (montant investi par ordre) est le seul champ modifiable.
    """
    return service.create_user_bot(current_user.id, payload)


@router.get("/user-bots", response_model=list[UserBotResponse])
async def list_user_bots(
    current_user: User = Depends(get_current_user),
    service: BotService = Depends(get_bot_service),
) -> list[UserBotResponse]:
    """List bot instances selected by the current user."""
    return service.list_user_bots(current_user.id)


# Static /user-bots routes must stay above /user-bots/{instance_id}.
@router.get("/user-bots/performance-summary", response_model=UserPerformanceSummaryResponse)
async def get_user_bot_performance_summary(
    period_days: int = Query(30, ge=0, le=3650),
    bot_id: str | None = Query(None),
    model_name: str | None = Query(None),
    current_user: User = Depends(get_current_user),
    service: BotService = Depends(get_bot_service),
) -> UserPerformanceSummaryResponse:
    """Get real user performance summary across selected Spot bots."""
    return service.get_user_performance_summary(
        current_user.id,
        period_days=period_days,
        bot_id=bot_id,
        model_name=model_name,
    )


# Dynamic /user-bots routes must stay below every static /user-bots route.
@router.get("/user-bots/{instance_id}", response_model=UserBotResponse)
async def get_user_bot(
    instance_id: str,
    current_user: User = Depends(get_current_user),
    service: BotService = Depends(get_bot_service),
) -> UserBotResponse:
    """Get one user bot instance."""
    return service.get_user_bot(current_user.id, instance_id)


@router.post("/user-bots/{instance_id}/start", response_model=BotActionResponse)
async def start_user_bot(
    instance_id: str,
    current_user: User = Depends(get_current_user),
    service: BotService = Depends(get_bot_service),
) -> BotActionResponse:
    """Start a selected bot with its locked template configuration."""
    return service.start_user_bot(current_user.id, instance_id)


@router.post("/user-bots/{instance_id}/pause", response_model=BotActionResponse)
async def pause_user_bot(
    instance_id: str,
    current_user: User = Depends(get_current_user),
    service: BotService = Depends(get_bot_service),
) -> BotActionResponse:
    """Pause a selected bot."""
    return service.pause_user_bot(current_user.id, instance_id)


@router.post("/user-bots/{instance_id}/stop", response_model=BotActionResponse)
async def stop_user_bot(
    instance_id: str,
    current_user: User = Depends(get_current_user),
    service: BotService = Depends(get_bot_service),
) -> BotActionResponse:
    """Stop a selected bot."""
    return service.stop_user_bot(current_user.id, instance_id)


@router.get("/user-bots/{instance_id}/decisions", response_model=list[TradingDecisionResponse])
async def list_user_bot_decisions(
    instance_id: str,
    current_user: User = Depends(get_current_user),
    service: BotService = Depends(get_bot_service),
) -> list[TradingDecisionResponse]:
    """List recent decisions for a selected bot."""
    return service.list_decisions(current_user.id, instance_id)


@router.get("/user-bots/{instance_id}/orders", response_model=list[BotOrderResponse])
async def list_user_bot_orders(
    instance_id: str,
    current_user: User = Depends(get_current_user),
    service: BotService = Depends(get_bot_service),
) -> list[BotOrderResponse]:
    """List recent Binance Testnet orders created by a selected bot."""
    return service.list_orders(current_user.id, instance_id)


@router.get("/user-bots/{instance_id}/trades", response_model=list[BotTradeResponse])
async def list_user_bot_trades(
    instance_id: str,
    current_user: User = Depends(get_current_user),
    service: BotService = Depends(get_bot_service),
) -> list[BotTradeResponse]:
    """List recent Binance Testnet trades attributed to a selected bot."""
    return service.list_trades(current_user.id, instance_id)


@router.get("/user-bots/{instance_id}/position", response_model=BotPositionResponse | None)
async def get_user_bot_position(
    instance_id: str,
    current_user: User = Depends(get_current_user),
    service: BotService = Depends(get_bot_service),
) -> BotPositionResponse | None:
    """Get the bot-managed position for a selected bot."""
    return service.get_position(current_user.id, instance_id)


@router.get("/user-bots/{instance_id}/performance", response_model=BotPerformanceResponse)
async def get_user_bot_performance(
    instance_id: str,
    current_user: User = Depends(get_current_user),
    service: BotService = Depends(get_bot_service),
) -> BotPerformanceResponse:
    """Get performance summary for a selected bot."""
    return service.get_performance(current_user.id, instance_id)
