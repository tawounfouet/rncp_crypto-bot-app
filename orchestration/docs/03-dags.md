# 03 — DAGs Cryptobot

Statut: référence
Derniere revision: 2026-07-28

## Qu'est-ce qu'un DAG ?

Un **DAG** (Directed Acyclic Graph) est un pipeline de tâches définies en Python.
Il décrit **quoi faire**, **dans quel ordre**, et **à quelle fréquence**.

```
DAG : cryptobot_health_check (toutes les heures)
│
├── Task 1 : ping_backend
│       └── GET http://crypto-bot-backend:8009/health
│
└── Task 2 : check_db_orders  (s'exécute après Task 1)
        └── SELECT COUNT(*) FROM orders;
```

---

## Structure d'un DAG Python

```
┌────────────────────────────────────────────────────────────┐
│                    DAG Python                               │
│                                                             │
│  1. Imports                                                 │
│  2. default_args  (owner, retries, start_date...)           │
│  3. Fonctions Python (_ping_backend, _check_db_orders...)   │
│  4. Déclaration DAG (with DAG(...) as dag:)                 │
│  5. Opérateurs (PythonOperator, BashOperator...)            │
│  6. Chaînage des tâches (task1 >> task2 >> task3)           │
└────────────────────────────────────────────────────────────┘
```

---

## Le DAG d'exemple : `example_cryptobot.py`

Ce DAG est fourni comme modèle de départ. Il effectue un **healthcheck** de l'écosystème.

```python
from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.providers.postgres.hooks.postgres import PostgresHook
import requests, logging

default_args = {
    "owner": "cryptobot",
    "depends_on_past": False,
    "start_date": datetime(2026, 6, 1),
    "email_on_failure": False,
    "retries": 1,
    "retry_delay": timedelta(minutes=5),
}

def _ping_backend():
    url = "http://crypto-bot-backend:8009/health"
    response = requests.get(url)
    if response.status_code != 200:
        raise Exception(f"Backend unhealthy: {response.status_code}")

def _check_db_orders():
    pg_hook = PostgresHook(postgres_conn_id="postgres_default")
    connection = pg_hook.get_conn()
    cursor = connection.cursor()
    cursor.execute("SELECT COUNT(*) FROM orders;")
    count = cursor.fetchone()[0]
    logging.info(f"Total orders in DB: {count}")

with DAG(
    "cryptobot_health_check",
    default_args=default_args,
    schedule_interval=timedelta(hours=1),
    catchup=False,
) as dag:

    ping_backend_task = PythonOperator(
        task_id="ping_backend",
        python_callable=_ping_backend,
    )

    check_db_task = PythonOperator(
        task_id="check_db_orders",
        python_callable=_check_db_orders,
    )

    ping_backend_task >> check_db_task   # ← chaînage
```

---

## Connexions Airflow configurées

Les connexions sont créées automatiquement par `airflow-init` au 1er démarrage :

| Connection ID | Type | Cible |
|---------------|------|-------|
| `postgres_default` | PostgreSQL | `postgres:5432` → `crypto_bot_db` |

Pour ajouter une connexion MinIO manuellement via l'UI :
> **Admin → Connections → + Add Connection**

---

## Bonnes pratiques DAG dans ce projet

### 1. Nommer les tâches clairement

```python
# ✅ Bon
task_id="fetch_binance_btc_ohlcv"

# ❌ Mauvais
task_id="task1"
```

### 2. Toujours utiliser `catchup=False`

```python
with DAG(..., catchup=False) as dag:
```
Sans cela, Airflow exécuterait tous les runs manqués depuis `start_date`.

### 3. Utiliser les Hooks plutôt que les connexions directes

```python
# ✅ Utiliser PostgresHook (gère la connexion via le pool Airflow)
from airflow.providers.postgres.hooks.postgres import PostgresHook
pg_hook = PostgresHook(postgres_conn_id="postgres_default")

# ❌ Ne pas hardcoder les connexions
import psycopg2
conn = psycopg2.connect(host="localhost", ...)
```

### 4. Logger via le module `logging` standard

```python
import logging
logging.info("Message visible dans l'UI Airflow")
```

---

## DAGs existants

```
orchestration/dags/
├── example_cryptobot.py   Healthcheck (backend + DB), horaire
├── ingest_ohlcv.py        Un DAG généré par exchange (ingest_ohlcv_<exchange>_to_minio)
└── ml_pipeline.py         Features → training → déploiement → vérification
```

### `ingest_ohlcv.py` — ingestion multi-exchange

Un DAG **par exchange**, généré à partir de `INGESTION_TARGETS` (actuellement
Binance et Kraken). Schedule : `@hourly`.

```
[exchange API] (via utils/connectors/exchanges, ccxt)
      │
      ▼
collect_<exchange>_<symbol>_<interval>
      │  écrit raw/ohlcv/<exchange>/<SYMBOL>/<interval>/<date>.parquet dans MinIO
      ▼
load_<exchange>_<symbol>_<interval>
      │  charge dans PostgreSQL, table market_data (scopée par exchange)
      ▼
[market_data prêt pour l'API backend et pour models/]
```

### `ml_pipeline.py` — features, training, déploiement

Schedule : quotidien à 06:00 UTC (après les runs d'ingestion nocturnes).

```
build_features_BTCUSDT_1h ─┐
build_features_ETHUSDT_1h ─┴─► train_random_forest ─► deploy_model ─► verify_inference
```

`build_features_*` et `train_random_forest` appellent `crypto-bot-ml-api` en HTTP
(`POST /internal/pipeline/features`, `POST /internal/pipeline/train-rf`) plutôt que
d'exécuter `python -m src.main` dans le conteneur Airflow — cf.
`04-troubleshooting.md`, Problème 8. `deploy_model` copie le meilleur modèle vers
MinIO, `verify_inference` appelle l'endpoint d'inférence du backend.
