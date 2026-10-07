# Architecture — models/

> Document de référence de la couche **Machine Learning** (entraînement + API `ml-api`). Vue système globale dans [`../ARCHITECTURE.md`](../ARCHITECTURE.md) ; constats dans [`../CODEBASE_ANALYSIS.md`](../CODEBASE_ANALYSIS.md).

---

## 1. Vue d'ensemble

Le package `models/` transforme des cours de marché en datasets versionnés, features, runs d'entraînement traçables et modèles servis par une API `ml-api` (`:8010`) et le registre MLflow (`:5001`). Il est piloté par un **CLI unique** (`src/main.py`) et par Airflow.

```
models/
├── src/
│   ├── main.py            # CLI : config, features, train-*, api, check
│   ├── config/            # config_loader (YAML) + settings (Pydantic)
│   ├── data/              # binance.py (collecte), storage.py (I/O Parquet/CSV/JSONL), validate.py
│   ├── features/          # build.py (features), labels.py (BUY/SELL/HOLD)
│   ├── models/            # random_forest, lstm, mlp, xgboost, baselines, losses
│   ├── training/          # train_random_forest / train_lstm / train_mlp / train_xgboost / train_bot_rsi_reversal / train_baselines
│   ├── mlops/             # registry.py (best model), tracking.py (MLflow), model_card.py, bootstrap_*
│   ├── inference/         # signal.py (prédiction), mlflow_registry.py (modèles par paire)
│   ├── api/               # main.py (FastAPI ml-api), serve.py, schemas.py
│   └── backtesting/       # engine.py (run_backtest)
├── config.yaml            # configuration centrale (données, features, labels, split, modèles)
├── artifacts/registry/    # <model_name>/best/{model,scaler}.joblib + feature_columns.json
├── mlruns/                # backend MLflow local
├── Dockerfile             # image ml-api
├── Dockerfile.mlflow      # image MLflow UI
├── Makefile               # commandes courtes
├── requirements*.txt(.template)
├── docs/
└── tests/                 # 36 tests
```

Métriques : **5 403 lignes / 63 fichiers** Python.

---

## 2. Configuration

- `config.yaml` : source unique des paramètres (`data`, `features`, `labels`, `split`, `preprocessing`, `models`, `training`, `mlops`).
- `src/config/config_loader.py` : `load_config()` lit `config.yaml` (chemin relatif **depuis `models/`**) et retourne un objet typé `AppSettings` ; `dump_config_snapshot()` sérialise.
- `src/config/settings.py` : modèles Pydantic (`ProjectSettings`, `DataSettings`, `FeaturesSettings`, `LabelSettings`, `TrainingSettings`, …) avec validations (`drop_duplicates`, `enforce_ohlc_consistency`, ratios de split…).

Le mapping de symbole `BTCETH` → paire Binance inversée `ETHBTC` est déclaré dans `config.yaml` (`symbol_mappings`, avec `invert_price`).

---

## 3. Pipeline données → features → labels

```
Binance klines (data/binance.py)
   → stockage local Parquet/CSV/JSONL (data/storage.py, sidecar *.meta.json)
   → validation qualité (data/validate.py, drop_duplicates, cohérence OHLC)
   → features OHLCV + indicateurs (features/build.py)
   → labels BUY/SELL/HOLD (features/labels.py)
```

- `data/storage.py` : `read_dataset`, `read_raw_ohlcv_from_minio` (`storage.py:44`), `write_dataset`, `write_json`, et le sidecar de métadonnées (`metadata_path_for`).
- `features/build.py` : `build_symbol_features(...)` ; partage les indicateurs avec `utils/features/indicators.py`.
- Labels : `horizon`, `threshold_mode` (`fixed` / `volatility`) — `config.yaml`.

---

## 4. Entraînement et MLOps

- Modèles : `models/random_forest.py`, `models/lstm.py`, `models/mlp.py`, `models/xgboost.py`, `models/baselines.py` (planchers AlwaysHold / UniformRandom), `models/losses.py`.
- Entraînements : un module par modèle dans `training/`, chacun exposant `train_from_processed_dataset(...)` et un `main()`.
  - Exemple `training/train_random_forest.py` : log du modèle dans MLflow (`mlflow.sklearn.log_model`, `registered_model_name=f"random_forest_{symbol.lower()}_{interval}"`) puis, si activé, `register_best_model(...)` (`train_random_forest.py:53-69`).
- MLOps : `mlops/registry.py` (`register_best_model` avec verrou fichier — `registry.py:30`), `mlops/tracking.py` (MLflow), `mlops/model_card.py`, `mlops/bootstrap_*.py` (artefacts de dev).
- Registre local : `artifacts/registry/<model>/best/{model.joblib, scaler.joblib, feature_columns.json}` — format attendu par `jobs/deploy_model.py`.

---

## 5. Inférence et API

- `inference/signal.py` : `INFERENCE_MODELS = ("random_forest", "mlp", "xgboost")` (`signal.py:53`), `predict_model_signal(...)`, `SignalPrediction`. `inference/mlflow_registry.py` : prédiction des modèles enregistrés par paire (`predict_registered_bot_model`), `list_trained_combos`, `backtest_registered_bot_model`.
- `api/main.py` : application **FastAPI** `ml-api` (`:8010`) exposant :
  - lecture : `/health`, `/models`, `/signals/latest`, `/bot-models/trained-combos`, `/bot-models/predict`, `/bot-models/backtest` ;
  - pipeline : **`/internal/pipeline/features`, `/train-random_forest`, `/train-mlp`, `/train-xgboost`** — **sans authentification** (V5). `_resolve_symbol` et `AVAILABLE_MODELS` s'appuient sur le registre partagé `utils/ml/registry.py`.
- `api/serve.py` : lancement uvicorn ; `api/schemas.py` : schémas requête/réponse.

La source unique des modèles/symboles exposés est `utils/ml/registry.py` et `utils/connectors/exchanges/registry.py` (voir [`../utils/ARCHITECTURE.md`](../utils/ARCHITECTURE.md)).

---

## 6. Backtesting

`backtesting/engine.py` : `BacktestConfig`, `BacktestResult`, `run_backtest(...)` (`engine.py:59`) — moteur partagé utilisé par `/bot-models/backtest` et le flux backtest du backend.

---

## 7. Exécution et dépendances

- CLI : `python -m src.main <command>` (`config`, `features`, `train-rf`, `train-lstm`, `train-mlp`, `train-xgboost`, `train-baselines`, `train-bot-rsi`, `api`, `check`) — `src/main.py:113-206`.
- Makefile : `make config|collect|collect-single|features|train-*|mlflow-ui|api|check|test`.
- Versions pilotées par `../versions.env` (`SCIKIT_LEARN_VERSION`, `JOBLIB_VERSION` partagés avec le backend ; `TORCH_VERSION=…+cpu` ; `MLFLOW_VERSION`).
- Résolution des chemins (`config.yaml`, `mlruns/`) **depuis `models/`** → lancer les commandes via `cd models`.

### Pièges vérifiés
- `torch==…+cpu` : index PyTorch CPU **sans wheel macOS** → installer `torch==2.13.0` depuis PyPI.
- `make test-models` **segfault** en parallèle (BLAS/OpenMP) → préfixer `OMP_NUM_THREADS=1`.
- `skops` non épinglé → 2 tests de persistance MLflow instables (épingler `skops==0.14.0`).
- **Aucun test `models/` n'est exécuté en CI.**

---

## 8. Limites structurelles (renvoi)

1. Endpoints `/internal/pipeline/*` sans authentification et port publié (V5).
2. Cache d'artefacts sans invalidation/versionnement côté backend (`backend/src/inference/service.py:30-76`).
3. Aucune exécution des tests models en CI.

Argumentation : [`../ANALYSE_CRITIQUE.md`](../ANALYSE_CRITIQUE.md).
