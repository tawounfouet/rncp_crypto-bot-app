# Architecture — utils/

> Document de référence du **package partagé**. Utilisé par le backend, les jobs et models ; vue globale dans [`../ARCHITECTURE.md`](../ARCHITECTURE.md).

---

## 1. Vue d'ensemble

`utils/` est le **package partagé** entre `backend/`, `jobs/` et `models/`. Il concentre les connecteurs externes (exchanges, MinIO, Postgres), les indicateurs techniques, les registres de modèles/symboles et la conversion de signaux. Il est importé via `PYTHONPATH=.` depuis la racine.

```
utils/
├── connectors/
│   ├── exchanges/          # drivers de données de marché (natif Binance + ccxt)
│   │   ├── base.py         # Protocol MarketDataDriver
│   │   ├── binance_native.py
│   │   ├── ccxt_driver.py  # CCXT_IDS + CcxtDriver (multi-exchange)
│   │   └── registry.py     # get_market_data_driver, list_configured_*
│   ├── minio.py            # MinioClient (upload/download fichier & DataFrame)
│   └── postgres.py         # get_database_url, create_db_engine
├── features/indicators.py  # indicateurs techniques partagés
├── ml/registry.py          # registres de modèles (source unique)
├── trading/signals.py      # conversion signal ↔ valeur
├── logging/                # logger.py + formatters.py
└── tests/                  # 6 fichiers de test
```

Métriques : **1 257 lignes / 25 fichiers** Python.

> ⚠️ **Ne pas confondre** avec `frontend/src/utils/` (indépendant, jamais importé depuis la racine). Ne **jamais** mettre les deux sur le même `PYTHONPATH`.

---

## 2. Connecteurs exchanges

- `connectors/exchanges/base.py` : `@runtime_checkable Protocol MarketDataDriver` avec `fetch_klines(...)` (`base.py:96-101`).
- `binance_native.py` : `BinanceMarketDataDriver` (driver natif, payload plus riche).
- `ccxt_driver.py` : `CcxtDriver` + mapping `CCXT_IDS` (couche générique multi-exchange).
- `registry.py` :
  - `get_market_data_driver(exchange)` (`registry.py:19`) — natif si enregistré (`_NATIVE_DRIVERS = {"binance": ...}`), sinon `CcxtDriver` ;
  - `list_configured_exchanges()` — union des ids ccxt et des drivers natifs ;
  - `list_configured_symbols()` — `SUPPORTED_SYMBOLS = ["BTCUSDC", "ETHUSDC"]` ; **le premier élément est la paire par défaut** partout ;
  - `supports_sandbox_credentials(exchange)` — vrai si ccxt expose une URL de test (`urls["test"]`).

Ce registry est la **source unique** des paires/exchanges (utilisée par le backend, les DAGs et ml-api), remplaçant les listes auparavant dupliquées.

---

## 3. Connecteurs de stockage

- `connectors/minio.py` : `MinioClient` (`minio.py:15`) — `client`, `_ensure_bucket`, `upload_file`/`download_file`, `upload_dataframe`/`download_dataframe`, `list_objects`, `delete_object`. Bucket par défaut `crypto-bot-data` (env `MINIO_BUCKET`).
- `connectors/postgres.py` : `get_database_url(...)` (`postgres.py:13`, lit `DATABASE_URL` puis `POSTGRES_*`) et `create_db_engine(...)` (`postgres.py:34`, pool `pool_pre_ping`, `pool_size=5`, `max_overflow=10`, `pool_recycle=3600`).

---

## 4. Features, modèles, signaux, logging

- `features/indicators.py` : `add_returns`, `add_volatility`, `add_sma`, `add_ema`, `add_rsi`, `add_macd`, `add_bollinger_bands`, `add_volume_sma`, `add_order_flow_features` — partagés backend/ML.
- `ml/registry.py` : `SUPPORTED_MODELS = ["random_forest", "xgboost", "mlp", "lstm"]`, `PAIR_QUALIFIED_MODELS = ["random_forest", "xgboost", "mlp"]`, `list_configured_models()`, `list_pair_qualified_models()` — source unique pour `models/` et `ml_pipeline`.
- `trading/signals.py` : `SIGNAL_TO_VALUE = {"BUY": 1, "HOLD": 0, "SELL": -1}` (`signals.py:8`), `VALUE_TO_SIGNAL`, `CLASS_ID_TO_SIGNAL = {0: "SELL", 1: "HOLD", 2: "BUY"}` — évite les mappings dupliqués.
- `logging/` : `logger.py` + `formatters.py` (configuration de logs homogène).

---

## 5. Tests

- `tests/` : `test_base.py`, `test_binance_native.py`, `test_ccxt_driver.py`, `test_postgres.py`, `test_registry.py`, `test_signals.py` (**6** fichiers).
- Lancement : `PYTHONPATH=. .venv/bin/python -m pytest utils/tests -q`.
- **Aucun test `utils/` en CI** ; le hook pre-commit relance `test-utils` **et** `test-backend` + `test-jobs` sur modification de `utils/` (car le package est partagé).

---

## 6. Limites structurelles (renvoi)

1. Deux packages `utils` distincts (racine vs `frontend/src/utils`) — piège de `PYTHONPATH`.
2. Le registry d'exchanges est le point d'extension obligatoire pour tout nouvel exchange.
3. Tests non exécutés en CI.

Argumentation : [`../ANALYSE_CRITIQUE.md`](../ANALYSE_CRITIQUE.md).
