"""
ASGI configuration for the Crypto Trading Bot.

This module provides ASGI application configuration for production deployment
with proper middleware, logging, and error handling.

ASGI (Asynchronous Server Gateway Interface) is the modern standard for
Python async web apps and supports WebSockets, HTTP/2, and streaming.

For deployment with:
- Gunicorn: gunicorn config.asgi:application -k uvicorn.workers.UvicornWorker
- Uvicorn: uvicorn config.asgi:application --host 0.0.0.0 --port 8000
- Docker: CMD ["uvicorn", "config.asgi:application", "--host", "0.0.0.0", "--port", "8000"]
"""

import logging
import os

# Set up logging before importing our modules
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")

logger = logging.getLogger(__name__)

# Import our main application (after logging setup)
from main import app as fastapi_app  # noqa: E402

# ASGI application instance
application = fastapi_app

# Production-specific configurations
if os.getenv("ENVIRONMENT", "development").lower() == "production":
    logger.info("🚀 Configuring application for PRODUCTION environment")

    # Disable docs in production
    application.openapi_url = None
    application.docs_url = None
    application.redoc_url = None

    logger.info("📝 API documentation disabled for production")

else:
    logger.info("🔧 Configuring application for DEVELOPMENT environment")


# Health check for load balancers
@application.get("/health/ready")
async def readiness_check():
    """
    Readiness probe for Kubernetes/Docker health checks.
    Returns 200 if the application is ready to serve traffic.
    """
    from shared.database import get_database_info

    try:
        db_info = get_database_info()
        if db_info.get("is_connected", False):
            return {
                "status": "ready",
                "database": "connected",
                "timestamp": "2025-07-29T03:30:00Z",
            }
        else:
            return {
                "status": "not_ready",
                "database": "disconnected",
                "error": db_info.get("error"),
            }, 503
    except Exception as e:
        logger.error(f"Readiness check failed: {e}")
        return {"status": "not_ready", "error": str(e)}, 503


@application.get("/health/live")
async def liveness_check():
    """
    Liveness probe for Kubernetes/Docker health checks.
    Returns 200 if the application process is alive.
    """
    return {"status": "alive", "timestamp": "2025-07-29T03:30:00Z"}


# Export for different deployment scenarios
def get_asgi_application():
    """
    Get the ASGI application instance.

    Used by deployment tools that need to import the application.
    """
    return application


# For debugging ASGI configuration
if __name__ == "__main__":
    logger.info("⚠️  This file should not be run directly.")
    logger.info("✅ Use: uvicorn config.asgi:application --reload")
    logger.info("📚 Or check main.py for development server")
