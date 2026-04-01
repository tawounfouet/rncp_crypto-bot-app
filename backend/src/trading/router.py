"""
Trading router for handling trading-related API endpoints.
Includes order management, transaction tracking, and trading operations.
"""

import logging

from auth.dependencies import get_current_user
from auth.models import User
from fastapi import APIRouter, Depends, HTTPException, Path, Query, status
from shared.core.exceptions import (
    BusinessLogicError,
    InsufficientFundsError,
    NotFoundError,
    ValidationError,
)
from shared.database import get_db
from shared.schemas.common import BaseResponse, PaginatedResponse
from sqlalchemy.orm import Session

from trading.schemas import (
    OrderCreate,
    OrderResponse,
    OrderSummary,
    PortfolioResponse,
    TradingStatsResponse,
    TransactionCreate,
    TransactionResponse,
    TransactionSummary,
)
from trading.service import TradingService

logger = logging.getLogger(__name__)

# Create router
router = APIRouter(prefix="/trading", tags=["trading"])


# Dependency to get trading service
def get_trading_service(db: Session = Depends(get_db)) -> TradingService:
    """Get trading service instance."""
    return TradingService(db)


# ============================================================================
# ORDER ENDPOINTS
# ============================================================================


@router.post("/orders", response_model=OrderResponse, status_code=status.HTTP_201_CREATED)
async def create_order(
    order_data: OrderCreate,
    current_user: User = Depends(get_current_user),
    trading_service: TradingService = Depends(get_trading_service),
):
    """
    Create a new trading order.

    This endpoint creates a new order and submits it to the exchange.
    The order can be MARKET, LIMIT, or various stop order types.

    Args:
        order_data: Order creation data
        current_user: Current authenticated user
        trading_service: Trading service instance

    Returns:
        Created order details with exchange confirmation

    Raises:
        HTTPException: If order creation fails
    """
    try:
        logger.info(f"User {current_user.username} creating {order_data.side} order " f"for {order_data.symbol}")

        order = await trading_service.create_order(user_id=current_user.id, order_data=order_data)

        return order

    except ValidationError as e:
        logger.warning(f"Order validation failed: {e.message}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "VALIDATION_ERROR",
                "message": e.message,
                "details": e.details,
            },
        ) from None
    except InsufficientFundsError as e:
        logger.warning(f"Insufficient funds for order: {e.message}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "INSUFFICIENT_FUNDS", "message": e.message},
        ) from None
    except BusinessLogicError as e:
        logger.error(f"Business logic error creating order: {e.message}")
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"error": "BUSINESS_LOGIC_ERROR", "message": e.message},
        ) from None
    except Exception as e:
        logger.error(f"Unexpected error creating order: {e!s}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "INTERNAL_ERROR", "message": "Failed to create order"},
        ) from None


@router.get("/orders", response_model=PaginatedResponse[OrderSummary])
async def get_user_orders(
    deployment_id: str | None = Query(None, description="Filter by deployment ID"),
    symbol: str | None = Query(None, description="Filter by symbol"),
    status: str | None = Query(None, description="Filter by order status"),
    side: str | None = Query(None, description="Filter by order side (BUY/SELL)"),
    start_date: str | None = Query(None, description="Start date (ISO format)"),
    end_date: str | None = Query(None, description="End date (ISO format)"),
    page: int = Query(1, ge=1, description="Page number"),
    size: int = Query(20, ge=1, le=100, description="Page size"),
    current_user: User = Depends(get_current_user),
    trading_service: TradingService = Depends(get_trading_service),
):
    """
    Get all orders for the current user with optional filters.

    Args:
        deployment_id: Filter by strategy deployment
        symbol: Filter by trading symbol
        status: Filter by order status
        side: Filter by order side
        start_date: Filter by start date
        end_date: Filter by end date
        page: Page number for pagination
        size: Number of items per page
        current_user: Current authenticated user
        trading_service: Trading service instance

    Returns:
        Paginated list of orders
    """
    try:
        filters = {
            "deployment_id": deployment_id,
            "symbol": symbol,
            "status": status,
            "side": side,
            "start_date": start_date,
            "end_date": end_date,
        }

        result = await trading_service.get_user_orders(
            user_id=current_user.id,
            filters=filters,
            page=page,
            size=size,
        )

        return result

    except Exception as e:
        logger.error(f"Error retrieving orders: {e!s}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "INTERNAL_ERROR", "message": "Failed to retrieve orders"},
        ) from None


@router.get("/orders/{order_id}", response_model=OrderResponse)
async def get_order_by_id(
    order_id: str = Path(..., description="Order ID"),
    current_user: User = Depends(get_current_user),
    trading_service: TradingService = Depends(get_trading_service),
):
    """
    Get detailed information about a specific order.

    Args:
        order_id: Order ID
        current_user: Current authenticated user
        trading_service: Trading service instance

    Returns:
        Order details including fills and status

    Raises:
        HTTPException: If order not found or access denied
    """
    try:
        order = await trading_service.get_order_by_id(order_id=order_id, user_id=current_user.id)

        if not order:
            raise NotFoundError(
                message=f"Order {order_id} not found",
                resource_type="Order",
                resource_id=order_id,
            )

        return order

    except NotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "NOT_FOUND", "message": e.message},
        ) from None
    except Exception as e:
        logger.error(f"Error retrieving order {order_id}: {e!s}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "INTERNAL_ERROR", "message": "Failed to retrieve order"},
        ) from None


@router.delete("/orders/{order_id}", response_model=BaseResponse)
async def cancel_order(
    order_id: str = Path(..., description="Order ID"),
    current_user: User = Depends(get_current_user),
    trading_service: TradingService = Depends(get_trading_service),
):
    """
    Cancel an open order.

    Args:
        order_id: Order ID to cancel
        current_user: Current authenticated user
        trading_service: Trading service instance

    Returns:
        Cancellation confirmation

    Raises:
        HTTPException: If order cannot be cancelled
    """
    try:
        logger.info(f"User {current_user.username} cancelling order {order_id}")

        await trading_service.cancel_order(order_id=order_id, user_id=current_user.id)

        return BaseResponse(
            success=True,
            message=f"Order {order_id} cancelled successfully",
        )

    except NotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "NOT_FOUND", "message": e.message},
        ) from None
    except BusinessLogicError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"error": "BUSINESS_LOGIC_ERROR", "message": e.message},
        ) from None
    except Exception as e:
        logger.error(f"Error cancelling order {order_id}: {e!s}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "INTERNAL_ERROR", "message": "Failed to cancel order"},
        ) from None


@router.get("/orders/{order_id}/status")
async def get_order_status(
    order_id: str = Path(..., description="Order ID"),
    current_user: User = Depends(get_current_user),
    trading_service: TradingService = Depends(get_trading_service),
):
    """
    Get real-time order status from exchange.

    Args:
        order_id: Order ID
        current_user: Current authenticated user
        trading_service: Trading service instance

    Returns:
        Current order status from exchange
    """
    try:
        status_data = await trading_service.get_order_status_from_exchange(order_id=order_id, user_id=current_user.id)

        return status_data

    except NotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "NOT_FOUND", "message": e.message},
        ) from None
    except Exception as e:
        logger.error(f"Error getting order status for {order_id}: {e!s}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "INTERNAL_ERROR", "message": "Failed to get order status"},
        ) from None


@router.get("/orders/deployment/{deployment_id}", response_model=list[OrderSummary])
async def get_deployment_orders(
    deployment_id: str = Path(..., description="Deployment ID"),
    current_user: User = Depends(get_current_user),
    trading_service: TradingService = Depends(get_trading_service),
):
    """
    Get all orders for a specific strategy deployment.

    Args:
        deployment_id: Strategy deployment ID
        current_user: Current authenticated user
        trading_service: Trading service instance

    Returns:
        List of orders for the deployment
    """
    try:
        orders = await trading_service.get_deployment_orders(deployment_id=deployment_id, user_id=current_user.id)

        return orders

    except NotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "NOT_FOUND", "message": e.message},
        ) from None
    except Exception as e:
        logger.error(
            f"Error getting orders for deployment {deployment_id}: {e!s}",
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "INTERNAL_ERROR",
                "message": "Failed to retrieve deployment orders",
            },
        ) from None


# ============================================================================
# TRANSACTION ENDPOINTS
# ============================================================================


@router.post(
    "/transactions",
    response_model=TransactionResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_transaction(
    transaction_data: TransactionCreate,
    current_user: User = Depends(get_current_user),
    trading_service: TradingService = Depends(get_trading_service),
):
    """
    Create a new transaction record.

    This is typically used for manual deposits, withdrawals, or fee tracking.
    Trade transactions are usually created automatically from order fills.

    Args:
        transaction_data: Transaction creation data
        current_user: Current authenticated user
        trading_service: Trading service instance

    Returns:
        Created transaction details
    """
    try:
        transaction = await trading_service.create_transaction(
            user_id=current_user.id, transaction_data=transaction_data
        )

        return transaction

    except ValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "VALIDATION_ERROR",
                "message": e.message,
                "details": e.details,
            },
        ) from None
    except Exception as e:
        logger.error(f"Error creating transaction: {e!s}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "INTERNAL_ERROR",
                "message": "Failed to create transaction",
            },
        ) from None


@router.get("/transactions", response_model=PaginatedResponse[TransactionSummary])
async def get_user_transactions(
    transaction_type: str | None = Query(None, description="Filter by type"),
    asset: str | None = Query(None, description="Filter by asset"),
    start_date: str | None = Query(None, description="Start date (ISO format)"),
    end_date: str | None = Query(None, description="End date (ISO format)"),
    page: int = Query(1, ge=1, description="Page number"),
    size: int = Query(20, ge=1, le=100, description="Page size"),
    current_user: User = Depends(get_current_user),
    trading_service: TradingService = Depends(get_trading_service),
):
    """
    Get all transactions for the current user with optional filters.

    Args:
        transaction_type: Filter by transaction type (TRADE, DEPOSIT, WITHDRAWAL, FEE)
        asset: Filter by asset
        start_date: Filter by start date
        end_date: Filter by end date
        page: Page number
        size: Items per page
        current_user: Current authenticated user
        trading_service: Trading service instance

    Returns:
        Paginated list of transactions
    """
    try:
        filters = {
            "transaction_type": transaction_type,
            "asset": asset,
            "start_date": start_date,
            "end_date": end_date,
        }

        result = await trading_service.get_user_transactions(
            user_id=current_user.id,
            filters=filters,
            page=page,
            size=size,
        )

        return result

    except Exception as e:
        logger.error(f"Error retrieving transactions: {e!s}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "INTERNAL_ERROR",
                "message": "Failed to retrieve transactions",
            },
        ) from None


@router.get("/transactions/{transaction_id}", response_model=TransactionResponse)
async def get_transaction_by_id(
    transaction_id: str = Path(..., description="Transaction ID"),
    current_user: User = Depends(get_current_user),
    trading_service: TradingService = Depends(get_trading_service),
):
    """
    Get detailed information about a specific transaction.

    Args:
        transaction_id: Transaction ID
        current_user: Current authenticated user
        trading_service: Trading service instance

    Returns:
        Transaction details
    """
    try:
        transaction = await trading_service.get_transaction_by_id(
            transaction_id=transaction_id, user_id=current_user.id
        )

        if not transaction:
            raise NotFoundError(
                message=f"Transaction {transaction_id} not found",
                resource_type="Transaction",
                resource_id=transaction_id,
            )

        return transaction

    except NotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "NOT_FOUND", "message": e.message},
        ) from None
    except Exception as e:
        logger.error(f"Error retrieving transaction {transaction_id}: {e!s}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "INTERNAL_ERROR",
                "message": "Failed to retrieve transaction",
            },
        ) from None


# ============================================================================
# PORTFOLIO AND STATISTICS ENDPOINTS
# ============================================================================


@router.get("/portfolio", response_model=PortfolioResponse)
async def get_user_portfolio(
    exchange: str | None = Query(None, description="Filter by exchange"),
    current_user: User = Depends(get_current_user),
    trading_service: TradingService = Depends(get_trading_service),
):
    """
    Get current portfolio with all asset balances and positions.

    Args:
        exchange: Optional exchange filter
        current_user: Current authenticated user
        trading_service: Trading service instance

    Returns:
        Portfolio with balances, positions, and total value
    """
    try:
        portfolio = await trading_service.get_user_portfolio(user_id=current_user.id, exchange=exchange)

        return portfolio

    except Exception as e:
        logger.error(f"Error retrieving portfolio: {e!s}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "INTERNAL_ERROR",
                "message": "Failed to retrieve portfolio",
            },
        ) from None


@router.get("/stats", response_model=TradingStatsResponse)
async def get_trading_statistics(
    period: str = Query("30d", description="Period for statistics (7d, 30d, 90d, 1y, all)"),
    deployment_id: str | None = Query(None, description="Filter by deployment"),
    current_user: User = Depends(get_current_user),
    trading_service: TradingService = Depends(get_trading_service),
):
    """
    Get trading statistics and performance metrics.

    Args:
        period: Time period for statistics
        deployment_id: Optional deployment filter
        current_user: Current authenticated user
        trading_service: Trading service instance

    Returns:
        Trading statistics including PnL, win rate, and trade counts
    """
    try:
        stats = await trading_service.get_trading_statistics(
            user_id=current_user.id, period=period, deployment_id=deployment_id
        )

        return stats

    except ValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "VALIDATION_ERROR", "message": e.message},
        ) from None
    except Exception as e:
        logger.error(f"Error retrieving trading stats: {e!s}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "INTERNAL_ERROR",
                "message": "Failed to retrieve statistics",
            },
        ) from None


@router.get("/positions")
async def get_open_positions(
    symbol: str | None = Query(None, description="Filter by symbol"),
    current_user: User = Depends(get_current_user),
    trading_service: TradingService = Depends(get_trading_service),
):
    """
    Get all open positions for the current user.

    Args:
        symbol: Optional symbol filter
        current_user: Current authenticated user
        trading_service: Trading service instance

    Returns:
        List of open positions with current P&L
    """
    try:
        positions = await trading_service.get_open_positions(user_id=current_user.id, symbol=symbol)

        return positions

    except Exception as e:
        logger.error(f"Error retrieving positions: {e!s}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "INTERNAL_ERROR",
                "message": "Failed to retrieve positions",
            },
        ) from None


# ============================================================================
# MARKET OPERATIONS
# ============================================================================


@router.post("/orders/market/buy")
async def quick_market_buy(
    symbol: str = Query(..., description="Trading symbol"),
    quote_amount: float = Query(..., gt=0, description="Amount in quote asset"),
    deployment_id: str | None = Query(None, description="Link to deployment"),
    current_user: User = Depends(get_current_user),
    trading_service: TradingService = Depends(get_trading_service),
):
    """
    Quick market buy order - simplified endpoint for buying at market price.

    Args:
        symbol: Trading symbol (e.g., BTCUSDT)
        quote_amount: Amount to spend in quote asset (e.g., USDT)
        deployment_id: Optional strategy deployment ID
        current_user: Current authenticated user
        trading_service: Trading service instance

    Returns:
        Created order details
    """
    try:
        order = await trading_service.market_buy(
            user_id=current_user.id,
            symbol=symbol,
            quote_amount=quote_amount,
            deployment_id=deployment_id,
        )

        return order

    except Exception as e:
        logger.error(f"Error executing market buy: {e!s}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "INTERNAL_ERROR",
                "message": "Failed to execute market buy",
            },
        ) from None


@router.post("/orders/market/sell")
async def quick_market_sell(
    symbol: str = Query(..., description="Trading symbol"),
    quantity: float = Query(..., gt=0, description="Quantity to sell"),
    deployment_id: str | None = Query(None, description="Link to deployment"),
    current_user: User = Depends(get_current_user),
    trading_service: TradingService = Depends(get_trading_service),
):
    """
    Quick market sell order - simplified endpoint for selling at market price.

    Args:
        symbol: Trading symbol (e.g., BTCUSDT)
        quantity: Quantity to sell in base asset
        deployment_id: Optional strategy deployment ID
        current_user: Current authenticated user
        trading_service: Trading service instance

    Returns:
        Created order details
    """
    try:
        order = await trading_service.market_sell(
            user_id=current_user.id,
            symbol=symbol,
            quantity=quantity,
            deployment_id=deployment_id,
        )

        return order

    except Exception as e:
        logger.error(f"Error executing market sell: {e!s}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "INTERNAL_ERROR",
                "message": "Failed to execute market sell",
            },
        ) from None


# ============================================================================
# UTILITY ENDPOINTS
# ============================================================================


@router.get("/health")
async def trading_health_check(
    trading_service: TradingService = Depends(get_trading_service),
):
    """
    Health check for trading module and exchange connectivity.

    Returns:
        Health status of trading services
    """
    try:
        health_status = await trading_service.check_health()
        return health_status

    except Exception as e:
        logger.error(f"Trading health check failed: {e!s}", exc_info=True)
        return {
            "status": "unhealthy",
            "error": str(e),
        }
