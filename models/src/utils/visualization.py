"""Model visualization helpers for local MVP artifacts."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path
from typing import Sequence

import numpy as np

from src.config.dependencies import require_dependency
from src.utils.logger import get_logger


logger = get_logger(__name__)


def _prepare_matplotlib():
    require_dependency("matplotlib", "Run `pip install -r requirements.txt` before exporting plots.")
    cache_dir = Path(tempfile.gettempdir()) / "cryptobot-matplotlib"
    cache_dir.mkdir(parents=True, exist_ok=True)
    os.environ.setdefault("MPLCONFIGDIR", str(cache_dir))
    os.environ.setdefault("XDG_CACHE_HOME", str(cache_dir))
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    return plt


def plot_training_history(history: Sequence[dict], save_path: str | Path, title: str = "Training history") -> Path:
    """Plot train and validation losses over epochs."""
    output_path = Path(save_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    plt = _prepare_matplotlib()

    epochs = [row["epoch"] for row in history]
    train_losses = [row["train_loss"] for row in history]
    validation_losses = [row["validation_loss"] for row in history]

    plt.figure(figsize=(10, 5))
    plt.plot(epochs, train_losses, label="Train loss", linewidth=2)
    plt.plot(epochs, validation_losses, label="Validation loss", linewidth=2)
    plt.xlabel("Epoch")
    plt.ylabel("Loss")
    plt.title(title)
    plt.legend()
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig(output_path, dpi=160, bbox_inches="tight")
    plt.close()
    logger.info("training history plot saved to %s", output_path)
    return output_path


def plot_confusion_matrix(
    y_true: Sequence[int],
    y_pred: Sequence[int],
    labels: Sequence[str],
    save_path: str | Path,
    title: str = "Confusion matrix",
) -> Path:
    """Plot a classification confusion matrix."""
    require_dependency("sklearn", "Run `pip install -r requirements.txt` before exporting confusion matrices.")
    from sklearn.metrics import confusion_matrix

    output_path = Path(save_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    plt = _prepare_matplotlib()

    matrix = confusion_matrix(y_true, y_pred, labels=list(range(len(labels))))
    figure, axis = plt.subplots(figsize=(6, 5))
    image = axis.imshow(matrix, interpolation="nearest", cmap="Blues")
    axis.figure.colorbar(image, ax=axis)
    axis.set(
        xticks=np.arange(len(labels)),
        yticks=np.arange(len(labels)),
        xticklabels=labels,
        yticklabels=labels,
        ylabel="True label",
        xlabel="Predicted label",
        title=title,
    )

    threshold = matrix.max() / 2 if matrix.size and matrix.max() else 0
    for row_index in range(matrix.shape[0]):
        for column_index in range(matrix.shape[1]):
            axis.text(
                column_index,
                row_index,
                format(matrix[row_index, column_index], "d"),
                ha="center",
                va="center",
                color="white" if matrix[row_index, column_index] > threshold else "black",
            )

    figure.tight_layout()
    figure.savefig(output_path, dpi=160, bbox_inches="tight")
    plt.close(figure)
    logger.info("confusion matrix saved to %s", output_path)
    return output_path


def plot_feature_importance(
    feature_names: Sequence[str],
    importances: Sequence[float],
    save_path: str | Path,
    top_n: int = 20,
    title: str = "Feature importance",
) -> Path:
    """Horizontal bar chart of the top_n most important features (Gini)."""
    output_path = Path(save_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    plt = _prepare_matplotlib()

    pairs = sorted(zip(feature_names, importances), key=lambda x: x[1], reverse=True)[:top_n]
    names, values = zip(*pairs)

    fig, ax = plt.subplots(figsize=(10, max(4, len(names) * 0.4)))
    bars = ax.barh(range(len(names)), list(reversed(values)), color="steelblue")
    ax.set_yticks(range(len(names)))
    ax.set_yticklabels(list(reversed(names)), fontsize=9)
    ax.set_xlabel("Importance (Gini)")
    ax.set_title(title)
    ax.bar_label(bars, fmt="%.4f", padding=3, fontsize=8)
    ax.set_xlim(0, max(values) * 1.15)
    fig.tight_layout()
    fig.savefig(output_path, dpi=160, bbox_inches="tight")
    plt.close(fig)
    logger.info("feature importance plot saved to %s", output_path)
    return output_path
