"""MVP validation checklist."""

from __future__ import annotations

from pathlib import Path

from src.config.config_loader import load_config

from utils.connectors.minio import MinioClient


def check_mvp(config_path: str = "config.yaml") -> dict[str, str]:
    """Return status for major MVP areas."""
    settings = load_config(config_path)
    statuses = {
        "CONFIG": "ok",
        "DATA": "missing",
        "FEATURES": "missing",
        "RF_MODEL": "missing",
        "LSTM_MODEL": "missing",
        "MLOPS": "missing",
        "API": "ok",
    }
    raw_path = Path(settings.data.paths.raw)
    processed_path = Path(settings.data.paths.processed)
    if raw_path.exists() and any(raw_path.rglob("*.parquet")):
        statuses["DATA"] = "ok"
    else:
        try:
            mc = MinioClient()
            objs = mc.list_objects(prefix="raw/ohlcv/")
            if objs:
                statuses["DATA"] = "ok (MinIO)"
        except Exception:
            pass
    if processed_path.exists() and any(processed_path.rglob("*.parquet")):
        statuses["FEATURES"] = "ok"
    if (Path(settings.mlops.model_registry_path) / "random_forest" / "best").exists():
        statuses["RF_MODEL"] = "ok"
    if (Path(settings.mlops.model_registry_path) / "lstm" / "best").exists():
        statuses["LSTM_MODEL"] = "ok"
    if Path("mlruns").exists():
        statuses["MLOPS"] = "ok"
    return statuses


def main() -> None:
    statuses = check_mvp()
    for name, status in statuses.items():
        print(f"{name:<10} {status}")


if __name__ == "__main__":
    main()
