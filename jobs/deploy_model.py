"""Deploy the best trained model to MinIO for backend inference.

Copies ``model.joblib``, ``scaler.joblib`` and ``feature_columns.json``
from the local model registry to MinIO so the backend API can load them.

Expected local registry layout (produced by ``register_best_model()``):
    artifacts/registry/<model_name>/best/{model,scaler}.joblib + feature_columns.json

MinIO target layout:
    models/<model_name>/best/{model,scaler}.joblib + feature_columns.json

Usage:
    python deploy_model.py                          # deploy all enabled models
    python deploy_model.py --model random_forest    # deploy a single model
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

from minio.error import S3Error

from utils.connectors.minio import MinioClient
from utils.logging import configure_logging

logger = logging.getLogger(__name__)

ARTIFACTS_TO_DEPLOY = ["model.joblib", "scaler.joblib", "feature_columns.json"]
REGISTRY_ROOT = Path("artifacts/registry")


def deploy_model(model_name: str, registry_root: Path = REGISTRY_ROOT) -> bool:
    """Upload the best version of *model_name* to MinIO.

    Returns:
        ``True`` on success, ``False`` if no best model was found.
    """
    source_dir = registry_root / model_name / "best"
    if not source_dir.exists():
        logger.warning("No best model found at %s", source_dir)
        return False

    client = MinioClient()
    bucket = client.default_bucket
    prefix = f"models/{model_name}/best"
    logger.info("Deploying model=%s from=%s → s3://%s/%s", model_name, source_dir, bucket, prefix)

    for filename in ARTIFACTS_TO_DEPLOY:
        src = source_dir / filename
        if not src.exists():
            logger.warning("Artifact missing, skipping: %s", src)
            continue
        dst_key = f"{prefix}/{filename}"
        ok = client.upload_file(str(src), dst_key, bucket=bucket)
        if not ok:
            logger.error("Failed to upload %s → %s", filename, dst_key)
            return False
        logger.info("Uploaded %s → %s (%d bytes)", filename, dst_key, src.stat().st_size)

    return True


def main() -> None:
    configure_logging(name="deploy_model", level="INFO")

    parser = argparse.ArgumentParser(description="Deploy trained model to MinIO")
    parser.add_argument(
        "--model", default=None,
        help="Model name to deploy (default: deploy all enabled models)",
    )
    parser.add_argument("--registry", default=str(REGISTRY_ROOT), help="Path to model registry root")
    args = parser.parse_args()

    registry_root = Path(args.registry)
    models_to_deploy = [args.model] if args.model else _detect_models(registry_root)

    success = True
    for model_name in models_to_deploy:
        ok = deploy_model(model_name, registry_root)
        if not ok:
            success = False
            logger.error("Deployment failed for model=%s", model_name)
        else:
            logger.info("Deployment complete for model=%s", model_name)

    sys.exit(0 if success else 1)


def _detect_models(registry_root: Path) -> list[str]:
    """Auto-detect model directories in the registry."""
    if not registry_root.exists():
        return []
    return sorted(
        entry.name for entry in registry_root.iterdir()
        if entry.is_dir() and (entry / "best").exists()
    )


if __name__ == "__main__":
    main()
