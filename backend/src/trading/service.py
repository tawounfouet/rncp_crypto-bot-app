"""
Trading service for managing orders, transactions, and trading operations.
Handles interaction with exchanges and order lifecycle management.
"""

import logging
import math
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

from shared.core.exceptions import (
    BusinessLogicError,
    InsufficientFundsError,
    NotFoundError,
    ValidationError,
)
from shared.schemas.common import PaginatedResponse, PaginationInfo
from sqlalchemy import desc
from sqlalchemy.orm import Session
from strategy.models import StrategyDeployment

from trading.models import Order, Transaction
from trading.schemas import (
    AssetBalance,
    OrderCreate,
    OrderResponse,
    OrderStatusEnum,
    OrderSummary,
    Portfolio,
    PortfolioResponse,
    TradingStats,
    TradingStatsResponse,
    TransactionCreate,
    TransactionResponse,
    TransactionSummary,
)

logger = logging.getLogger(__name__)


class TradingService:
    """Service for handling all trading operations."""

    def __init__(self, db: Session):
        """
        Initialize trading service.

        Args:
            db: Database session
        """
        self.db = db

    # ========================================================================
    # ORDER MANAGEMENT
    # ========================================================================

    async def create_order(self, user_id: str, order_data: OrderCreate) -> OrderResponse:
        """
        Create a new trading order.

        Args:
            user_id: User ID creating the order
            order_data: Order creation data

        Returns:
            Created order details

        Raises:
            ValidationError: If order data is invalid
            InsufficientFundsError: If insufficient funds
            BusinessLogicError: If business rules are violated
        """
        try:
            # Validate deployment exists and belongs to user
            deployment = (
                self.db.query(StrategyDeployment)
                .filter(
                    StrategyDeployment.id == order_data.deployment_id,
                    StrategyDeployment.user_id == user_id,
                )
                .first()
            )

            if not deployment:
                raise NotFoundError(
                    message=f"Deployment {order_data.deployment_id} not found",
                    resource_type="StrategyDeployment",
                    resource_id=order_data.deployment_id,
                )

            # Validate order parameters
            self._validate_order_parameters(order_data)

            # Create order in database
            order = Order(
                deployment_id=order_data.deployment_id,
                user_id=user_id,
                exchange=deployment.exchange,
                symbol=order_data.symbol,
                order_type=order_data.order_type.value,
                side=order_data.side.value,
                time_in_force=(order_data.time_in_force.value if order_data.time_in_force else "GTC"),
                quantity=order_data.quantity,
                price=order_data.price,
                stop_price=order_data.stop_price,
                quote_order_quantity=order_data.quote_order_quantity,
                status=OrderStatusEnum.NEW.value,
            )

            self.db.add(order)
            self.db.commit()
            self.db.refresh(order)

            # TODO: Submit order to exchange (Binance API integration)
            # exchange_response = await self._submit_to_exchange(order)
            # order.update_from_exchange_response(exchange_response)
            # self.db.commit()

            logger.info(f"Created order {order.id} for user {user_id}: {order.side} {order.quantity} {order.symbol}")

            return OrderResponse.model_validate(order)

        except (ValidationError, NotFoundError, InsufficientFundsError):
            raise
        except Exception as e:
            self.db.rollback()
            logger.error(f"Error creating order: {e!s}", exc_info=True)
            raise BusinessLogicError(
                message=f"Failed to create order: {e!s}",
                details={"user_id": user_id, "order_data": order_data.model_dump()},
            ) from None

    async def get_user_orders(
        self,
        user_id: str,
        filters: dict[str, Any] | None = None,
        page: int = 1,
        size: int = 20,
    ) -> PaginatedResponse[OrderSummary]:
        """
        Get paginated list of user orders with filters.

        Args:
            user_id: User ID
            filters: Optional filter dict
            page: Page number
            size: Page size

        Returns:
            Paginated list of orders
        """
        try:
            query = self.db.query(Order).filter(Order.user_id == user_id)

            # Apply filters
            if filters:
                if filters.get("deployment_id"):
                    query = query.filter(Order.deployment_id == filters["deployment_id"])
                if filters.get("symbol"):
                    query = query.filter(Order.symbol == filters["symbol"])
                if filters.get("status"):
                    query = query.filter(Order.status == filters["status"])
                if filters.get("side"):
                    query = query.filter(Order.side == filters["side"])
                if filters.get("start_date"):
                    start_date = datetime.fromisoformat(filters["start_date"])
                    query = query.filter(Order.created_at >= start_date)
                if filters.get("end_date"):
                    end_date = datetime.fromisoformat(filters["end_date"])
                    query = query.filter(Order.created_at <= end_date)

            # Get total count
            total = query.count()

            # Apply pagination
            orders = query.order_by(desc(Order.created_at)).offset((page - 1) * size).limit(size).all()

            # Convert to response models
            order_summaries = [OrderSummary.model_validate(order) for order in orders]

            return PaginatedResponse(
                success=True,
                message=f"Retrieved {len(order_summaries)} orders",
                data=order_summaries,
                pagination=PaginationInfo(
                    page=page,
                    size=size,
                    total=total,
                    pages=math.ceil(total / size) if total > 0 else 0,
                ),
            )

        except Exception as e:
            logger.error(f"Error getting user orders: {e!s}", exc_info=True)
            raise

    async def get_order_by_id(self, order_id: str, user_id: str) -> OrderResponse | None:
        """
        Get order by ID.

        Args:
            order_id: Order ID
            user_id: User ID (for authorization)

        Returns:
            Order details or None
        """
        order = self.db.query(Order).filter(Order.id == order_id, Order.user_id == user_id).first()

        if not order:
            return None

        return OrderResponse.model_validate(order)

    async def cancel_order(self, order_id: str, user_id: str) -> bool:
        """
        Cancel an open order.

        Args:
            order_id: Order ID
            user_id: User ID (for authorization)

        Returns:
            True if cancelled successfully

        Raises:
            NotFoundError: If order not found
            BusinessLogicError: If order cannot be cancelled
        """
        try:
            order = self.db.query(Order).filter(Order.id == order_id, Order.user_id == user_id).first()

            if not order:
                raise NotFoundError(
                    message=f"Order {order_id} not found",
                    resource_type="Order",
                    resource_id=order_id,
                )

            if not order.is_open:
                raise BusinessLogicError(message=f"Order {order_id} cannot be cancelled (status: {order.status})")

            # TODO: Cancel on exchange
            # await self._cancel_on_exchange(order)

            order.status = OrderStatusEnum.CANCELED.value
            self.db.commit()

            logger.info(f"Cancelled order {order_id} for user {user_id}")
            return True

        except (NotFoundError, BusinessLogicError):
            raise
        except Exception as e:
            self.db.rollback()
            logger.error(f"Error cancelling order: {e!s}", exc_info=True)
            raise BusinessLogicError(message=f"Failed to cancel order: {e!s}") from None

    async def get_order_status_from_exchange(self, order_id: str, user_id: str) -> dict[str, Any]:
        """
        Get real-time order status from exchange.

        Args:
            order_id: Order ID
            user_id: User ID

        Returns:
            Order status from exchange
        """
        order = await self.get_order_by_id(order_id, user_id)

        if not order:
            raise NotFoundError(
                message=f"Order {order_id} not found",
                resource_type="Order",
                resource_id=order_id,
            )

        # TODO: Query exchange for real-time status
        # For now, return database status
        return {
            "order_id": order.id,
            "exchange_order_id": order.exchange_order_id,
            "status": order.status,
            "symbol": order.symbol,
            "executed_quantity": str(order.executed_quantity),
            "remaining_quantity": str(order.remaining_quantity),
        }

    async def get_deployment_orders(self, deployment_id: str, user_id: str) -> list[OrderSummary]:
        """
        Get all orders for a deployment.

        Args:
            deployment_id: Deployment ID
            user_id: User ID

        Returns:
            List of orders
        """
        orders = (
            self.db.query(Order)
            .filter(Order.deployment_id == deployment_id, Order.user_id == user_id)
            .order_by(desc(Order.created_at))
            .all()
        )

        return [OrderSummary.model_validate(order) for order in orders]

    # ========================================================================
    # TRANSACTION MANAGEMENT
    # ========================================================================

    async def create_transaction(self, user_id: str, transaction_data: TransactionCreate) -> TransactionResponse:
        """
        Create a new transaction record.

        Args:
            user_id: User ID
            transaction_data: Transaction data

        Returns:
            Created transaction
        """
        try:
            transaction = Transaction(
                user_id=user_id,
                exchange=transaction_data.exchange,
                transaction_type=transaction_data.transaction_type.value,
                order_id=transaction_data.order_id,
                asset=transaction_data.asset,
                amount=transaction_data.amount,
                direction=transaction_data.direction.value,
                quote_asset=transaction_data.quote_asset,
                quote_amount=transaction_data.quote_amount,
                price=transaction_data.price,
                fee_amount=transaction_data.fee_amount,
                fee_asset=transaction_data.fee_asset,
                external_id=transaction_data.external_id,
                status="COMPLETED",
                description=transaction_data.description,
                timestamp=datetime.now(UTC),
            )

            self.db.add(transaction)
            self.db.commit()
            self.db.refresh(transaction)

            logger.info(
                f"Created transaction {transaction.id} for user {user_id}: "
                f"{transaction.transaction_type} {transaction.amount} {transaction.asset}"
            )

            return TransactionResponse.model_validate(transaction)

        except Exception as e:
            self.db.rollback()
            logger.error(f"Error creating transaction: {e!s}", exc_info=True)
            raise

    async def get_user_transactions(
        self,
        user_id: str,
        filters: dict[str, Any] | None = None,
        page: int = 1,
        size: int = 20,
    ) -> PaginatedResponse[TransactionSummary]:
        """
        Get paginated list of user transactions.

        Args:
            user_id: User ID
            filters: Optional filters
            page: Page number
            size: Page size

        Returns:
            Paginated transactions
        """
        try:
            query = self.db.query(Transaction).filter(Transaction.user_id == user_id)

            # Apply filters
            if filters:
                if filters.get("transaction_type"):
                    query = query.filter(Transaction.transaction_type == filters["transaction_type"])
                if filters.get("asset"):
                    query = query.filter(Transaction.asset == filters["asset"])
                if filters.get("start_date"):
                    start_date = datetime.fromisoformat(filters["start_date"])
                    query = query.filter(Transaction.timestamp >= start_date)
                if filters.get("end_date"):
                    end_date = datetime.fromisoformat(filters["end_date"])
                    query = query.filter(Transaction.timestamp <= end_date)

            # Get total count
            total = query.count()

            # Apply pagination
            transactions = query.order_by(desc(Transaction.timestamp)).offset((page - 1) * size).limit(size).all()

            # Convert to response models
            transaction_summaries = [TransactionSummary.model_validate(t) for t in transactions]

            return PaginatedResponse(
                success=True,
                message=f"Retrieved {len(transaction_summaries)} transactions",
                data=transaction_summaries,
                pagination=PaginationInfo(
                    page=page,
                    size=size,
                    total=total,
                    pages=math.ceil(total / size) if total > 0 else 0,
                ),
            )

        except Exception as e:
            logger.error(f"Error getting user transactions: {e!s}", exc_info=True)
            raise

    async def get_transaction_by_id(self, transaction_id: str, user_id: str) -> TransactionResponse | None:
        """Get transaction by ID."""
        transaction = (
            self.db.query(Transaction).filter(Transaction.id == transaction_id, Transaction.user_id == user_id).first()
        )

        if not transaction:
            return None

        return TransactionResponse.model_validate(transaction)

    # ========================================================================
    # PORTFOLIO AND STATISTICS
    # ========================================================================

    async def get_user_portfolio(self, user_id: str, exchange: str | None = None) -> PortfolioResponse:
        """
        Get user portfolio with real balances from Binance.

        Args:
            user_id: User ID
            exchange: Optional exchange filter

        Returns:
            Portfolio information
        """
        from auth.models import UserSettings  # lazy to avoid circular import
        from market.clients.binance import ClientBinance

        target_exchange = exchange or "binance"
        empty_portfolio = Portfolio(
            user_id=user_id,
            exchange=target_exchange,
            balances=[],
            total_usd_value=Decimal("0"),
            last_updated=datetime.now(UTC),
        )

        # Retrieve stored API credentials
        settings = self.db.query(UserSettings).filter(UserSettings.user_id == user_id).first()
        if not settings or not settings.has_credentials_for_exchange("binance"):
            return PortfolioResponse(
                success=False,
                message="Clés API Binance non configurées",
                portfolio=empty_portfolio,
            )

        try:
            binance_client = ClientBinance.from_user_settings(settings)
        except ValueError as exc:
            logger.warning("Binance credentials invalid for user %s: %s", user_id, exc)
            return PortfolioResponse(
                success=False,
                message="Clés API Binance invalides ou manquantes",
                portfolio=empty_portfolio,
            )

        account_info = binance_client.get_account_info()
        if account_info is None:
            return PortfolioResponse(
                success=False,
                message="Impossible de contacter Binance (vérifiez les permissions IP de vos clés API)",
                portfolio=empty_portfolio,
            )

        # Keep only non-zero balances
        raw_balances = [
            b
            for b in account_info.get("balances", [])
            if float(b.get("free", "0")) > 0 or float(b.get("locked", "0")) > 0
        ]

        # Build USD price map from all tickers (USDT and USDC pairs)
        all_tickers = binance_client.get_all_tickers() or []
        usdt_prices: dict[str, Decimal] = {
            "USDT": Decimal("1"),
            "BUSD": Decimal("1"),
            "USDC": Decimal("1"),
            "TUSD": Decimal("1"),
        }
        for ticker in all_tickers:
            symbol = ticker.get("symbol", "")
            price_str = ticker.get("price")
            if (symbol.endswith("USDT") or symbol.endswith("USDC")) and price_str:
                try:
                    usdt_prices[symbol[:-4]] = Decimal(str(price_str))
                except Exception:
                    pass

        balances: list[AssetBalance] = []
        total_usd = Decimal("0")
        for b in raw_balances:
            asset = b["asset"]
            free = Decimal(str(b.get("free", "0")))
            locked = Decimal(str(b.get("locked", "0")))
            total = free + locked
            usd_price = usdt_prices.get(asset)
            # LD tokens (Simple Earn) are 1:1 with the underlying asset
            if usd_price is None and asset.startswith("LD") and len(asset) > 2:
                usd_price = usdt_prices.get(asset[2:])
            usd_value = (total * usd_price).quantize(Decimal("0.01")) if usd_price else None
            if usd_value is not None:
                total_usd += usd_value
            balances.append(AssetBalance(asset=asset, total=total, available=free, locked=locked, usd_value=usd_value))

        balances.sort(key=lambda b: b.usd_value or Decimal("0"), reverse=True)

        portfolio = Portfolio(
            user_id=user_id,
            exchange=target_exchange,
            balances=balances,
            total_usd_value=total_usd.quantize(Decimal("0.01")),
            last_updated=datetime.now(UTC),
        )
        logger.info("Binance portfolio user=%s: %d assets, total=$%.2f", user_id, len(balances), float(total_usd))
        return PortfolioResponse(success=True, message="Portefeuille récupéré depuis Binance", portfolio=portfolio)

    async def get_trading_statistics(
        self,
        user_id: str,
        period: str = "30d",
        deployment_id: str | None = None,
    ) -> TradingStatsResponse:
        """
        Get trading statistics for a period.

        Args:
            user_id: User ID
            period: Time period (7d, 30d, 90d, 1y, all)
            deployment_id: Optional deployment filter

        Returns:
            Trading statistics
        """
        try:
            # Calculate period start date
            period_days = {
                "7d": 7,
                "30d": 30,
                "90d": 90,
                "1y": 365,
                "all": None,
            }

            start_date = None
            if period_days.get(period):
                start_date = datetime.now(UTC) - timedelta(days=period_days[period])

            # Query orders
            query = self.db.query(Order).filter(Order.user_id == user_id, Order.status == OrderStatusEnum.FILLED.value)

            if deployment_id:
                query = query.filter(Order.deployment_id == deployment_id)

            if start_date:
                query = query.filter(Order.created_at >= start_date)

            filled_orders = query.all()

            # Calculate statistics
            total_trades = len(filled_orders)
            winning_trades = 0
            losing_trades = 0
            total_pnl = Decimal("0")

            # TODO: Implement proper P&L calculation
            # This requires tracking buy/sell pairs and calculating profit/loss

            stats = TradingStats(
                total_trades=total_trades,
                winning_trades=winning_trades,
                losing_trades=losing_trades,
                win_rate=winning_trades / total_trades if total_trades > 0 else 0.0,
                total_profit_loss=total_pnl,
                average_profit=Decimal("0"),
                average_loss=Decimal("0"),
                max_drawdown=Decimal("0"),
                sharpe_ratio=None,
            )

            return TradingStatsResponse(
                success=True,
                message=f"Trading statistics for {period}",
                stats=stats,
            )

        except Exception as e:
            logger.error(f"Error getting trading statistics: {e!s}", exc_info=True)
            raise

    async def get_open_positions(self, user_id: str, symbol: str | None = None) -> list[dict[str, Any]]:
        """
        Get open positions.

        Args:
            user_id: User ID
            symbol: Optional symbol filter

        Returns:
            List of open positions
        """
        # TODO: Implement position tracking
        return []

    # ========================================================================
    # QUICK MARKET OPERATIONS
    # ========================================================================

    async def market_buy(
        self,
        user_id: str,
        symbol: str,
        quote_amount: float,
        deployment_id: str | None = None,
    ) -> OrderResponse:
        """Quick market buy."""
        # Find or create default deployment if not provided
        if not deployment_id:
            deployment_id = await self._get_or_create_manual_deployment(user_id)

        order_data = OrderCreate(
            deployment_id=deployment_id,
            symbol=symbol,
            order_type="MARKET",
            side="BUY",
            quantity=Decimal("0"),  # Will be calculated
            quote_order_quantity=Decimal(str(quote_amount)),
        )

        return await self.create_order(user_id, order_data)

    async def market_sell(
        self,
        user_id: str,
        symbol: str,
        quantity: float,
        deployment_id: str | None = None,
    ) -> OrderResponse:
        """Quick market sell."""
        if not deployment_id:
            deployment_id = await self._get_or_create_manual_deployment(user_id)

        order_data = OrderCreate(
            deployment_id=deployment_id,
            symbol=symbol,
            order_type="MARKET",
            side="SELL",
            quantity=Decimal(str(quantity)),
        )

        return await self.create_order(user_id, order_data)

    # ========================================================================
    # UTILITY METHODS
    # ========================================================================

    async def check_health(self) -> dict[str, Any]:
        """Check health of trading services."""
        return {
            "status": "healthy",
            "database": "connected",
            "exchange": "not_connected",  # TODO: Check exchange connectivity
        }

    def _validate_order_parameters(self, order_data: OrderCreate) -> None:
        """Validate order parameters."""
        # Validate LIMIT orders have price
        if order_data.order_type.value in [
            "LIMIT",
            "STOP_LOSS_LIMIT",
            "TAKE_PROFIT_LIMIT",
        ]:
            if not order_data.price:
                raise ValidationError(
                    message="Price is required for limit orders",
                    field="price",
                )

        # Validate STOP orders have stop_price
        if order_data.order_type.value in ["STOP_LOSS", "STOP_LOSS_LIMIT"]:
            if not order_data.stop_price:
                raise ValidationError(
                    message="Stop price is required for stop orders",
                    field="stop_price",
                )

        # Validate quantity or quote_order_quantity
        if not order_data.quantity and not order_data.quote_order_quantity:
            raise ValidationError(
                message="Either quantity or quote_order_quantity must be provided",
                field="quantity",
            )

    async def _get_or_create_manual_deployment(self, user_id: str) -> str:
        """Get or create a manual trading deployment for the user."""
        # TODO: Implement this to find or create a default deployment
        # For now, this is a placeholder
        raise BusinessLogicError(message="Manual deployment not configured. Please specify deployment_id.")
