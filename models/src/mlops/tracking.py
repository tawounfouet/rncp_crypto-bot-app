"""MLOps tracking — MLflow SDK + JSON sidecar.

MLflow logs all runs to the configured tracking URI (SQLite by default).
A JSON sidecar in mlruns/<experiment>/<model>/<run_id>/ is kept for quick
CLI access without starting the MLflow server.
"""

from __future__ import annotations

import json
import math
import os
import shutil
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Iterator

import mlflow

from src.config.config_loader import dump_config_snapshot
from src.config.settings import AppSettings
from src.utils.logger import get_logger


logger = get_logger(__name__)


def new_run_id(settings: AppSettings) -> str:
    """Create a timestamp-based run id."""
    return datetime.now(tz=UTC).strftime(settings.mlops.run_id_format)


def _sanitize(value: object) -> object:
    """Replace non-finite floats with None for JSON/MLflow compatibility."""
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


class MlflowRun:
    """Thin wrapper that logs to MLflow + writes JSON sidecars."""

    def __init__(self, run_dir: Path, mlflow_run_id: str) -> None:
        self.run_dir = run_dir
        self.mlflow_run_id = mlflow_run_id
        self.params: dict = {}
        self.metrics: dict = {}

    def log_params(self, params: dict) -> None:
        self.params.update(params)
        clean = {k: str(v) for k, v in params.items()}
        mlflow.log_params(clean)
        path = self.run_dir / "params.json"
        path.write_text(json.dumps(self.params, indent=2, default=str), encoding="utf-8")
        logger.info("mlops params logged path=%s keys=%s", path, sorted(params.keys()))

    def log_metrics(self, metrics: dict) -> None:
        self.metrics.update(metrics)
        finite = {k: v for k, v in metrics.items() if isinstance(v, (int, float)) and math.isfinite(v)}
        if finite:
            mlflow.log_metrics(finite)
        path = self.run_dir / "metrics.json"
        path.write_text(
            json.dumps({k: _sanitize(v) for k, v in self.metrics.items()}, indent=2, default=str),
            encoding="utf-8",
        )
        logger.info("mlops metrics logged path=%s metrics=%s", path, metrics)

    def log_artifacts(self, artifact_dir: str | Path) -> None:
        source = Path(artifact_dir)
        destination = self.run_dir / "artifacts"
        if destination.exists():
            shutil.rmtree(destination)
        if source.exists():
            shutil.copytree(source, destination)
            mlflow.log_artifacts(str(source))
            logger.info("mlops artifacts copied source=%s destination=%s", source, destination)


@contextmanager
def start_run(settings: AppSettings, model_name: str, run_id: str | None = None) -> Iterator[MlflowRun]:
    """Start a tracked MLflow run and write JSON sidecars for CLI access."""
    actual_run_id = run_id or new_run_id(settings)
    run_dir = Path("mlruns") / settings.mlops.experiment_name / model_name / actual_run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    config_snapshot_path = run_dir / "config_snapshot.json"
    config_snapshot_path.write_text(json.dumps(dump_config_snapshot(settings), indent=2, default=str), encoding="utf-8")

    # MLFLOW_TRACKING_URI (defini par docker-compose pour crypto-bot-ml-api, pointe
    # vers le Postgres partage avec mlflow-ui) prime sur le sqlite local de
    # config.yaml quand present -- sinon les runs restent invisibles depuis l'UI
    # web, qui lit exclusivement ce Postgres.
    tracking_uri = os.environ.get("MLFLOW_TRACKING_URI") or settings.mlops.tracking_uri
    mlflow.set_tracking_uri(tracking_uri)
    mlflow.set_experiment(settings.mlops.experiment_name)

    logger.info(
        "mlops run start model=%s run_id=%s run_dir=%s config_snapshot=%s",
        model_name,
        actual_run_id,
        run_dir,
        config_snapshot_path,
    )

    with mlflow.start_run(run_name=f"{model_name}/{actual_run_id}") as active_run:
        mlflow.set_tag("model_name", model_name)
        mlflow.set_tag("run_id", actual_run_id)
        run = MlflowRun(run_dir, active_run.info.run_id)
        try:
            yield run
        finally:
            logger.info(
                "mlops run complete model=%s run_id=%s run_dir=%s",
                model_name,
                actual_run_id,
                run_dir,
            )
