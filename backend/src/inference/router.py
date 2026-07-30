from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException

from inference.live_features import build_live_feature_frame
from inference.schemas import ModelInfoResponse, PredictLiveRequest, PredictRequest, PredictResponse
from inference.service import InferenceError, InferenceService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/inference", tags=["inference"])

_service: InferenceService | None = None


def get_service() -> InferenceService:
    global _service
    if _service is None:
        _service = InferenceService()
    return _service


@router.post("/predict", response_model=PredictResponse)
def predict(payload: PredictRequest):
    """Run inference on a pre-computed feature vector.

    The ``features`` dict must contain **all** columns listed in the model's
    ``feature_columns.json`` (request ``GET /inference/model`` to list them).
    """
    svc = get_service()
    try:
        result = svc.predict(payload.features)
    except InferenceError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except KeyError as exc:
        raise HTTPException(
            status_code=400,
            detail=f"Missing feature column: {exc}",
        ) from exc

    return PredictResponse(
        symbol=payload.symbol.upper(),
        interval=payload.interval,
        model_name=svc.model_name,
        model_version=svc.model_version,
        **result,
    )


@router.get("/model", response_model=ModelInfoResponse)
def model_info():
    """Return metadata about the deployed model."""
    svc = get_service()
    try:
        columns = svc.feature_columns
        loaded = True
    except InferenceError as exc:
        columns = []
        loaded = False
        logger.warning("Model info requested but model not loaded: %s", exc)

    return ModelInfoResponse(
        model_name=svc.model_name,
        model_version=svc.model_version,
        feature_columns=columns,
        artifact_path=str(svc.cache_dir),
        loaded=loaded,
    )


@router.post("/predict-live", response_model=PredictResponse)
def predict_live(payload: PredictLiveRequest):
    svc = get_service()
    try:
        df = build_live_feature_frame(payload.symbol, payload.interval)
        last_row = df.iloc[-1]
        features = {col: last_row[col] for col in svc.feature_columns}
        result = svc.predict(features)

    except Exception as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    return PredictResponse(
        symbol=payload.symbol.upper(),
        interval=payload.interval,
        model_name=svc.model_name,
        model_version=svc.model_version,
        **result,
    )
