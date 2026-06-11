"""Degenerate baseline classifiers used as performance floor references.

Always-HOLD sets the accuracy floor on imbalanced datasets.
UniformRandom sets the f1_macro floor.
Any trained model must beat both baselines to be considered useful.
"""

from __future__ import annotations

import numpy as np
from sklearn.metrics import accuracy_score, classification_report, f1_score, precision_score, recall_score

from src.utils.logger import get_logger


logger = get_logger(__name__)


class AlwaysHoldClassifier:
    """Predicts HOLD for every input. Accuracy floor on imbalanced datasets."""

    def __init__(self, hold_label: str = "HOLD") -> None:
        self.hold_label = hold_label

    def predict(self, X: np.ndarray) -> np.ndarray:
        return np.full(len(X), fill_value=self.hold_label)


class UniformRandomClassifier:
    """Predicts uniformly at random among three classes. f1_macro floor."""

    def __init__(self, labels: list[str], random_state: int = 42) -> None:
        self.labels = labels
        self.rng = np.random.default_rng(random_state)

    def predict(self, X: np.ndarray) -> np.ndarray:
        return self.rng.choice(self.labels, size=len(X))


def evaluate_baseline(
    name: str,
    y_true: np.ndarray,
    y_pred: np.ndarray,
    label_names: list[str],
) -> dict:
    """Compute and log standard metrics for a baseline predictor."""
    metrics = {
        "accuracy": float(accuracy_score(y_true, y_pred)),
        "precision_macro": float(precision_score(y_true, y_pred, average="macro", zero_division=0)),
        "recall_macro": float(recall_score(y_true, y_pred, average="macro", zero_division=0)),
        "f1_macro": float(f1_score(y_true, y_pred, average="macro", zero_division=0)),
    }
    logger.info("%s evaluation complete metrics=%s", name, metrics)

    report = classification_report(y_true, y_pred, labels=label_names, output_dict=True, zero_division=0)
    for label in label_names:
        if label in report:
            logger.info(
                "%s class_metrics label=%s precision=%.4f recall=%.4f f1=%.4f support=%d",
                name,
                label,
                report[label]["precision"],
                report[label]["recall"],
                report[label]["f1-score"],
                int(report[label]["support"]),
            )
    return metrics
