"""
Crypto Trading Bot - FastAPI Application Entry Point

This is the main application file that configures and starts the FastAPI server
with all the necessary middleware, routes, and database connections.
"""

import logging
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse
from shared.config.constants import ErrorCode

# Configuration imports
from shared.config.settings import get_settings

# Database imports
from shared.database.connection import get_database_info, init_database
from sqlalchemy.exc import SQLAlchemyError

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan manager.

    Handles startup and shutdown events for the FastAPI application.
    """
    # Startup
    logger.info("🚀 Starting Crypto Trading Bot API...")

    try:
        # Initialize database
        if init_database():
            logger.info("✅ Database initialized successfully")

            # Log database info
            db_info = get_database_info()
            logger.info(f"📊 Database: {db_info.get('database_type', 'unknown').upper()}")
            if not db_info.get("error"):
                logger.info(f"🔗 Connection: {'✅ Active' if db_info.get('is_connected') else '❌ Inactive'}")
        else:
            logger.error("❌ Failed to initialize database")

    except Exception as e:
        logger.error(f"💥 Startup error: {e}")
        raise

    logger.info("🎉 Application startup completed successfully!")

    yield

    # Shutdown
    logger.info("🛑 Shutting down Crypto Trading Bot API...")
    logger.info("👋 Application shutdown completed")


# Get application settings
settings = get_settings()

# Create FastAPI application with lifespan
app = FastAPI(
    title=settings.APP_NAME,
    description="Advanced cryptocurrency trading bot with automated strategies",
    version=settings.APP_VERSION,
    docs_url=f"{settings.API_PREFIX}/docs",
    redoc_url=f"{settings.API_PREFIX}/redoc",
    openapi_url=f"{settings.API_PREFIX}/openapi.json",
    lifespan=lifespan,
)

# from shared.database.connection import engine
# from models import Base  # Importez votre Base SQLAlchemy


# @app.on_event("startup")
# async def startup_event():
#     """Créer les tables au démarrage de l'application"""
#     Base.metadata.create_all(bind=engine)
#     print("✅ Tables créées avec succès")

# Add trusted host middleware for security
if not settings.DEBUG:
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=settings.ALLOWED_HOSTS)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)


# Global exception handlers
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Handle request validation errors."""
    logger.warning(f"Validation error on {request.url}: {exc}")
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "error": ErrorCode.VALIDATION_ERROR.value,
            "message": "Request validation failed",
            "details": exc.errors(),
        },
    )


@app.exception_handler(SQLAlchemyError)
async def database_exception_handler(request: Request, exc: SQLAlchemyError):
    """Handle database errors."""
    logger.error(f"Database error on {request.url}: {exc}")
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": ErrorCode.DATABASE_ERROR.value,
            "message": "Database operation failed",
        },
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """Handle all other exceptions."""
    logger.error(f"Unexpected error on {request.url}: {exc}", exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": ErrorCode.INTERNAL_ERROR.value,
            "message": "Internal server error",
        },
    )


# Health check endpoints
@app.get("/health", tags=["Health"])
async def health_check():
    """Basic health check endpoint."""
    return {
        "status": "healthy",
        "service": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "environment": settings.ENVIRONMENT,
    }


@app.get("/health/detailed", tags=["Health"])
async def detailed_health_check():
    """Detailed health check with database status."""
    try:
        db_info = get_database_info()

        health_data = {
            "status": "healthy",
            "service": settings.APP_NAME,
            "version": settings.APP_VERSION,
            "environment": settings.ENVIRONMENT,
            "timestamp": "2025-07-29T03:15:00Z",
            "database": {
                "type": db_info.get("database_type", "unknown"),
                "connected": db_info.get("is_connected", False),
                "error": db_info.get("error"),
            },
            "features": {
                "background_tasks": settings.ENABLE_BACKGROUND_TASKS,
                "websockets": settings.ENABLE_WEBSOCKETS,
                "metrics": settings.ENABLE_METRICS,
            },
        }

        # Determine overall status
        if db_info.get("error") or not db_info.get("is_connected"):
            health_data["status"] = "degraded"

        return health_data

    except Exception as e:
        logger.error(f"Health check error: {e}")
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={
                "status": "unhealthy",
                "service": settings.APP_NAME,
                "error": str(e),
            },
        )


# Root endpoint
@app.get("/", tags=["Root"])
async def read_root():
    """Root endpoint with API information."""
    return {
        "message": f"Welcome to {settings.APP_NAME}",
        "version": settings.APP_VERSION,
        "environment": settings.ENVIRONMENT,
        "docs": f"{settings.API_PREFIX}/docs",
        "health": "/health",
    }


# API prefix route group
@app.get(settings.API_PREFIX, tags=["API"])
async def api_info():
    """API information endpoint."""
    return {
        "api_version": settings.API_VERSION,
        "service": settings.APP_NAME,
        "documentation": f"{settings.API_PREFIX}/docs",
        "endpoints": {
            "health": "/health",
            "detailed_health": "/health/detailed",
            "auth": f"{settings.API_PREFIX}/auth",
            "users": f"{settings.API_PREFIX}/users",
            "strategies": f"{settings.API_PREFIX}/strategies",
            "trading": f"{settings.API_PREFIX}/trading",
            "market": f"{settings.API_PREFIX}/market",
        },
    }


# Router includes (after app configuration)
from auth.router import router as auth_router  # noqa: E402
from auth.users_router import router as users_router  # noqa: E402
from market.router import router as market_router  # noqa: E402
from strategy.router import router as strategies_router  # noqa: E402
from trading.router import router as trading_router  # noqa: E402
from inference.router import router as inference_router  # noqa: E402

# Include authentication and user management routers
app.include_router(auth_router, prefix=settings.API_PREFIX)
app.include_router(users_router, prefix=settings.API_PREFIX)

# Include strategy management router
app.include_router(strategies_router, prefix=settings.API_PREFIX)

# Include trading router
app.include_router(trading_router, prefix=settings.API_PREFIX)

# Include market data router
app.include_router(market_router, prefix=settings.API_PREFIX)

# Include model inference router
app.include_router(inference_router, prefix=settings.API_PREFIX)
# app.include_router(market_router, prefix=f"{settings.API_PREFIX}/market", tags=["Market Data"])


if __name__ == "__main__":
    """
    Run the application with uvicorn when executed directly.
    For production, use: uvicorn main:app --host 0.0.0.0 --port 8000
    """

    logger.info(f"🔧 Starting {settings.APP_NAME} in {settings.ENVIRONMENT} mode")
    logger.info(f"🌐 Server will be available at: http://{settings.HOST}:{settings.PORT}")
    logger.info(f"📚 API Documentation: http://{settings.HOST}:{settings.PORT}{settings.API_PREFIX}/docs")

    uvicorn.run(
        "main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG,
        log_level="info" if settings.DEBUG else "warning",
        access_log=settings.DEBUG,
    )
