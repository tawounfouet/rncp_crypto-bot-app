# jobs/ — Scripts batch exécutés par Airflow

Statut: référence
Derniere revision: 2026-07-28

Ce dossier contient les **jobs d'ingestion et de traitement batch** orchestrés par Airflow.

## Principe

```
app/
├── orchestration/dags/   ← DAGs Airflow (planification, retry, alerting)
└── jobs/                 ← Code métier exécuté par les DAGs
    ├── requirements.txt  ← Dépendances légères (pas de torch/mlflow)
    ├── ingest/
    │   └── collect_ohlcv.py   ← Job 1 : exchange (Binance, Kraken, via ccxt) → MinIO
    ├── transform/
    │   └── load_ohlcv.py      ← Job 2 : MinIO → PostgreSQL (table market_data)
    └── deploy_model.py        ← Job 3 : copie le meilleur modèle entraîné vers MinIO
```

Les jobs sont des **scripts Python autonomes** avec un `main()` et une interface CLI.
Ils sont appelés par Airflow via `PythonOperator` (import direct dans le DAG).

## Jobs disponibles

| Job | Description | Fréquence |
|-----|-------------|-----------|
| `ingest/collect_ohlcv.py` | Collecte OHLCV multi-exchange (Binance, Kraken) → MinIO `raw/ohlcv/` | Toutes les heures, un DAG par exchange (`orchestration/dags/ingest_ohlcv.py`) |
| `transform/load_ohlcv.py` | Charge les fichiers MinIO dans PostgreSQL, table `market_data` | Enchaîné après chaque collecte |
| `deploy_model.py` | Copie l'artefact du meilleur modèle (`model.joblib`, `scaler.joblib`, `feature_columns.json`) vers MinIO | Déclenché par le DAG `ml_pipeline` |

## Variables d'environnement

Toutes les configurations passent par des variables d'environnement (déjà dans `.env`) :

| Variable | Défaut | Description |
|----------|--------|-------------|
| `BINANCE_BASE_URL` | `https://api.binance.com` | URL de base Binance |
| `MINIO_ENDPOINT` | `minio:9000` | Endpoint MinIO |
| `MINIO_ACCESS_KEY` | `minioadmin` | Clé d'accès MinIO |
| `MINIO_SECRET_KEY` | `minioadmin` | Secret MinIO |
| `MINIO_BUCKET` | `crypto-bot-data` | Bucket de destination |

## Convention de nommage dans MinIO

Le chemin inclut l'exchange, pour distinguer les sources sur les mêmes paires :

```
crypto-bot-data/
└── raw/
    └── ohlcv/
        └── binance/
            └── BTCUSDC/
                └── 1h/
                    ├── 2026-06-09.parquet
                    ├── 2026-06-10.parquet
                    └── ...
        └── kraken/
            └── BTCEUR/
                └── 1h/
                    └── ...
```

Soit `raw/ohlcv/{exchange}/{SYMBOL}/{interval}/{date}.parquet`.

## Lancer un job manuellement

```bash
# Dans le conteneur Airflow (qui a accès au réseau dev-network)
docker compose exec airflow-webserver python /opt/airflow/jobs/ingest/collect_ohlcv.py \
    --exchange binance \
    --symbol BTCUSDC \
    --interval 1h \
    --limit 1000
```

`--exchange` est optionnel (défaut `binance`) ; les exchanges supportés viennent du
registry `utils/connectors/exchanges` (cf. `docs/05-multi-exchange-layer.md`).
