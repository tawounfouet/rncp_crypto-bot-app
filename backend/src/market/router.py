"""
Market data router for handling market data API endpoints.
Includes endpoints for fetching historical data, current prices, symbols, and technical indicators.
"""

import logging
from datetime import UTC, datetime, timedelta

from auth.dependencies import get_current_user
from auth.models import User
from fastapi import APIRouter, Depends, HTTPException, Path, Query, status
from shared.core.exceptions import NotFoundError, ValidationError
from shared.database import get_db
from shared.schemas.common import BaseResponse
from sqlalchemy.orm import Session

from market.insert_service import MarketDataInsertService
from market.schemas import (
    MarketDataListResponse,
    MarketDataRequest,
    MarketDataResponse,
    MarketSummary,
    MarketSummaryResponse,
    PriceInfo,
    PriceResponse,
    SymbolInfo,
    SymbolListResponse,
    TechnicalIndicators,
    TechnicalIndicatorsResponse,
    TradingPair,
)
from market.service import MarketDataService

logger = logging.getLogger(__name__)

# Create router
router = APIRouter(prefix="/market", tags=["Market Data"])

# Constants
SYMBOL_DESCRIPTION = "Trading symbol (e.g., BTCUSDT)"


# Dependency to get market data service
def get_market_data_service() -> MarketDataService:
    """Get market data service instance."""
    return MarketDataService()


# ============================================================================
# MARKET DATA INSERTION ENDPOINT (NEW - Real Binance Data)
# ============================================================================


@router.post("/data/insert", response_model=BaseResponse)
async def insert_historical_data(
    request: MarketDataRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> BaseResponse:
    """
    **Insert historical market data from Binance into PostgreSQL database.**

    This endpoint fetches real OHLCV data from Binance and stores it in the database.
    Uses UPSERT logic to handle duplicate records (updates if exists, inserts if new).

    **Parameters:**
    - **symbol**: Trading pair (e.g., 'BTCUSDT')
    - **interval**: Timeframe ('1m', '5m', '15m', '30m', '1h', '4h', '1d', '1w')
    - **start_time**: Start datetime for historical data (ISO format)
    - **end_time**: End datetime (optional, defaults to now)
    - **limit**: Maximum records to fetch (default: 1000, max: 1000)

    **Example Request:**
    ```json
    {
        "symbol": "BTCUSDT",
        "interval": "1h",
        "start_time": "2024-01-01T00:00:00Z",
        "end_time": "2024-01-31T23:59:59Z",
        "limit": 744
    }
    ```

    **Returns:**
    Statistics about the insertion:
    - `inserted`: Number of new records inserted
    - `updated`: Number of existing records updated
    - `failed`: Number of failed insertions
    - `total`: Total records processed
    """
    try:
        logger.info(f"User {current_user.username} requesting data insertion for {request.symbol} ({request.interval})")

        # Create insert service
        insert_service = MarketDataInsertService(db)

        # Validate symbol
        is_valid = insert_service.validate_symbol(request.exchange, request.symbol)
        if not is_valid:
            raise ValidationError(f"Invalid trading symbol: {request.symbol}")

        # Set default end_time if not provided
        end_time = request.end_time or datetime.now(UTC)

        # Validate date range
        if request.start_time >= end_time:
            raise ValidationError("start_time must be before end_time")

        # Check existing data count
        existing_count = insert_service.get_data_count(
            request.symbol, request.interval, request.start_time, end_time, exchange=request.exchange
        )

        logger.info(f"Found {existing_count} existing records for {request.symbol} ({request.interval}) in database")

        # Insert data from the exchange
        result = insert_service.insert_historical_data(
            exchange=request.exchange,
            symbol=request.symbol,
            interval=request.interval,
            start_time=request.start_time,
            end_time=end_time,
            limit=request.limit,
        )

        return BaseResponse(
            success=True,
            message=(
                f"Successfully processed {result['total']} records for {request.symbol}. "
                f"Inserted: {result['inserted']}, Updated: {result['updated']}, "
                f"Failed: {result['failed']}"
            ),
            data=result,
        )

    except ValidationError as e:
        logger.warning(f"Validation error: {e!s}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from None
    except Exception as e:
        logger.error(f"Error inserting historical data: {e!s}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to insert historical data: {e!s}",
        ) from None


# ============================================================================
# MARKET DATA ENDPOINTS
# ============================================================================


@router.post("/data", response_model=MarketDataListResponse)
async def fetch_market_data(
    request: MarketDataRequest,
    current_user: User = Depends(get_current_user),
    market_service: MarketDataService = Depends(get_market_data_service),
) -> MarketDataListResponse:
    """
    Fetch historical market data (OHLCV) for a specific symbol and timeframe.

    - **symbol**: Trading symbol (e.g., BTCUSDT)
    - **interval**: Timeframe (e.g., 1m, 5m, 15m, 1h, 4h, 1d)
    - **start_time**: Optional start time for historical data
    - **end_time**: Optional end time for historical data
    - **limit**: Number of records to fetch (default: 100, max: 1000)
    """
    try:
        logger.info(f"User {current_user.username} fetching market data for {request.symbol} ({request.interval})")

        # Validate symbol
        is_valid = await market_service.validate_symbol(request.symbol)
        if not is_valid:
            raise ValidationError(f"Invalid symbol: {request.symbol}")

        # Calculate date range if not provided
        end_time = request.end_time or datetime.now(UTC)
        start_time = request.start_time or (end_time - timedelta(days=30))

        # Fetch historical data
        df = await market_service.get_historical_data(
            symbol=request.symbol,
            timeframe=request.interval,
            start_date=start_time,
            end_date=end_time,
            limit=request.limit,
        )

        # Convert DataFrame to response models
        data_list = []
        for _, row in df.iterrows():
            data_list.append(
                MarketDataResponse(
                    id=f"{request.symbol}_{request.interval}_{row['timestamp']}",
                    symbol=request.symbol,
                    exchange="binance",
                    interval_timeframe=request.interval,
                    open_time=row["timestamp"],
                    open_price=row["open"],
                    high_price=row["high"],
                    low_price=row["low"],
                    close_price=row["close"],
                    volume=row["volume"],
                    close_time=row["timestamp"],
                    created_at=datetime.now(UTC),
                )
            )

        return MarketDataListResponse(
            success=True,
            message=f"Fetched {len(data_list)} market data records",
            data=data_list,
            symbol=request.symbol,
            interval=request.interval,
            count=len(data_list),
        )

    except ValidationError as e:
        logger.warning(f"Validation error: {e!s}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from None
    except NotFoundError as e:
        logger.warning(f"Not found: {e!s}")
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from None
    except Exception as e:
        logger.error(f"Error fetching market data: {e!s}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch market data",
        ) from None


@router.get("/data/latest/{symbol}", response_model=MarketDataListResponse)
async def get_latest_market_data(
    symbol: str = Path(..., description=SYMBOL_DESCRIPTION),
    interval: str = Query("1h", description="Timeframe (e.g., 1m, 5m, 1h, 1d)"),
    periods: int = Query(100, ge=1, le=1000, description="Number of periods to fetch"),
    exchange: str = Query("binance", description="Exchange source (e.g., binance, kraken)"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> MarketDataListResponse:
    """
    Get the latest market data for a symbol from PostgreSQL database.

    - **symbol**: Trading symbol
    - **interval**: Timeframe
    - **periods**: Number of periods to fetch
    - **exchange**: Exchange source
    """
    try:
        logger.info(f"User {current_user.username} fetching latest {periods} periods for {symbol} ({interval})")

        # Create service instance
        insert_service = MarketDataInsertService(db)

        # Validate symbol
        is_valid = insert_service.validate_symbol(exchange, symbol)
        if not is_valid:
            raise ValidationError(f"Invalid symbol: {symbol}")

        # Fetch latest data from PostgreSQL
        data_records = insert_service.get_latest_data(
            symbol=symbol, interval=interval, limit=periods, exchange=exchange
        )

        if not data_records:
            logger.warning(f"No data found in database for {symbol} ({interval})")
            return MarketDataListResponse(
                success=True,
                message=f"No data found for {symbol} ({interval})",
                data=[],
                symbol=symbol,
                interval=interval,
                count=0,
            )

        # Convert to response
        data_list = []
        for record in data_records:
            data_list.append(
                MarketDataResponse(
                    id=record["id"],
                    symbol=record["symbol"],
                    exchange=record["exchange"],
                    interval_timeframe=record["interval_timeframe"],
                    open_time=record["open_time"],
                    close_time=record["close_time"],
                    open_price=record["open_price"],
                    high_price=record["high_price"],
                    low_price=record["low_price"],
                    close_price=record["close_price"],
                    volume=record["volume"],
                    quote_asset_volume=record["quote_asset_volume"],
                    number_of_trades=record["number_of_trades"],
                    taker_buy_base_volume=record["taker_buy_base_volume"],
                    taker_buy_quote_volume=record["taker_buy_quote_volume"],
                    created_at=datetime.now(UTC),
                )
            )

        return MarketDataListResponse(
            success=True,
            message=f"Fetched latest {len(data_list)} records from database",
            data=data_list,
            symbol=symbol,
            interval=interval,
            count=len(data_list),
        )

    except ValidationError as e:
        logger.warning(f"Validation error: {e!s}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from None
    except Exception as e:
        logger.error(f"Error fetching latest data: {e!s}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch latest market data: {e!s}",
        ) from None


# ============================================================================
# PRICE ENDPOINTS
# ============================================================================


@router.get("/price/{symbol}", response_model=PriceResponse)
async def get_current_price(
    symbol: str = Path(..., description=SYMBOL_DESCRIPTION),
    current_user: User = Depends(get_current_user),
    market_service: MarketDataService = Depends(get_market_data_service),
) -> PriceResponse:
    """
    Get current price information for a symbol.

    - **symbol**: Trading symbol

    Returns current price, 24h change, high, low, and volume.
    """
    try:
        logger.info(f"User {current_user.username} fetching price for {symbol}")

        # Validate symbol
        is_valid = await market_service.validate_symbol(symbol)
        if not is_valid:
            raise ValidationError(f"Invalid symbol: {symbol}")

        # Get latest data for price calculation
        df = await market_service.get_latest_data(symbol=symbol, timeframe="1h", periods=24)

        if df.empty:
            raise NotFoundError(f"No price data available for {symbol}")

        latest = df.iloc[-1]
        first = df.iloc[0]

        price_change = latest["close"] - first["open"]
        price_change_percent = (price_change / first["open"]) * 100

        price_info = PriceInfo(
            symbol=symbol,
            price=latest["close"],
            price_change=price_change,
            price_change_percent=price_change_percent,
            high_24h=df["high"].max(),
            low_24h=df["low"].min(),
            volume_24h=df["volume"].sum(),
            timestamp=latest["timestamp"],
        )

        return PriceResponse(success=True, message=f"Current price for {symbol}", data=price_info)

    except ValidationError as e:
        logger.warning(f"Validation error: {e!s}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from None
    except NotFoundError as e:
        logger.warning(f"Not found: {e!s}")
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from None
    except Exception as e:
        logger.error(f"Error fetching price: {e!s}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch price",
        ) from None


@router.get("/prices", response_model=list[PriceInfo])
async def get_multiple_prices(
    symbols: str = Query(..., description="Comma-separated list of symbols"),
    current_user: User = Depends(get_current_user),
    market_service: MarketDataService = Depends(get_market_data_service),
) -> list[PriceInfo]:
    """
    Get current prices for multiple symbols.

    - **symbols**: Comma-separated list of trading symbols (e.g., BTCUSDT,ETHUSDT,BNBUSDT)
    """
    try:
        symbol_list = [s.strip().upper() for s in symbols.split(",")]
        logger.info(f"User {current_user.username} fetching prices for {len(symbol_list)} symbols")

        prices = []
        for symbol in symbol_list:
            try:
                # Get latest data
                df = await market_service.get_latest_data(symbol=symbol, timeframe="1h", periods=24)

                if not df.empty:
                    latest = df.iloc[-1]
                    first = df.iloc[0]

                    price_change = latest["close"] - first["open"]
                    price_change_percent = (price_change / first["open"]) * 100

                    prices.append(
                        PriceInfo(
                            symbol=symbol,
                            price=latest["close"],
                            price_change=price_change,
                            price_change_percent=price_change_percent,
                            high_24h=df["high"].max(),
                            low_24h=df["low"].min(),
                            volume_24h=df["volume"].sum(),
                            timestamp=latest["timestamp"],
                        )
                    )
            except Exception as e:
                logger.warning(f"Error fetching price for {symbol}: {e!s}")
                continue

        return prices

    except Exception as e:
        logger.error(f"Error fetching multiple prices: {e!s}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch prices",
        ) from None


# ============================================================================
# SYMBOL ENDPOINTS
# ============================================================================


@router.get("/symbols", response_model=SymbolListResponse)
async def get_available_symbols(
    current_user: User = Depends(get_current_user),
    market_service: MarketDataService = Depends(get_market_data_service),
) -> SymbolListResponse:
    """
    Get list of available trading symbols.

    Returns all trading pairs available on the exchange.
    """
    try:
        logger.info(f"User {current_user.username} fetching available symbols")

        symbols = await market_service.get_available_symbols()

        return SymbolListResponse(
            success=True,
            message=f"Found {len(symbols)} available symbols",
            data=symbols,
        )

    except Exception as e:
        logger.error(f"Error fetching symbols: {e!s}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch symbols",
        ) from None


@router.get("/symbols/{symbol}", response_model=SymbolInfo)
async def get_symbol_info(
    symbol: str = Path(..., description=SYMBOL_DESCRIPTION),
    current_user: User = Depends(get_current_user),
    market_service: MarketDataService = Depends(get_market_data_service),
) -> SymbolInfo:
    """
    Get detailed information about a specific symbol.

    - **symbol**: Trading symbol

    Returns trading rules, precision, and limits for the symbol.
    """
    try:
        logger.info(f"User {current_user.username} fetching info for {symbol}")

        # Validate symbol
        is_valid = await market_service.validate_symbol(symbol)
        if not is_valid:
            raise ValidationError(f"Invalid symbol: {symbol}")

        info = await market_service.get_symbol_info(symbol)

        return SymbolInfo(**info)

    except ValidationError as e:
        logger.warning(f"Validation error: {e!s}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from None
    except Exception as e:
        logger.error(f"Error fetching symbol info: {e!s}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch symbol information",
        ) from None


# ============================================================================
# TECHNICAL INDICATORS ENDPOINTS
# ============================================================================


@router.get("/indicators/{symbol}", response_model=TechnicalIndicatorsResponse)
async def get_technical_indicators(
    symbol: str = Path(..., description=SYMBOL_DESCRIPTION),
    interval: str = Query("1h", description="Timeframe"),
    periods: int = Query(100, ge=50, le=500, description="Number of periods for calculation"),
    current_user: User = Depends(get_current_user),
    market_service: MarketDataService = Depends(get_market_data_service),
) -> TechnicalIndicatorsResponse:
    """
    Calculate technical indicators for a symbol.

    - **symbol**: Trading symbol
    - **interval**: Timeframe
    - **periods**: Number of periods to use for calculations

    Returns moving averages, RSI, Bollinger Bands, and other indicators.
    """
    try:
        logger.info(f"User {current_user.username} calculating indicators for {symbol} ({interval})")

        # Validate symbol
        is_valid = await market_service.validate_symbol(symbol)
        if not is_valid:
            raise ValidationError(f"Invalid symbol: {symbol}")

        # Get market data
        df = await market_service.get_latest_data(symbol=symbol, timeframe=interval, periods=periods)

        if df.empty or len(df) < 50:
            raise ValidationError("Insufficient data for indicator calculation")

        # Calculate indicators (placeholder - would use real TA library)
        indicators = TechnicalIndicators(
            symbol=symbol,
            interval=interval,
            timestamp=df.iloc[-1]["timestamp"],
            sma_20=float(df["close"].rolling(20).mean().iloc[-1]),
            sma_50=float(df["close"].rolling(50).mean().iloc[-1]),
            ema_20=float(df["close"].ewm(span=20).mean().iloc[-1]),
            ema_50=float(df["close"].ewm(span=50).mean().iloc[-1]),
            rsi_14=50.0,  # Placeholder
            bb_upper=float(df["close"].rolling(20).mean().iloc[-1] + 2 * df["close"].rolling(20).std().iloc[-1]),
            bb_middle=float(df["close"].rolling(20).mean().iloc[-1]),
            bb_lower=float(df["close"].rolling(20).mean().iloc[-1] - 2 * df["close"].rolling(20).std().iloc[-1]),
            macd=0.0,  # Placeholder
            macd_signal=0.0,  # Placeholder
            macd_histogram=0.0,  # Placeholder
        )

        return TechnicalIndicatorsResponse(
            success=True,
            message=f"Calculated indicators for {symbol}",
            data=indicators,
        )

    except ValidationError as e:
        logger.warning(f"Validation error: {e!s}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from None
    except Exception as e:
        logger.error(f"Error calculating indicators: {e!s}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to calculate technical indicators",
        ) from None


# ============================================================================
# MARKET SUMMARY ENDPOINT
# ============================================================================


@router.get("/summary", response_model=MarketSummaryResponse)
async def get_market_summary(
    current_user: User = Depends(get_current_user),
    market_service: MarketDataService = Depends(get_market_data_service),
) -> MarketSummaryResponse:
    """
    Get overall market summary with top movers and trending pairs.

    Returns market overview including gainers, losers, and volume leaders.
    """
    try:
        logger.info(f"User {current_user.username} fetching market summary")

        # Get available symbols (limited for demo)
        symbols = await market_service.get_available_symbols()
        top_symbols = symbols[:20]  # Limit to top 20 for demo

        pairs = []
        for symbol in top_symbols:
            try:
                df = await market_service.get_latest_data(symbol=symbol, timeframe="1h", periods=24)
                if not df.empty:
                    latest = df.iloc[-1]
                    first = df.iloc[0]
                    change = ((latest["close"] - first["open"]) / first["open"]) * 100

                    pairs.append(
                        TradingPair(
                            symbol=symbol,
                            base_asset=symbol[:-4],  # Simplified
                            quote_asset=symbol[-4:],
                            current_price=latest["close"],
                            volume_24h=df["volume"].sum(),
                            change_24h=latest["close"] - first["open"],
                            change_percent_24h=change,
                            is_active=True,
                        )
                    )
            except Exception:  # noqa: S112
                continue

        # Sort for gainers and losers
        pairs_sorted = sorted(pairs, key=lambda x: x.change_percent_24h, reverse=True)
        summary = MarketSummary(
            timestamp=datetime.now(UTC),
            total_pairs=len(symbols),
            total_volume_24h=sum(p.volume_24h for p in pairs),
            top_gainers=pairs_sorted[:5],
            top_losers=pairs_sorted[-5:],
            most_active=sorted(pairs, key=lambda x: x.volume_24h, reverse=True)[:5],
        )

        return MarketSummaryResponse(success=True, message="Market summary", data=summary)

    except Exception as e:
        logger.error(f"Error fetching market summary: {e!s}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch market summary",
        ) from None
