"""MLOps tracking — MLflow SDK + JSON sidecar.

MLflow logs all runs to the configured tracking URI (SQLite by default).
A JSON sidecar in mlruns/<experiment>/<model>/<run_id>/ is kept for quick
CLI access without starting the MLflow server.
"""

from __future__ import annotations

import json
import math
import os
import secrets
import shutil
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path

import mlflow

from src.config.config_loader import dump_config_snapshot
from src.config.settings import AppSettings
from src.utils.logger import get_logger

logger = get_logger(__name__)


def new_run_id(settings: AppSettings) -> str:
    """Create a timestamp-based run id, unique even for two calls in the same second.

    Le DAG ml_pipeline lance desormais un entrainement par couple (modele, symbole) en
    parallele (ex. train_random_forest_BTCUSDC et train_random_forest_ETHUSDC) : sans le
    suffixe aleatoire, un format seconde-pres (run_id_format, cf. config.yaml) produit le
    MEME run_id pour deux appels concurrents tombant dans la meme seconde -- meme run_dir,
    meme run MLflow, d'ou un IntegrityError (metric_pk) observe en conditions reelles le
    2026-08-29 quand deux entrainements en parallele ecrivaient dans le run MLflow partage.
    """
    timestamp = datetime.now(tz=UTC).strftime(settings.mlops.run_id_format)
    return f"{timestamp}-{secrets.token_hex(3)}"


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
def start_run(
    settings: AppSettings,
    model_name: str,
    run_id: str | None = None,
    symbol: str | None = None,
    interval: str | None = None,
) -> Iterator[MlflowRun]:
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
        if symbol:
            mlflow.set_tag("symbol", symbol.upper())
        if interval:
            mlflow.set_tag("interval", interval)
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
