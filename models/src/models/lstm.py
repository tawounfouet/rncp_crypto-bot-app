"""PyTorch LSTM classifier for BUY/SELL/HOLD labels."""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from src.config.dependencies import require_dependency
from src.config.settings import AppSettings
from src.models.random_forest import get_feature_columns
from src.utils.logger import get_logger, log_model_save, log_training_epoch
from src.utils.visualization import plot_confusion_matrix, plot_training_history


logger = get_logger(__name__)


def ensure_torch_available() -> None:
    require_dependency("torch", "Run `pip install -r requirements.txt` before training LSTM.")


def create_lstm_classifier(
    input_size: int,
    hidden_size: int,
    num_layers: int,
    dropout: float,
    output_size: int,
    bidirectional: bool = False,
):
    """Create an LSTM classifier class instance when torch is available."""
    ensure_torch_available()
    import torch

    class LSTMClassifier(torch.nn.Module):
        def __init__(self) -> None:
            super().__init__()
            self.lstm = torch.nn.LSTM(
                input_size=input_size,
                hidden_size=hidden_size,
                num_layers=num_layers,
                dropout=dropout if num_layers > 1 else 0.0,
                batch_first=True,
                bidirectional=bidirectional,
            )
            direction_factor = 2 if bidirectional else 1
            self.classifier = torch.nn.Linear(hidden_size * direction_factor, output_size)

        def forward(self, x):
            output, _ = self.lstm(x)
            last_step = output[:, -1, :]
            return self.classifier(last_step)

    return LSTMClassifier()


def create_sequences(features: np.ndarray, labels: np.ndarray, sequence_length: int) -> tuple[np.ndarray, np.ndarray]:
    """Convert row-wise features into LSTM windows."""
    if len(features) < sequence_length:
        return (
            np.empty((0, sequence_length, features.shape[1]), dtype=np.float32),
            np.empty((0,), dtype=np.int64),
        )
    x_sequences = []
    y_sequences = []
    for end_index in range(sequence_length - 1, len(features)):
        start_index = end_index - sequence_length + 1
        x_sequences.append(features[start_index : end_index + 1])
        y_sequences.append(labels[end_index])
    return np.asarray(x_sequences, dtype=np.float32), np.asarray(y_sequences, dtype=np.int64)


def temporal_split(data: pd.DataFrame, settings: AppSettings) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Split a processed dataset without temporal leakage."""
    ordered = data.sort_values("open_time").reset_index(drop=True)
    train_end = int(len(ordered) * settings.split.train_ratio)
    val_end = train_end + int(len(ordered) * settings.split.validation_ratio)
    train = ordered.iloc[:train_end]
    validation = ordered.iloc[train_end:val_end]
    test = ordered.iloc[val_end:]
    if train.empty or validation.empty or test.empty:
        raise ValueError("Not enough rows to create temporal train/validation/test split")
    return train, validation, test


def prepare_lstm_datasets(data: pd.DataFrame, settings: AppSettings) -> dict[str, Any]:
    """Prepare scaled temporal sequences for LSTM training."""
    require_dependency("sklearn", "Run `pip install -r requirements.txt` before preparing LSTM datasets.")
    from sklearn.preprocessing import StandardScaler

    feature_columns = get_feature_columns(data)
    if not feature_columns:
        raise ValueError("No numeric feature columns available for LSTM training")
    logger.info(
        "lstm prepare start rows=%s columns=%s feature_count=%s target_distribution=%s",
        len(data),
        len(data.columns),
        len(feature_columns),
        data["target"].value_counts().to_dict(),
    )

    label_to_id = settings.label_to_id
    unknown_labels = set(data["target"]) - set(label_to_id)
    if unknown_labels:
        raise ValueError(f"Unknown target labels for LSTM training: {sorted(unknown_labels)}")

    train, validation, test = temporal_split(data, settings)
    logger.info(
        "lstm temporal split complete train_rows=%s validation_rows=%s test_rows=%s",
        len(train),
        len(validation),
        len(test),
    )
    scaler = StandardScaler()
    train_features = scaler.fit_transform(train[feature_columns])
    validation_features = scaler.transform(validation[feature_columns])
    test_features = scaler.transform(test[feature_columns])

    train_labels = train["target"].map(label_to_id).to_numpy()
    validation_labels = validation["target"].map(label_to_id).to_numpy()
    test_labels = test["target"].map(label_to_id).to_numpy()
    sequence_length = settings.models.lstm.sequence_length

    x_train, y_train = create_sequences(train_features, train_labels, sequence_length)
    x_validation, y_validation = create_sequences(validation_features, validation_labels, sequence_length)
    x_test, y_test = create_sequences(test_features, test_labels, sequence_length)
    if len(x_train) == 0 or len(x_validation) == 0 or len(x_test) == 0:
        raise ValueError(
            f"Not enough rows to create LSTM sequences. Need at least {sequence_length} rows in each split."
        )
    logger.info(
        "lstm sequence preparation complete sequence_length=%s train_sequences=%s validation_sequences=%s test_sequences=%s feature_count=%s",
        sequence_length,
        len(x_train),
        len(x_validation),
        len(x_test),
        len(feature_columns),
    )

    # Close prices aligned with test sequences: each prediction corresponds to
    # the price at the end of its sequence window.
    test_prices = test["close"].reset_index(drop=True).iloc[sequence_length - 1 :].reset_index(drop=True)

    return {
        "feature_columns": feature_columns,
        "scaler": scaler,
        "x_train": x_train,
        "y_train": y_train,
        "x_validation": x_validation,
        "y_validation": y_validation,
        "x_test": x_test,
        "y_test": y_test,
        "test_prices": test_prices,
        "split_rows": {
            "train": int(len(train)),
            "validation": int(len(validation)),
            "test": int(len(test)),
        },
    }


def train_lstm(data: pd.DataFrame, settings: AppSettings) -> dict[str, Any]:
    """Train a compact LSTM classifier and return model metadata."""
    ensure_torch_available()
    require_dependency("sklearn", "Run `pip install -r requirements.txt` before training LSTM.")
    require_dependency("joblib", "Run `pip install -r requirements.txt` before saving LSTM artifacts.")

    import torch
    from sklearn.metrics import accuracy_score, classification_report, f1_score, precision_score, recall_score
    from torch.utils.data import DataLoader, TensorDataset

    torch.manual_seed(settings.project.random_state)
    np.random.seed(settings.project.random_state)

    prepared = prepare_lstm_datasets(data, settings)
    lstm_cfg = settings.models.lstm
    training_cfg = settings.training
    logger.info(
        "lstm train start hidden_size=%s num_layers=%s dropout=%s bidirectional=%s batch_size=%s epochs=%s lr=%s",
        lstm_cfg.hidden_size,
        lstm_cfg.num_layers,
        lstm_cfg.dropout,
        lstm_cfg.bidirectional,
        training_cfg.batch_size,
        training_cfg.epochs,
        training_cfg.learning_rate,
    )

    model = create_lstm_classifier(
        input_size=len(prepared["feature_columns"]),
        hidden_size=lstm_cfg.hidden_size,
        num_layers=lstm_cfg.num_layers,
        dropout=lstm_cfg.dropout,
        output_size=lstm_cfg.output_size,
        bidirectional=lstm_cfg.bidirectional,
    )
    optimizer = torch.optim.AdamW(
        model.parameters(),
        lr=training_cfg.learning_rate,
        weight_decay=training_cfg.weight_decay,
    )

    class_weights_tensor: torch.Tensor | None = None
    if training_cfg.use_class_weights:
        from sklearn.utils.class_weight import compute_class_weight

        classes = np.unique(prepared["y_train"])
        weights = compute_class_weight("balanced", classes=classes, y=prepared["y_train"])
        class_weights_tensor = torch.tensor(weights, dtype=torch.float32)
        logger.info("lstm class weights computed classes=%s weights=%s", classes.tolist(), weights.tolist())

    if training_cfg.loss == "focal":
        from src.models.losses import FocalLoss

        criterion = FocalLoss(gamma=training_cfg.focal_gamma, weight=class_weights_tensor)
        logger.info(
            "lstm loss=focal gamma=%s use_class_weights=%s", training_cfg.focal_gamma, training_cfg.use_class_weights
        )
    else:
        criterion = torch.nn.CrossEntropyLoss(weight=class_weights_tensor)
        logger.info("lstm loss=cross_entropy use_class_weights=%s", training_cfg.use_class_weights)

    train_dataset = TensorDataset(
        torch.tensor(prepared["x_train"], dtype=torch.float32),
        torch.tensor(prepared["y_train"], dtype=torch.long),
    )
    train_loader = DataLoader(train_dataset, batch_size=training_cfg.batch_size, shuffle=False)
    x_validation = torch.tensor(prepared["x_validation"], dtype=torch.float32)
    y_validation = torch.tensor(prepared["y_validation"], dtype=torch.long)

    best_state = copy.deepcopy(model.state_dict())
    best_validation_loss = float("inf")
    epochs_without_improvement = 0
    history = []

    for epoch in range(1, training_cfg.epochs + 1):
        model.train()
        train_losses = []
        for x_batch, y_batch in train_loader:
            optimizer.zero_grad()
            logits = model(x_batch)
            loss = criterion(logits, y_batch)
            loss.backward()
            if training_cfg.gradient_clipping.enabled:
                torch.nn.utils.clip_grad_norm_(model.parameters(), training_cfg.gradient_clipping.max_norm)
            optimizer.step()
            train_losses.append(float(loss.detach().item()))

        model.eval()
        with torch.no_grad():
            validation_logits = model(x_validation)
            validation_loss = float(criterion(validation_logits, y_validation).item())
        train_loss = float(np.mean(train_losses)) if train_losses else 0.0
        history.append({"epoch": epoch, "train_loss": train_loss, "validation_loss": validation_loss})
        log_training_epoch("lstm", epoch, train_loss, validation_loss)

        if validation_loss < best_validation_loss - training_cfg.early_stopping.min_delta:
            best_validation_loss = validation_loss
            best_state = copy.deepcopy(model.state_dict())
            epochs_without_improvement = 0
            logger.info("lstm validation improved epoch=%s best_validation_loss=%.6f", epoch, best_validation_loss)
        else:
            epochs_without_improvement += 1
            if epochs_without_improvement >= training_cfg.early_stopping.patience:
                logger.info(
                    "lstm early stopping epoch=%s patience=%s best_validation_loss=%.6f",
                    epoch,
                    training_cfg.early_stopping.patience,
                    best_validation_loss,
                )
                break

    if training_cfg.early_stopping.restore_best_weights:
        model.load_state_dict(best_state)
        logger.info("lstm restored best weights best_validation_loss=%.6f", best_validation_loss)

    x_test = torch.tensor(prepared["x_test"], dtype=torch.float32)
    y_test = prepared["y_test"]
    model.eval()
    with torch.no_grad():
        predictions = model(x_test).argmax(dim=1).numpy()

    hold_id = settings.label_to_id["HOLD"]
    active_mask = predictions != hold_id
    if active_mask.sum() > 0:
        directional_accuracy = float(accuracy_score(y_test[active_mask], predictions[active_mask]))
    else:
        directional_accuracy = float("nan")

    metrics = {
        "accuracy": float(accuracy_score(y_test, predictions)),
        "precision_macro": float(precision_score(y_test, predictions, average="macro", zero_division=0)),
        "recall_macro": float(recall_score(y_test, predictions, average="macro", zero_division=0)),
        "f1_macro": float(f1_score(y_test, predictions, average="macro", zero_division=0)),
        "directional_accuracy": directional_accuracy,
        "best_validation_loss": float(best_validation_loss),
        "epochs_trained": len(history),
    }
    logger.info("lstm evaluation complete metrics=%s", metrics)

    label_names = [settings.id_to_label[i] for i in sorted(settings.id_to_label)]
    report = classification_report(
        y_test,
        predictions,
        labels=list(settings.label_to_id.values()),
        target_names=label_names,
        output_dict=True,
        zero_division=0,
    )
    for label in label_names:
        if label in report:
            logger.info(
                "lstm class_metrics label=%s precision=%.4f recall=%.4f f1=%.4f support=%d",
                label,
                report[label]["precision"],
                report[label]["recall"],
                report[label]["f1-score"],
                int(report[label]["support"]),
            )
    if active_mask.sum() == 0:
        logger.warning("lstm degenerate: 0 active signals (BUY/SELL) in test predictions — model predicts only HOLD")

    from src.backtesting.engine import BacktestConfig, run_backtest

    pred_labels = [settings.id_to_label[int(p)] for p in predictions]
    bt_result = run_backtest(
        prices=prepared["test_prices"],
        signals=pred_labels,
        config=BacktestConfig(min_hold_bars=3),
    )
    metrics.update({f"bt_{k}": v for k, v in bt_result.to_dict().items()})
    logger.info("lstm backtest complete bt_metrics=%s", bt_result.to_dict())

    return {
        "model": model,
        "model_config": {
            "input_size": len(prepared["feature_columns"]),
            "hidden_size": lstm_cfg.hidden_size,
            "num_layers": lstm_cfg.num_layers,
            "dropout": lstm_cfg.dropout,
            "bidirectional": lstm_cfg.bidirectional,
            "output_size": lstm_cfg.output_size,
            "sequence_length": lstm_cfg.sequence_length,
        },
        "scaler": prepared["scaler"],
        "feature_columns": prepared["feature_columns"],
        "metrics": metrics,
        "history": history,
        "test_rows": int(len(y_test)),
        "split_rows": prepared["split_rows"],
        "y_test": [int(label) for label in y_test],
        "y_pred": [int(label) for label in predictions],
        "labels": [settings.id_to_label[index] for index in sorted(settings.id_to_label)],
    }


def save_lstm_artifacts(result: dict[str, Any], output_dir: str | Path) -> None:
    """Persist LSTM model state, scaler, feature list and metrics."""
    ensure_torch_available()
    require_dependency("joblib", "Run `pip install -r requirements.txt` before saving LSTM artifacts.")
    import joblib
    import torch

    destination = Path(output_dir)
    destination.mkdir(parents=True, exist_ok=True)
    logger.info("lstm artifact save start destination=%s", destination)
    torch.save(result["model"].state_dict(), destination / "model.pt")
    joblib.dump(result["scaler"], destination / "scaler.joblib")
    (destination / "feature_columns.json").write_text(json.dumps(result["feature_columns"], indent=2), encoding="utf-8")
    (destination / "model_config.json").write_text(json.dumps(result["model_config"], indent=2), encoding="utf-8")
    (destination / "metrics.json").write_text(json.dumps(result["metrics"], indent=2), encoding="utf-8")
    (destination / "training_history.json").write_text(json.dumps(result["history"], indent=2), encoding="utf-8")
    plot_training_history(result["history"], destination / "training_history.png", title="LSTM training history")
    plot_confusion_matrix(
        result["y_test"],
        result["y_pred"],
        result["labels"],
        destination / "confusion_matrix.png",
        title="LSTM confusion matrix",
    )
    log_model_save("lstm", destination / "model.pt")
    logger.info("lstm artifact save complete destination=%s", destination)
