"""Bootstrap deterministic development artifacts for the signal API."""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

from src.config.config_loader import load_config
from src.data.storage import write_dataset


FEATURE_COLUMNS = [
    "open",
    "high",
    "low",
    "close",
    "volume",
    "return_1",
    "return_3",
    "return_6",
    "volatility_20",
    "sma_20",
    "sma_50",
    "ema_12",
    "ema_26",
    "rsi_14",
    "macd",
    "macd_signal",
    "macd_hist",
    "bb_upper",
    "bb_lower",
    "bb_width",
    "volume_sma_20",
]


def build_feature_frame(symbol: str, rows: int = 240) -> pd.DataFrame:
    rng = np.random.default_rng(42 if symbol.upper() == "BTCUSDT" else 84)
    now = datetime.now(UTC).replace(minute=0, second=0, microsecond=0)
    timestamps = [now - timedelta(hours=rows - index - 1) for index in range(rows)]
    base = 65000.0 if symbol.upper() == "BTCUSDT" else 0.055
    trend = np.linspace(-0.025, 0.025, rows)
    wave = np.sin(np.linspace(0, 10, rows)) * 0.012
    noise = rng.normal(0, 0.002, rows)
    close = base * (1 + trend + wave + noise)
    open_ = close * (1 + rng.normal(0, 0.001, rows))
    high = np.maximum(open_, close) * 1.002
    low = np.minimum(open_, close) * 0.998
    volume = rng.uniform(50, 250, rows)

    frame = pd.DataFrame(
        {
            "symbol": symbol.upper(),
            "interval": "1h",
            "open_time": timestamps,
            "open": open_,
            "high": high,
            "low": low,
            "close": close,
            "volume": volume,
        }
    )
    frame["return_1"] = frame["close"].pct_change(1).fillna(0)
    frame["return_3"] = frame["close"].pct_change(3).fillna(0)
    frame["return_6"] = frame["close"].pct_change(6).fillna(0)
    frame["volatility_20"] = frame["return_1"].rolling(20).std().fillna(0)
    frame["sma_20"] = frame["close"].rolling(20).mean().bfill()
    frame["sma_50"] = frame["close"].rolling(50).mean().bfill()
    frame["ema_12"] = frame["close"].ewm(span=12, adjust=False).mean()
    frame["ema_26"] = frame["close"].ewm(span=26, adjust=False).mean()
    delta = frame["close"].diff().fillna(0)
    gains = delta.clip(lower=0).rolling(14).mean().bfill()
    losses = (-delta.clip(upper=0)).rolling(14).mean().bfill().replace(0, 1e-9)
    frame["rsi_14"] = 100 - (100 / (1 + gains / losses))
    frame["macd"] = frame["ema_12"] - frame["ema_26"]
    frame["macd_signal"] = frame["macd"].ewm(span=9, adjust=False).mean()
    frame["macd_hist"] = frame["macd"] - frame["macd_signal"]
    rolling_std = frame["close"].rolling(20).std().bfill()
    frame["bb_upper"] = frame["sma_20"] + 2 * rolling_std
    frame["bb_lower"] = frame["sma_20"] - 2 * rolling_std
    frame["bb_width"] = (frame["bb_upper"] - frame["bb_lower"]) / frame["sma_20"]
    frame["volume_sma_20"] = frame["volume"].rolling(20).mean().bfill()
    frame["target"] = np.select(
        [frame["return_3"] > 0.002, frame["return_3"] < -0.002],
        ["BUY", "SELL"],
        default="HOLD",
    )
    return frame


def ensure_random_forest_artifact(settings, *, force: bool = False) -> Path:
    import joblib
    from sklearn.ensemble import RandomForestClassifier
    from sklearn.preprocessing import StandardScaler

    destination = Path(settings.mlops.model_registry_path) / "random_forest" / "best"
    required = [
        destination / "model.joblib",
        destination / "scaler.joblib",
        destination / "feature_columns.json",
    ]
    if not force and all(path.exists() for path in required):
        return destination

    frame = build_feature_frame("BTCUSDT")
    scaler = StandardScaler()
    x_train = scaler.fit_transform(frame[FEATURE_COLUMNS])
    y_train = frame["target"]
    model = RandomForestClassifier(
        n_estimators=60,
        max_depth=6,
        min_samples_leaf=4,
        class_weight="balanced",
        random_state=42,
    )
    model.fit(x_train, y_train)

    destination.mkdir(parents=True, exist_ok=True)
    joblib.dump(model, destination / "model.joblib")
    joblib.dump(scaler, destination / "scaler.joblib")
    (destination / "feature_columns.json").write_text(json.dumps(FEATURE_COLUMNS, indent=2), encoding="utf-8")
    (destination / "metrics.json").write_text(
        json.dumps({"bootstrap": True, "rows": len(frame), "created_at": datetime.now(UTC).isoformat()}, indent=2),
        encoding="utf-8",
    )
    return destination


def ensure_feature_datasets(settings, *, force: bool = False) -> list[Path]:
    paths: list[Path] = []
    for symbol in settings.data.symbols:
        base_path = Path(settings.data.paths.processed) / symbol.upper() / f"1h_features"
        primary_path = base_path.with_suffix(f".{settings.data.formats.processed_primary}")
        if force or not primary_path.exists():
            frame = build_feature_frame(symbol.upper())
            paths.extend(
                write_dataset(
                    frame,
                    base_path,
                    settings.data.formats.processed_primary,
                    settings.data.formats.processed_exports,
                    metadata={"bootstrap": True, "symbol": symbol.upper(), "interval": "1h"},
                )
            )
        else:
            paths.append(primary_path)
    return paths


def main() -> None:
    parser = argparse.ArgumentParser(description="Create deterministic dev ML artifacts.")
    parser.add_argument("--config", default="config.yaml")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    settings = load_config(args.config)
    artifact = ensure_random_forest_artifact(settings, force=args.force)
    datasets = ensure_feature_datasets(settings, force=args.force)
    print(f"random_forest artifact ready: {artifact}")
    for path in datasets:
        print(f"feature dataset ready: {path}")


if __name__ == "__main__":
    main()
