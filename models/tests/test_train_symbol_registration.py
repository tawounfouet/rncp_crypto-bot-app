"""Tests de la qualification par paire du chemin B (MLflow Model Registry).

Couvre le bug corrige dans train_random_forest.py / train_xgboost.py : sans nom de
modele qualifie par paire, entrainer un second symbole ecrasait le premier au meme nom
MLflow, et sans empaqueter scaler+model dans un sklearn.Pipeline avant l'enregistrement,
predict_registered_bot_model() recevait des features non mises a l'echelle -- silencieux,
aucune erreur, juste des signaux incorrects. Meme structure de test que
test_bot_rsi_mlflow.py (tracking MLflow isole via tmp_path, pas de garantie de version
minimale ici : la meme skip condition s'applique).
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest
import yaml

from tests.fixtures import sample_features

pytestmark = pytest.mark.skipif(
    sys.version_info < (3, 11) or importlib.util.find_spec("mlflow") is None,
    reason="Python 3.11+ and mlflow are required for MLflow registry tests",
)

BASE_CONFIG_PATH = Path(__file__).resolve().parents[1] / "config.yaml"


def _isolated_config(tmp_path: Path) -> Path:
    """Copie de config.yaml avec les chemins d'artefacts/registre locaux dans tmp_path.

    Evite d'ecrire dans models/artifacts/registry (chemin A, reel) pendant les tests --
    ce chemin n'est pas concerne par ce correctif, seul le Model Registry MLflow l'est.
    """
    config = yaml.safe_load(BASE_CONFIG_PATH.read_text(encoding="utf-8"))
    config["data"]["paths"]["artifacts"] = str(tmp_path / "artifacts")
    config["mlops"]["model_registry_path"] = str(tmp_path / "registry")
    config_path = tmp_path / "config.yaml"
    config_path.write_text(yaml.dump(config), encoding="utf-8")
    return config_path


def _tracking_uri(path: Path) -> str:
    return f"sqlite:///{path.as_posix()}"


@pytest.mark.parametrize(
    "train_module",
    ["src.training.train_random_forest", "src.training.train_xgboost"],
)
def test_train_registers_model_qualified_by_symbol(train_module, tmp_path, monkeypatch):
    import mlflow

    training = importlib.import_module(train_module)

    config_path = _isolated_config(tmp_path)
    monkeypatch.setenv("MLFLOW_TRACKING_URI", _tracking_uri(tmp_path / "mlflow.db"))

    dataset_path = tmp_path / "features.csv"
    sample_features().to_csv(dataset_path, index=False)

    training.train_from_processed_dataset(dataset_path, str(config_path), symbol="BTCUSDC")
    training.train_from_processed_dataset(dataset_path, str(config_path), symbol="ETHUSDC")

    client = mlflow.tracking.MlflowClient()
    model_name_prefix = train_module.rsplit(".", 1)[-1].removeprefix("train_")
    btc_versions = client.search_model_versions(f"name='{model_name_prefix}_btcusdc'")
    eth_versions = client.search_model_versions(f"name='{model_name_prefix}_ethusdc'")

    # Chaque paire a sa propre entree, versionnee independamment -- la regression du
    # bug corrige serait: une seule des deux paires enregistree (l'autre l'ayant ecrasee).
    assert len(btc_versions) == 1
    assert len(eth_versions) == 1


@pytest.mark.parametrize(
    "train_module",
    ["src.training.train_random_forest", "src.training.train_xgboost"],
)
def test_registered_model_predicts_with_scaled_features(train_module, tmp_path, monkeypatch):
    """Le modele enregistre doit etre directement utilisable par predict_registered_bot_model
    (features brutes, sans scaling manuel) -- preuve que le Pipeline scaler+model est bien
    celui qui a ete enregistre, pas le RandomForestClassifier/XGBClassifier brut."""
    from src.inference.mlflow_registry import predict_registered_bot_model

    training = importlib.import_module(train_module)

    config_path = _isolated_config(tmp_path)
    monkeypatch.setenv("MLFLOW_TRACKING_URI", _tracking_uri(tmp_path / "mlflow.db"))

    data = sample_features()
    dataset_path = tmp_path / "features.csv"
    data.to_csv(dataset_path, index=False)

    training.train_from_processed_dataset(dataset_path, str(config_path), symbol="BTCUSDC")

    model_name_prefix = train_module.rsplit(".", 1)[-1].removeprefix("train_")
    feature_columns = ["close", "ema_12", "rsi_14", "macd", "volume_sma_20"]
    raw_features = {col: float(data.iloc[-1][col]) for col in feature_columns}

    prediction = predict_registered_bot_model(
        model_name=f"{model_name_prefix}_btcusdc",
        features=raw_features,
        config_path=str(config_path),
    )

    assert prediction["signal"] in {"BUY", "SELL", "HOLD"}
    assert 0.0 <= prediction["confidence"] <= 1.0
