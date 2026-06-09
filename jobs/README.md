# jobs/ — Scripts batch exécutés par Airflow

Ce dossier contient les **jobs d'ingestion et de traitement batch** orchestrés par Airflow.

## Principe

```
app/
├── orchestration/dags/   ← DAGs Airflow (planification, retry, alerting)
└── jobs/                 ← Code métier exécuté par les DAGs
    ├── requirements.txt  ← Dépendances légères (pas de torch/mlflow)
    └── ingest/
        └── collect_ohlcv.py  ← Job 1 : Binance → MinIO
```

Les jobs sont des **scripts Python autonomes** avec un `main()` et une interface CLI.
Ils sont appelés par Airflow via `PythonOperator` (import direct dans le DAG).

## Jobs disponibles

| Job | Description | Fréquence |
|-----|-------------|-----------|
| `ingest/collect_ohlcv.py` | Collecte OHLCV Binance → MinIO `raw/ohlcv/` | Toutes les heures |

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

```
crypto-bot-data/
└── raw/
    └── ohlcv/
        └── BTCUSDT/
            └── 1h/
                ├── 2026-06-09.parquet
                ├── 2026-06-10.parquet
                └── ...
```

## Lancer un job manuellement

```bash
# Dans le conteneur Airflow (qui a accès au réseau dev-network)
docker compose exec airflow-webserver python /opt/airflow/jobs/ingest/collect_ohlcv.py \
    --symbol BTCUSDT \
    --interval 1h \
    --limit 1000
```
