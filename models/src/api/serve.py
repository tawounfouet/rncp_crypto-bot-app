"""Run the FastAPI app with uvicorn."""

from __future__ import annotations

from src.config.config_loader import load_config


def main() -> None:
    import uvicorn

    settings = load_config("config.yaml")
    uvicorn.run(
        "src.api.main:app",
        host=settings.api.host,
        port=settings.api.port,
        reload=settings.api.reload,
    )


if __name__ == "__main__":
    main()
