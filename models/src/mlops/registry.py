"""Local model registry helpers."""

from __future__ import annotations

import shutil
from pathlib import Path

from src.utils.logger import get_logger


logger = get_logger(__name__)


def register_best_model(artifact_dir: str | Path, registry_root: str | Path, model_name: str) -> Path:
    """Copy an artifact directory to the local registry best pointer."""
    source = Path(artifact_dir)
    destination = Path(registry_root) / model_name / "best"
    logger.info("registry update start model=%s source=%s destination=%s", model_name, source, destination)
    if destination.exists():
        shutil.rmtree(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(source, destination)
    logger.info("registry update complete model=%s destination=%s", model_name, destination)
    return destination
