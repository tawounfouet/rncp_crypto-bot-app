"""MLP (Multilayer Perceptron) baseline training and inference.

Reuses the exact same artifact layout as the Random Forest baseline
(model.joblib + scaler.joblib + feature_columns.json) so the backend
``InferenceService`` can serve it without changes.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from src.config.dependencies import require_dependency
from src.config.settings import AppSettings
from src.models.random_forest import get_feature_columns
from src.utils.logger import get_logger, log_model_save
from src.utils.visualization import plot_confusion_matrix, plot_feature_importance


logger = get_logger(__name__)


def train_mlp(data: pd.DataFrame, settings: AppSettings):
    """Train an MLPClassifier and return model metadata."""
    require_dependency("sklearn", "Run `pip install -r requirements.txt` before training MLP.")
    require_dependency("joblib", "Run `pip install -r requirements.txt` before saving MLP artifacts.")

    from sklearn.metrics import accuracy_score, classification_report, f1_score, precision_score, recall_score
    from sklearn.neural_network import MLPClassifier
    from sklearn.preprocessing import StandardScaler

    feature_columns = get_feature_columns(data)
    if not feature_columns:
        raise ValueError("No numeric feature columns available for training")
    logger.info(
        "mlp train start rows=%s columns=%s feature_count=%s target_distribution=%s",
        len(data),
        len(data.columns),
        len(feature_columns),
        data["target"].value_counts().to_dict(),
    )

    ordered = data.sort_values("open_time").reset_index(drop=True)
    train_end = int(len(ordered) * settings.split.train_ratio)
    val_end = train_end + int(len(ordered) * settings.split.validation_ratio)
    train = ordered.iloc[:train_end]
    test = ordered.iloc[val_end:]
    if train.empty or test.empty:
        raise ValueError("Not enough rows to create temporal train/test split")
    logger.info(
        "mlp split complete train_rows=%s validation_rows=%s test_rows=%s", len(train), val_end - train_end, len(test)
    )

    scaler = StandardScaler()
    x_train = scaler.fit_transform(train[feature_columns])
    y_train = train["target"]
    x_test = scaler.transform(test[feature_columns])
    y_test = test["target"]
    logger.info("mlp scaling complete x_train_shape=%s x_test_shape=%s", x_train.shape, x_test.shape)

    mlp_cfg = settings.models.mlp
    logger.info(
        "mlp fit start hidden_layer_sizes=%s activation=%s solver=%s max_iter=%s early_stopping=%s",
        mlp_cfg.hidden_layer_sizes,
        mlp_cfg.activation,
        mlp_cfg.solver,
        mlp_cfg.max_iter,
        mlp_cfg.early_stopping,
    )
    model = MLPClassifier(
        hidden_layer_sizes=mlp_cfg.hidden_layer_sizes,
        activation=mlp_cfg.activation,
        solver=mlp_cfg.solver,
        alpha=mlp_cfg.alpha,
        learning_rate_init=mlp_cfg.learning_rate_init,
        batch_size=mlp_cfg.batch_size,
        max_iter=mlp_cfg.max_iter,
        early_stopping=mlp_cfg.early_stopping,
        random_state=mlp_cfg.random_state,
    )
    model.fit(x_train, y_train)
    logger.info("mlp fit complete n_iter=%s", getattr(model, "n_iter_", None))
    y_pred = model.predict(x_test)
    label_names = [settings.id_to_label[i] for i in sorted(settings.id_to_label)]
    metrics = {
        "accuracy": float(accuracy_score(y_test, y_pred)),
        "precision_macro": float(precision_score(y_test, y_pred, average="macro", zero_division=0)),
        "recall_macro": float(recall_score(y_test, y_pred, average="macro", zero_division=0)),
        "f1_macro": float(f1_score(y_test, y_pred, average="macro", zero_division=0)),
    }
    logger.info("mlp evaluation complete metrics=%s", metrics)

    report = classification_report(y_test, y_pred, labels=label_names, output_dict=True, zero_division=0)
    for label in label_names:
        if label in report:
            logger.info(
                "mlp class_metrics label=%s precision=%.4f recall=%.4f f1=%.4f support=%d",
                label,
                report[label]["precision"],
                report[label]["recall"],
                report[label]["f1-score"],
                int(report[label]["support"]),
            )

    # MLP n'expose pas de feature_importances_ natif : approximation par la norme
    # moyenne des poids de la premiere couche (|W| moyen par feature d'entree),
    # normalisee pour rester comparable au format des autres modeles.
    first_layer_weights = np.asarray(model.coefs_[0], dtype=float)
    per_feature_importance = np.abs(first_layer_weights).mean(axis=1)
    total_importance = float(per_feature_importance.sum())
    if total_importance:
        per_feature_importance = per_feature_importance / total_importance
    importance_pairs = sorted(
        zip(feature_columns, per_feature_importance.tolist()),
        key=lambda x: x[1],
        reverse=True,
    )

    from src.backtesting.engine import BacktestConfig, run_backtest

    bt_result = run_backtest(
        prices=test["close"].reset_index(drop=True),
        signals=list(y_pred),
        config=BacktestConfig(min_hold_bars=3),
    )
    metrics.update({f"bt_{k}": v for k, v in bt_result.to_dict().items()})
    logger.info("mlp backtest complete bt_metrics=%s", bt_result.to_dict())

    return {
        "model": model,
        "scaler": scaler,
        "feature_columns": feature_columns,
        "feature_importance": importance_pairs,
        "metrics": metrics,
        "backtest": bt_result,
        "test_rows": len(test),
        "y_test": y_test.map(settings.label_to_id).tolist(),
        "y_pred": [int(settings.label_to_id[label]) for label in y_pred],
        "labels": [settings.id_to_label[index] for index in sorted(settings.id_to_label)],
    }


def save_mlp_artifacts(result: dict, output_dir: str | Path) -> None:
    """Persist MLP model, scaler and feature list."""
    require_dependency("joblib", "Run `pip install -r requirements.txt` before saving MLP artifacts.")
    import joblib

    destination = Path(output_dir)
    destination.mkdir(parents=True, exist_ok=True)
    logger.info("mlp artifact save start destination=%s", destination)
    joblib.dump(result["model"], destination / "model.joblib")
    joblib.dump(result["scaler"], destination / "scaler.joblib")
    (destination / "feature_columns.json").write_text(json.dumps(result["feature_columns"], indent=2), encoding="utf-8")
    (destination / "metrics.json").write_text(json.dumps(result["metrics"], indent=2), encoding="utf-8")
    plot_confusion_matrix(
        result["y_test"],
        result["y_pred"],
        result["labels"],
        destination / "confusion_matrix.png",
        title="MLP confusion matrix",
    )
    (destination / "feature_importance.json").write_text(
        json.dumps([{"feature": f, "importance": i} for f, i in result["feature_importance"]], indent=2),
        encoding="utf-8",
    )
    feature_names, importances = zip(*result["feature_importance"])
    plot_feature_importance(
        feature_names,
        importances,
        destination / "feature_importance.png",
        title="MLP — feature importance (first-layer weights)",
    )
    log_model_save("mlp", destination / "model.joblib")
    logger.info("mlp artifact save complete destination=%s", destination)
