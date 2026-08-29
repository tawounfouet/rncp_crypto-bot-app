"""Train the XGBoost baseline."""

from __future__ import annotations

import argparse
from pathlib import Path

import mlflow.sklearn
import numpy as np
from sklearn.base import BaseEstimator, ClassifierMixin
from sklearn.pipeline import Pipeline

from src.config.config_loader import load_config
from src.data.storage import read_dataset
from src.mlops.model_card import write_model_card
from src.mlops.registry import register_best_model
from src.mlops.tracking import new_run_id, start_run
from src.models.xgboost import save_xgboost_artifacts, train_xgboost
from src.utils.logger import get_logger


logger = get_logger(__name__)


class _StringLabelXGBoost(BaseEstimator, ClassifierMixin):
    """Enveloppe un XGBClassifier entraine sur des labels entiers pour que predict()
    renvoie directement les labels texte ("BUY"/"SELL"/"HOLD").

    XGBoost est entraine ici sur des labels entiers (settings.label_to_id, cf.
    src/models/xgboost.py), contrairement a RandomForestClassifier qui est entraine
    directement sur les labels texte. Mais predict_registered_bot_model() (chemin B,
    MLflow Model Registry, interroge par bots/) appelle model.predict(frame) et attend
    directement "BUY"/"SELL"/"HOLD" -- sans cette enveloppe il recevrait un entier brut
    (0/1/2) et rejetterait la prediction comme signal non supporte. Chemin A
    (xgboost.py / predict_xgboost_signal, registre local + backend) n'est pas concerne :
    cette classe n'est utilisee que pour ce qui est enregistre dans MLflow ci-dessous.

    Herite de BaseEstimator/ClassifierMixin (plutot que du duck-typing) : sklearn >= 1.6
    exige que toute etape d'un Pipeline implemente __sklearn_tags__, fourni par
    BaseEstimator.
    """

    def __init__(self, estimator=None, id_to_label: dict[int, str] | None = None) -> None:
        # Deroge a la convention sklearn (__init__ ne devrait pas calculer d'attribut
        # derive) : cette classe n'existe que pour envelopper un estimateur deja entraine
        # assemble post-hoc (fit() ci-dessous n'est jamais reellement appele en usage
        # normal), donc classes_ doit exister des la construction -- sklearn.check_is_fitted
        # (invoque par Pipeline.predict) detecte un estimateur "entraine" en cherchant un
        # attribut suffixe "_" dans self.__dict__, ce qu'une @property ne fournit pas.
        self.estimator = estimator
        self.id_to_label = id_to_label
        if estimator is not None and id_to_label is not None:
            self.classes_ = np.array([id_to_label[i] for i in estimator.classes_])

    def fit(self, x, y=None):
        # No-op : l'estimateur sous-jacent est deja entraine (cf. train_xgboost() plus haut).
        # Necessaire uniquement pour satisfaire sklearn.pipeline.Pipeline, qui verifie que
        # chaque etape expose fit() (jamais appele ici, le Pipeline est assemble post-hoc).
        return self

    def predict(self, x):
        return np.array([self.id_to_label[int(prediction)] for prediction in self.estimator.predict(x)])

    def predict_proba(self, x):
        return self.estimator.predict_proba(x)


def train_from_processed_dataset(
    path: str | Path, config_path: str = "config.yaml", *, symbol: str, interval: str = "1h"
) -> Path:
    """Train XGBoost from a processed dataset path and return artifact directory.

    Enregistre aussi le couple scaler+modele comme un seul sklearn.Pipeline dans le
    MLflow Model Registry, sous un nom qualifie par paire ET timeframe (ex.
    "xgboost_btcusdc_1h") -- cf. train_random_forest.py pour le detail du pourquoi (le
    modele attend des features mises a l'echelle, pas les features brutes transmises par
    predict_registered_bot_model()).
    """
    settings = load_config(config_path)
    logger.info(
        "train_xgboost job start dataset=%s config=%s symbol=%s interval=%s", path, config_path, symbol, interval
    )
    data = read_dataset(path)
    run_id = new_run_id(settings)
    logger.info("train_xgboost run created run_id=%s rows=%s", run_id, len(data))
    result = train_xgboost(data, settings)
    artifact_dir = Path(settings.data.paths.artifacts) / "xgboost" / run_id
    save_xgboost_artifacts(result, artifact_dir)
    write_model_card(
        artifact_dir,
        model_name="xgboost",
        run_id=run_id,
        metrics=result["metrics"],
        dataset_summary={"rows": len(data), "source": str(path), "symbol": symbol.upper(), "interval": interval},
    )
    registered_model_name = f"xgboost_{symbol.lower()}_{interval}"
    with start_run(settings, "xgboost", run_id=run_id, symbol=symbol, interval=interval) as run:
        run.log_params(settings.models.xgboost.model_dump())
        run.log_metrics(result["metrics"])
        run.log_artifacts(artifact_dir)
        decoding_model = _StringLabelXGBoost(result["model"], settings.id_to_label)
        pipeline = Pipeline([("scaler", result["scaler"]), ("model", decoding_model)])
        mlflow.sklearn.log_model(
            pipeline,
            "model",
            registered_model_name=registered_model_name,
            # skops (defaut mlflow.sklearn) refuse XGBClassifier comme type "non fiable" --
            # cloudpickle serialise n'importe quel objet Python sans liste d'autorisation a
            # maintenir a la main.
            serialization_format=mlflow.sklearn.SERIALIZATION_FORMAT_CLOUDPICKLE,
        )
        logger.info("train_xgboost registered in MLflow Model Registry name=%s", registered_model_name)
    if settings.mlops.register_best_model:
        registry_path = register_best_model(artifact_dir, settings.mlops.model_registry_path, "xgboost")
        logger.info("train_xgboost registry updated path=%s", registry_path)
    logger.info("train_xgboost job complete artifact_dir=%s metrics=%s", artifact_dir, result["metrics"])
    return artifact_dir


def main() -> None:
    parser = argparse.ArgumentParser(description="Train XGBoost baseline.")
    parser.add_argument("--config", default="config.yaml")
    parser.add_argument("--dataset", required=True)
    parser.add_argument("--symbol", required=True)
    parser.add_argument("--interval", default="1h")
    args = parser.parse_args()
    train_from_processed_dataset(args.dataset, args.config, symbol=args.symbol, interval=args.interval)


if __name__ == "__main__":
    main()
