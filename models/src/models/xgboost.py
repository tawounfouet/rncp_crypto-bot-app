"""XGBoost baseline training and inference.

Reuses the exact same artifact layout as the Random Forest baseline
(model.joblib + scaler.joblib + feature_columns.json) so the backend
``InferenceService`` can serve it without changes (joblib serializes
``XGBClassifier`` the same way as a scikit-learn estimator).
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from src.config.dependencies import require_dependency
from src.config.settings import AppSettings
from src.models.random_forest import get_feature_columns
from src.utils.logger import get_logger, log_model_save
from src.utils.visualization import plot_confusion_matrix, plot_feature_importance


logger = get_logger(__name__)


def train_xgboost(data: pd.DataFrame, settings: AppSettings):
    """Train an XGBClassifier and return model metadata."""
    require_dependency("xgboost", "Run `pip install -r requirements.txt` before training XGBoost.")
    require_dependency("joblib", "Run `pip install -r requirements.txt` before saving XGBoost artifacts.")

    from sklearn.metrics import accuracy_score, classification_report, f1_score, precision_score, recall_score
    from sklearn.preprocessing import StandardScaler
    from xgboost import XGBClassifier

    feature_columns = get_feature_columns(data)
    if not feature_columns:
        raise ValueError("No numeric feature columns available for training")
    logger.info(
        "xgboost train start rows=%s columns=%s feature_count=%s target_distribution=%s",
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
        "xgboost split complete train_rows=%s validation_rows=%s test_rows=%s",
        len(train),
        val_end - train_end,
        len(test),
    )

    # XGBoost impose des labels entiers 0..N-1 pour la classification multi-classe
    # (contrairement a RandomForest/MLP qui acceptent des chaines).
    id_to_label = settings.id_to_label
    scaler = StandardScaler()
    x_train = scaler.fit_transform(train[feature_columns])
    y_train = train["target"].map(settings.label_to_id)
    x_test = scaler.transform(test[feature_columns])
    y_test = test["target"].map(settings.label_to_id)
    logger.info("xgboost scaling complete x_train_shape=%s x_test_shape=%s", x_train.shape, x_test.shape)

    xgb_cfg = settings.models.xgboost
    logger.info(
        "xgboost fit start n_estimators=%s max_depth=%s learning_rate=%s subsample=%s colsample_bytree=%s",
        xgb_cfg.n_estimators,
        xgb_cfg.max_depth,
        xgb_cfg.learning_rate,
        xgb_cfg.subsample,
        xgb_cfg.colsample_bytree,
    )
    model = XGBClassifier(
        n_estimators=xgb_cfg.n_estimators,
        max_depth=xgb_cfg.max_depth,
        learning_rate=xgb_cfg.learning_rate,
        subsample=xgb_cfg.subsample,
        colsample_bytree=xgb_cfg.colsample_bytree,
        min_child_weight=xgb_cfg.min_child_weight,
        reg_lambda=xgb_cfg.reg_lambda,
        n_jobs=xgb_cfg.n_jobs,
        random_state=xgb_cfg.random_state,
    )
    model.fit(x_train, y_train)
    logger.info("xgboost fit complete")
    y_pred = model.predict(x_test)
    metrics = {
        "accuracy": float(accuracy_score(y_test, y_pred)),
        "precision_macro": float(precision_score(y_test, y_pred, average="macro", zero_division=0)),
        "recall_macro": float(recall_score(y_test, y_pred, average="macro", zero_division=0)),
        "f1_macro": float(f1_score(y_test, y_pred, average="macro", zero_division=0)),
    }
    logger.info("xgboost evaluation complete metrics=%s", metrics)

    report = classification_report(y_test, y_pred, labels=list(id_to_label), output_dict=True, zero_division=0)
    for label_id in sorted(id_to_label):
        key = str(label_id)
        if key in report:
            logger.info(
                "xgboost class_metrics label=%s precision=%.4f recall=%.4f f1=%.4f support=%d",
                id_to_label[label_id],
                report[key]["precision"],
                report[key]["recall"],
                report[key]["f1-score"],
                int(report[key]["support"]),
            )

    if len(data) >= 5000:
        from sklearn.model_selection import TimeSeriesSplit, cross_validate
        from sklearn.pipeline import Pipeline

        X_all = data.sort_values("open_time")[feature_columns].to_numpy()
        y_all = data.sort_values("open_time")["target"].map(settings.label_to_id).to_numpy()
        pipeline = Pipeline(
            [
                ("scaler", StandardScaler()),
                (
                    "xgb",
                    XGBClassifier(
                        n_estimators=xgb_cfg.n_estimators,
                        max_depth=xgb_cfg.max_depth,
                        learning_rate=xgb_cfg.learning_rate,
                        subsample=xgb_cfg.subsample,
                        colsample_bytree=xgb_cfg.colsample_bytree,
                        min_child_weight=xgb_cfg.min_child_weight,
                        reg_lambda=xgb_cfg.reg_lambda,
                        n_jobs=xgb_cfg.n_jobs,
                        random_state=xgb_cfg.random_state,
                    ),
                ),
            ]
        )
        cv_results = cross_validate(
            pipeline,
            X_all,
            y_all,
            cv=TimeSeriesSplit(n_splits=5),
            scoring={"f1_macro": "f1_macro", "accuracy": "accuracy"},
        )
        metrics["cv_f1_macro_mean"] = float(cv_results["test_f1_macro"].mean())
        metrics["cv_f1_macro_std"] = float(cv_results["test_f1_macro"].std())
        logger.info("xgboost cv f1_macro mean=%.4f std=%.4f", metrics["cv_f1_macro_mean"], metrics["cv_f1_macro_std"])
    else:
        logger.info("xgboost cv skipped rows=%s (need >= 5000)", len(data))

    from src.backtesting.engine import BacktestConfig, run_backtest

    bt_result = run_backtest(
        prices=test["close"].reset_index(drop=True),
        signals=[id_to_label[int(prediction)] for prediction in y_pred],
        config=BacktestConfig(min_hold_bars=3),
    )
    metrics.update({f"bt_{k}": v for k, v in bt_result.to_dict().items()})
    logger.info("xgboost backtest complete bt_metrics=%s", bt_result.to_dict())

    importance_pairs = sorted(
        zip(feature_columns, model.feature_importances_.tolist()),
        key=lambda x: x[1],
        reverse=True,
    )
    return {
        "model": model,
        "scaler": scaler,
        "feature_columns": feature_columns,
        "feature_importance": importance_pairs,
        "metrics": metrics,
        "backtest": bt_result,
        "test_rows": len(test),
        "y_test": y_test.tolist(),
        "y_pred": [int(prediction) for prediction in y_pred],
        "labels": [id_to_label[index] for index in sorted(id_to_label)],
    }


def save_xgboost_artifacts(result: dict, output_dir: str | Path) -> None:
    """Persist XGBoost model, scaler and feature list."""
    require_dependency("joblib", "Run `pip install -r requirements.txt` before saving XGBoost artifacts.")
    import joblib

    destination = Path(output_dir)
    destination.mkdir(parents=True, exist_ok=True)
    logger.info("xgboost artifact save start destination=%s", destination)
    joblib.dump(result["model"], destination / "model.joblib")
    joblib.dump(result["scaler"], destination / "scaler.joblib")
    (destination / "feature_columns.json").write_text(json.dumps(result["feature_columns"], indent=2), encoding="utf-8")
    (destination / "metrics.json").write_text(json.dumps(result["metrics"], indent=2), encoding="utf-8")
    plot_confusion_matrix(
        result["y_test"],
        result["y_pred"],
        result["labels"],
        destination / "confusion_matrix.png",
        title="XGBoost confusion matrix",
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
        title="XGBoost — feature importance (gain)",
    )
    log_model_save("xgboost", destination / "model.joblib")
    logger.info("xgboost artifact save complete destination=%s", destination)
