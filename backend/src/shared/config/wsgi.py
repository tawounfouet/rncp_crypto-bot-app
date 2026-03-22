"""
WSGI configuration for legacy compatibility.

⚠️  WARNING: FastAPI uses ASGI, not WSGI!
    This file is provided for legacy compatibility only.

    Use config/asgi.py instead for FastAPI applications.

WSGI (Web Server Gateway Interface) is the traditional Python web standard
but doesn't support async features that FastAPI relies on.

If you absolutely need WSGI compatibility, consider using:
- a2wsgi: Adapter to run ASGI apps on WSGI servers
- But you'll lose async benefits, WebSockets, etc.
"""

import logging

logger = logging.getLogger(__name__)


def application(environ, start_response):
    """
    WSGI application function.

    ⚠️  This is a fallback that returns an error message.
        FastAPI requires ASGI, not WSGI.
    """

    logger.error("❌ WSGI called but FastAPI requires ASGI!")

    status = "501 Not Implemented"
    response_headers = [("Content-type", "application/json"), ("Content-Length", "150")]

    start_response(status, response_headers)

    error_response = """{
    "error": "WSGI_NOT_SUPPORTED",
    "message": "FastAPI requires ASGI, not WSGI. Use config/asgi.py instead.",
    "solution": "uvicorn config.asgi:application"
}"""

    return [error_response.encode("utf-8")]


# Alternative: ASGI-to-WSGI adapter (if really needed)
def create_wsgi_adapter():
    """
    Create a WSGI adapter for FastAPI (NOT RECOMMENDED).

    This loses all async benefits of FastAPI.
    Only use if you absolutely must deploy on WSGI-only infrastructure.
    """
    try:
        from a2wsgi import ASGIMiddleware
        from config.asgi import application as asgi_app

        logger.warning("🔄 Creating ASGI-to-WSGI adapter (performance will be degraded)")
        return ASGIMiddleware(asgi_app)

    except ImportError:
        logger.error("❌ a2wsgi not installed. Install with: pip install a2wsgi")
        return application  # Return error function


if __name__ == "__main__":
    logger.warning("⚠️  WSGI is not recommended for FastAPI!")
    logger.info("✅ Use instead: uvicorn config.asgi:application")
    logger.info("📚 Check config/asgi.py for proper ASGI configuration")
