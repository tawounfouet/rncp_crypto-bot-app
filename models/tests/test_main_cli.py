"""Tests de cablage du CLI centralise (src/main.py) vers les fonctions d'entrainement.

Couvre une regression reelle : train_rf_command/train_xgboost_command appelaient
train_from_processed_dataset() sans le parametre symbol devenu obligatoire, ce qui
aurait fait planter `python -m src.main train-rf` (jamais detecte par les tests
d'entrainement existants, qui n'exercent que la couche du dessous). Mocke les fonctions
d'entrainement : ce sont des tests de cablage argparse -> appel, pas d'entrainement reel.
"""

from __future__ import annotations

import argparse
from unittest.mock import patch

from src.main import train_rf_command, train_xgboost_command


def test_train_rf_command_passes_symbol_argument():
    args = argparse.Namespace(dataset="data/processed/BTCUSDC/1h_features.parquet", config="config.yaml", symbol="BTCUSDC")
    with patch("src.main.train_from_processed_dataset") as mock_train:
        mock_train.return_value = "artifacts/random_forest/run1"
        train_rf_command(args)
    mock_train.assert_called_once_with(args.dataset, args.config, symbol="BTCUSDC")


def test_train_rf_command_resolves_default_symbol_when_omitted():
    args = argparse.Namespace(dataset="data/processed/BTCUSDC/1h_features.parquet", config="config.yaml", symbol=None)
    with (
        patch("src.main.train_from_processed_dataset") as mock_train,
        patch("src.main.list_configured_symbols", return_value=["BTCUSDC", "ETHUSDC"]),
    ):
        mock_train.return_value = "artifacts/random_forest/run1"
        train_rf_command(args)
    mock_train.assert_called_once_with(args.dataset, args.config, symbol="BTCUSDC")


def test_train_xgboost_command_passes_symbol_argument():
    args = argparse.Namespace(dataset="data/processed/ETHUSDC/1h_features.parquet", config="config.yaml", symbol="ETHUSDC")
    with patch("src.main.train_xgboost_from_processed_dataset") as mock_train:
        mock_train.return_value = "artifacts/xgboost/run1"
        train_xgboost_command(args)
    mock_train.assert_called_once_with(args.dataset, args.config, symbol="ETHUSDC")
