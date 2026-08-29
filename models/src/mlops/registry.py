"""Local model registry helpers."""

from __future__ import annotations

import fcntl
import os
import shutil
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from src.utils.logger import get_logger

logger = get_logger(__name__)


@contextmanager
def _locked(lock_path: Path) -> Iterator[None]:
    """Verrou de fichier bloquant (fcntl.flock) -- serialise les appels concurrents."""
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with open(lock_path, "w") as handle:
        fcntl.flock(handle, fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(handle, fcntl.LOCK_UN)


def register_best_model(artifact_dir: str | Path, registry_root: str | Path, model_name: str) -> Path:
    """Copy an artifact directory to the local registry best pointer.

    destination (artifacts/registry/<model_name>/best) n'est PAS qualifie par paire --
    un seul emplacement pour tous les symboles d'un meme model_name (limite connue du
    chemin A, cf. commentaires ml_pipeline.py). Le DAG entraine desormais plusieurs
    paires en parallele pour un meme model_name (ex. train_random_forest_BTCUSDC et
    train_random_forest_ETHUSDC) : sans serialisation, deux appels concurrents sur la
    meme destination se marchent dessus (l'un efface/renomme pendant que l'autre copie)
    -- 500 Internal Server Error observe en conditions reelles le 2026-08-29 (une
    ecriture atomique seule, testee d'abord, ne suffit pas : elle deplace juste la
    fenetre de course entre deux "os.replace" concurrents). Un verrou de fichier par
    model_name serialise les appels : le dernier arrive "gagne" (meme semantique
    qu'avant), juste sans jamais crasher.
    """
    source = Path(artifact_dir)
    destination = Path(registry_root) / model_name / "best"
    destination.parent.mkdir(parents=True, exist_ok=True)
    lock_path = destination.parent / ".best.lock"
    logger.info("registry update start model=%s source=%s destination=%s", model_name, source, destination)
    with _locked(lock_path):
        tmp_destination = destination.parent / f".best-{uuid.uuid4().hex}"
        shutil.copytree(source, tmp_destination)
        if destination.exists():
            shutil.rmtree(destination)
        os.replace(tmp_destination, destination)
    logger.info("registry update complete model=%s destination=%s", model_name, destination)
    return destination
