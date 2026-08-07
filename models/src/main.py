#!/usr/bin/env python
"""Central CLI for the CryptoBot models-training MVP."""

from __future__ import annotations

import argparse
from pathlib import Path

try:
    from dotenv import load_dotenv

    env_path = Path(__file__).resolve().parents[2] / ".env"
    load_dotenv(dotenv_path=env_path)
except ImportError:
    pass

from src.config.config_loader import load_config
from src.features.build import build_symbol_features
from src.training.train_baselines import train_from_processed_dataset as train_baselines_from_processed_dataset
from src.training.train_lstm import train_from_processed_dataset as train_lstm_from_processed_dataset
from src.training.train_mlp import train_from_processed_dataset as train_mlp_from_processed_dataset
from src.training.train_random_forest import train_from_processed_dataset
from src.training.train_xgboost import train_from_processed_dataset as train_xgboost_from_processed_dataset
from src.utils.logger import configure_logging, get_logger
from src.validation.mvp_check import check_mvp


def config_command(args: argparse.Namespace) -> None:
    settings = load_config(args.config)
    print(f"project={settings.project.name}")
    print(f"symbols={','.join(settings.data.symbols)}")
    print(f"interval={settings.data.primary_interval}")
    print(f"mlops={settings.mlops.tracking_backend}:{settings.mlops.tracking_uri}")


def features_command(args: argparse.Namespace) -> None:
    settings = load_config(args.config)
    symbols = args.symbols or settings.data.symbols
    interval = args.interval or settings.data.primary_interval
    for symbol in symbols:
        frame = build_symbol_features(symbol, interval, args.config)
        print(f"features {symbol.upper()} {interval}: {len(frame)} rows")


def train_rf_command(args: argparse.Namespace) -> None:
    artifact_dir = train_from_processed_dataset(args.dataset, args.config)
    print(f"random_forest artifacts: {artifact_dir}")


def train_lstm_command(args: argparse.Namespace) -> None:
    artifact_dir = train_lstm_from_processed_dataset(args.dataset, args.config)
    print(f"lstm artifacts: {artifact_dir}")


def train_mlp_command(args: argparse.Namespace) -> None:
    artifact_dir = train_mlp_from_processed_dataset(args.dataset, args.config)
    print(f"mlp artifacts: {artifact_dir}")


def train_xgboost_command(args: argparse.Namespace) -> None:
    artifact_dir = train_xgboost_from_processed_dataset(args.dataset, args.config)
    print(f"xgboost artifacts: {artifact_dir}")


def train_baselines_command(args: argparse.Namespace) -> None:
    train_baselines_from_processed_dataset(args.dataset, args.config)
    print(f"baselines evaluated on: {args.dataset}")


def check_command(args: argparse.Namespace) -> None:
    statuses = check_mvp(args.config)
    for name, status in statuses.items():
        print(f"{name:<10} {status}")


def api_command(args: argparse.Namespace) -> None:
    import uvicorn

    settings = load_config(args.config)
    uvicorn.run(
        "src.api.main:app",
        host=args.host or settings.api.host,
        port=args.port or settings.api.port,
        reload=args.reload or settings.api.reload,
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="CryptoBot models-training MVP CLI",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--config", default="config.yaml", help="Path to project YAML config")
    subparsers = parser.add_subparsers(dest="command", required=True)

    config_parser = subparsers.add_parser("config", help="Validate and print config summary")
    config_parser.set_defaults(func=config_command)

    features_parser = subparsers.add_parser("features", help="Build processed features")
    features_parser.add_argument("--symbols", nargs="*", help="Symbols to process")
    features_parser.add_argument("--interval", help="Interval to process")
    features_parser.set_defaults(func=features_command)

    train_rf_parser = subparsers.add_parser("train-rf", help="Train Random Forest baseline")
    train_rf_parser.add_argument(
        "--dataset",
        default=str(Path("data/processed/BTCUSDT/1h_features.parquet")),
        help="Processed dataset path",
    )
    train_rf_parser.set_defaults(func=train_rf_command)

    train_lstm_parser = subparsers.add_parser("train-lstm", help="Train LSTM classifier")
    train_lstm_parser.add_argument(
        "--dataset",
        default=str(Path("data/processed/BTCUSDT/1h_features.parquet")),
        help="Processed dataset path",
    )
    train_lstm_parser.set_defaults(func=train_lstm_command)

    train_mlp_parser = subparsers.add_parser("train-mlp", help="Train MLP classifier")
    train_mlp_parser.add_argument(
        "--dataset",
        default=str(Path("data/processed/BTCUSDT/1h_features.parquet")),
        help="Processed dataset path",
    )
    train_mlp_parser.set_defaults(func=train_mlp_command)

    train_xgboost_parser = subparsers.add_parser("train-xgboost", help="Train XGBoost classifier")
    train_xgboost_parser.add_argument(
        "--dataset",
        default=str(Path("data/processed/BTCUSDT/1h_features.parquet")),
        help="Processed dataset path",
    )
    train_xgboost_parser.set_defaults(func=train_xgboost_command)

    train_baselines_parser = subparsers.add_parser(
        "train-baselines", help="Evaluate AlwaysHold and UniformRandom baselines"
    )
    train_baselines_parser.add_argument(
        "--dataset",
        default=str(Path("data/processed/BTCUSDT/1h_features.parquet")),
        help="Processed dataset path",
    )
    train_baselines_parser.set_defaults(func=train_baselines_command)

    api_parser = subparsers.add_parser("api", help="Start FastAPI signal API")
    api_parser.add_argument("--host", help="API host override")
    api_parser.add_argument("--port", type=int, help="API port override")
    api_parser.add_argument("--reload", action="store_true", help="Enable uvicorn reload")
    api_parser.set_defaults(func=api_command)

    check_parser = subparsers.add_parser("check", help="Run MVP readiness check")
    check_parser.set_defaults(func=check_command)

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    settings = load_config(args.config)
    configure_logging(settings)
    get_logger("cli").info("command started: %s", args.command)
    args.func(args)


if __name__ == "__main__":
    main()
