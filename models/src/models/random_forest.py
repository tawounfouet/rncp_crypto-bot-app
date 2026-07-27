"""Random Forest baseline training and inference."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from src.config.dependencies import require_dependency
from src.config.settings import AppSettings
from src.utils.logger import get_logger, log_model_save
from src.utils.visualization import plot_confusion_matrix, plot_feature_importance


logger = get_logger(__name__)

EXCLUDED_FEATURE_COLUMNS = {
    "symbol",
    "interval",
    "open_time",
    "close_time",
    "source",
    "target",
    "future_return",
    "price_inverted",  # always False for BTCUSDT, 0% importance
}


def get_feature_columns(data: pd.DataFrame) -> list[str]:
    """Return numeric feature columns excluding labels and metadata."""
    return [
        column
        for column in data.columns
        if column not in EXCLUDED_FEATURE_COLUMNS and pd.api.types.is_numeric_dtype(data[column])
    ]


def train_random_forest(data: pd.DataFrame, settings: AppSettings):
    """Train a RandomForestClassifier and return model metadata."""
    require_dependency("sklearn", "Run `pip install -r requirements.txt` before training Random Forest.")
    require_dependency("joblib", "Run `pip install -r requirements.txt` before saving Random Forest artifacts.")

    from sklearn.ensemble import RandomForestClassifier
    from sklearn.metrics import accuracy_score, classification_report, f1_score, precision_score, recall_score
    from sklearn.preprocessing import StandardScaler

    feature_columns = get_feature_columns(data)
    if not feature_columns:
        raise ValueError("No numeric feature columns available for training")
    logger.info(
        "random_forest train start rows=%s columns=%s feature_count=%s target_distribution=%s",
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
        "random_forest split complete train_rows=%s validation_rows=%s test_rows=%s",
        len(train),
        val_end - train_end,
        len(test),
    )

    scaler = StandardScaler()
    x_train = scaler.fit_transform(train[feature_columns])
    y_train = train["target"]
    x_test = scaler.transform(test[feature_columns])
    y_test = test["target"]
    logger.info("random_forest scaling complete x_train_shape=%s x_test_shape=%s", x_train.shape, x_test.shape)

    rf_cfg = settings.models.random_forest
    logger.info(
        "random_forest fit start n_estimators=%s max_depth=%s min_samples_leaf=%s class_weight=%s",
        rf_cfg.n_estimators,
        rf_cfg.max_depth,
        rf_cfg.min_samples_leaf,
        rf_cfg.class_weight,
    )
    model = RandomForestClassifier(
        n_estimators=rf_cfg.n_estimators,
        max_depth=rf_cfg.max_depth,
        min_samples_leaf=rf_cfg.min_samples_leaf,
        class_weight=rf_cfg.class_weight,
        n_jobs=rf_cfg.n_jobs,
        random_state=rf_cfg.random_state,
    )
    model.fit(x_train, y_train)
    logger.info("random_forest fit complete")
    y_pred = model.predict(x_test)
    label_names = [settings.id_to_label[i] for i in sorted(settings.id_to_label)]
    metrics = {
        "accuracy": float(accuracy_score(y_test, y_pred)),
        "precision_macro": float(precision_score(y_test, y_pred, average="macro", zero_division=0)),
        "recall_macro": float(recall_score(y_test, y_pred, average="macro", zero_division=0)),
        "f1_macro": float(f1_score(y_test, y_pred, average="macro", zero_division=0)),
    }
    logger.info("random_forest evaluation complete metrics=%s", metrics)

    report = classification_report(y_test, y_pred, labels=label_names, output_dict=True, zero_division=0)
    for label in label_names:
        if label in report:
            logger.info(
                "random_forest class_metrics label=%s precision=%.4f recall=%.4f f1=%.4f support=%d",
                label,
                report[label]["precision"],
                report[label]["recall"],
                report[label]["f1-score"],
                int(report[label]["support"]),
            )

    if len(data) >= 5000:
        from sklearn.model_selection import TimeSeriesSplit, cross_validate
        from sklearn.pipeline import Pipeline

        X_all = data.sort_values("open_time")[feature_columns].to_numpy()
        y_all = data.sort_values("open_time")["target"].to_numpy()
        pipeline = Pipeline(
            [
                ("scaler", StandardScaler()),
                (
                    "rf",
                    RandomForestClassifier(
                        n_estimators=rf_cfg.n_estimators,
                        max_depth=rf_cfg.max_depth,
                        min_samples_leaf=rf_cfg.min_samples_leaf,
                        class_weight=rf_cfg.class_weight,
                        n_jobs=rf_cfg.n_jobs,
                        random_state=rf_cfg.random_state,
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
        logger.info(
            "random_forest cv f1_macro mean=%.4f std=%.4f",
            metrics["cv_f1_macro_mean"],
            metrics["cv_f1_macro_std"],
        )
    else:
        logger.info(
            "random_forest cv skipped rows=%s (need >= 5000)",
            len(data),
        )

    from src.backtesting.engine import BacktestConfig, run_backtest

    bt_result = run_backtest(
        prices=test["close"].reset_index(drop=True),
        signals=list(y_pred),
        config=BacktestConfig(min_hold_bars=3),
    )
    metrics.update({f"bt_{k}": v for k, v in bt_result.to_dict().items()})
    logger.info("random_forest backtest complete bt_metrics=%s", bt_result.to_dict())

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
        "y_test": y_test.map(settings.label_to_id).tolist(),
        "y_pred": [int(settings.label_to_id[label]) for label in y_pred],
        "labels": [settings.id_to_label[index] for index in sorted(settings.id_to_label)],
    }


def save_random_forest_artifacts(result: dict, output_dir: str | Path) -> None:
    """Persist Random Forest model, scaler and feature list."""
    require_dependency("joblib", "Run `pip install -r requirements.txt` before saving Random Forest artifacts.")
    import json

    import joblib

    destination = Path(output_dir)
    destination.mkdir(parents=True, exist_ok=True)
    logger.info("random_forest artifact save start destination=%s", destination)
    joblib.dump(result["model"], destination / "model.joblib")
    joblib.dump(result["scaler"], destination / "scaler.joblib")
    (destination / "feature_columns.json").write_text(json.dumps(result["feature_columns"], indent=2), encoding="utf-8")
    (destination / "metrics.json").write_text(json.dumps(result["metrics"], indent=2), encoding="utf-8")
    plot_confusion_matrix(
        result["y_test"],
        result["y_pred"],
        result["labels"],
        destination / "confusion_matrix.png",
        title="Random Forest confusion matrix",
    )
    feature_names, importances = zip(*result["feature_importance"])
    (destination / "feature_importance.json").write_text(
        json.dumps([{"feature": f, "importance": i} for f, i in result["feature_importance"]], indent=2),
        encoding="utf-8",
    )
    plot_feature_importance(
        feature_names,
        importances,
        destination / "feature_importance.png",
        title="Random Forest — feature importance (Gini)",
    )
    log_model_save("random_forest", destination / "model.joblib")
    logger.info("random_forest artifact save complete destination=%s", destination)
