# Architecture — jobs/

> Document de référence des **jobs batch** exécutés par Airflow. Ordonnancement dans [`../orchestration/ARCHITECTURE.md`](../orchestration/ARCHITECTURE.md) ; vue globale dans [`../ARCHITECTURE.md`](../ARCHITECTURE.md).

---

## 1. Vue d'ensemble

`jobs/` contient le **code métier** des tâches batch, sous forme de **scripts Python autonomes** dotés d'un `main()` et d'une interface CLI. Airflow ne les orchestre que comme des `PythonOperator` (import direct depuis les DAGs) — les jobs restent exécutables seuls.

```
jobs/
├── ingest/collect_ohlcv.py     # exchange → MinIO (couche raw/)
├── transform/load_ohlcv.py     # MinIO → PostgreSQL (table market_data)
├── backfill/backfill_ohlcv.py  # reprise historique multi-exchange
├── deploy_model.py             # registre local → MinIO (artefacts modèle)
├── requirements.txt(.template) # dépendances légères (pas de torch/mlflow)
└── tests/test_collect_ohlcv.py # 1 fichier de test
```

Métriques : **791 lignes / 8 fichiers** Python.

---

## 2. Jobs

### 2.1 `ingest/collect_ohlcv.py` — collecte

`run_ingestion(...)` (`collect_ohlcv.py:46`) :
1. résout le driver via `utils.connectors.exchanges.get_market_data_driver(exchange)` (`collect_ohlcv.py:69`) — natif Binance, sinon ccxt ;
2. construit un DataFrame et le persiste dans MinIO en Parquet via `MinioClient.upload_dataframe` (`collect_ohlcv.py:89-90`).

Clé d'objet : **`raw/ohlcv/{exchange}/{SYMBOL}/{interval}/{YYYY-MM-DD}.parquet`** (`collect_ohlcv.py:86`). `--exchange` est piloté par le registry d'exchanges (Binance, Kraken, …).

### 2.2 `transform/load_ohlcv.py` — chargement

`run_loading(object_key, ...)` → `transform_and_load(df, db_url)` (`load_ohlcv.py:78`) :
1. `download_parquet_dataframe` lit le Parquet depuis MinIO (`load_ohlcv.py:44`) ;
2. renommage des colonnes vers le schéma Postgres ;
3. `INSERT ... ON CONFLICT DO UPDATE` idempotent sur la table `market_data`, contrainte **`uq_market_data_symbol_time`** (`load_ohlcv.py:124-134`).

### 2.3 `backfill/backfill_ohlcv.py` — reprise historique

`run_backfill(...)` (`backfill_ohlcv.py:97`) pagine les klines passées via le driver (`API_SLEEP_S = 0.25` pour respecter les rate limits — `backfill_ohlcv.py:75`), écrit dans MinIO puis en base. Supporte `--dry-run`. Déclenchement **manuel uniquement** (voir DAG).

### 2.4 `deploy_model.py` — déploiement d'artefacts

`deploy_model(model_name, registry_root="artifacts/registry")` (`deploy_model.py:33`) copie `ARTIFACTS_TO_DEPLOY = ["model.joblib", "scaler.joblib", "feature_columns.json"]` (`deploy_model.py:29`) de `artifacts/registry/<model>/best` vers MinIO sous `models/<model>/best` — pour que le backend charge le modèle. Déclenché par le DAG `cryptobot_ml_pipeline`.

---

## 3. Runtime et dépendances

- Les jobs s'exécutent **dans l'image Airflow** (venv partagé) via `PythonOperator`. `orchestration/Dockerfile` installe `-r jobs/requirements.txt`.
- Contrainte notable : Airflow 2.8.1 exige `sqlalchemy<2.0` → les jobs utilisent `AIRFLOW_SQLALCHEMY_SPEC=>=1.4.28,<2.0` (`versions.env`), distinct de la version backend.
- Connexions : `utils/connectors/minio.py` (`MinioClient`) et accès Postgres via SQLAlchemy Core.

### Variables d'environnement

`BINANCE_BASE_URL`, `MINIO_ENDPOINT`, `MINIO_ACCESS_KEY`, `MINIO_SECRET_KEY`, `MINIO_BUCKET` (`jobs/README.md`).

---

## 4. Tests

- `jobs/tests/test_collect_ohlcv.py` — lancement : `PYTHONPATH=. .venv/bin/python -m pytest jobs/tests -q`.
- **Aucun test `jobs/` n'est exécuté en CI** ; le hook pre-commit `run-tests-if-needed.sh` relance `test-jobs` sur modification de `jobs/` ou `utils/`.

---

## 5. Limites structurelles (renvoi)

1. Dépendance forte au registry `utils/connectors/exchanges` pour tout ajout d'exchange.
2. Pas de tests exécutés en CI.
3. Le job de déploiement suppose le layout local `artifacts/registry/<model>/best`.

Argumentation : [`../ANALYSE_CRITIQUE.md`](../ANALYSE_CRITIQUE.md).
