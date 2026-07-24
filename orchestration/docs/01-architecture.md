# 01 — Architecture de l'orchestration

## Vue d'ensemble

Apache Airflow est intégré comme couche d'orchestration dans le projet `_dst-crypto-bot_v2`. Il coordonne les pipelines de données entre le backend FastAPI, PostgreSQL, et MinIO.

---

## Diagramme de l'architecture globale

```
┌─────────────────────────────────────────────────────────────────────┐
│                        DOCKER NETWORK : dev-network                  │
│                                                                       │
│  ┌──────────────┐    HTTP     ┌──────────────────┐                   │
│  │   Frontend   │ ──────────► │  Backend FastAPI  │                  │
│  │  (Streamlit) │             │    :8009/health   │                  │
│  │    :8501     │             └────────┬─────────-┘                  │
│  └──────────────┘                      │                             │
│                                        │ SQL                          │
│  ┌───────────────────────────────────┐ │                             │
│  │         AIRFLOW                   │ ▼                             │
│  │  ┌─────────────┐  ┌───────────┐  │ ┌──────────────────────────┐  │
│  │  │  Webserver  │  │ Scheduler │  │ │       PostgreSQL          │  │
│  │  │    :8080    │  │           │  │ │         :5432             │  │
│  │  └─────┬───────┘  └─────┬─────┘ │ │  ┌─────────────────────┐ │  │
│  │        │                │        │ │  │  crypto_bot_db      │ │  │
│  │        └───────┬────────┘        │ │  │  airflow            │ │  │
│  └────────────────│─────────────────┘ │  └─────────────────────┘ │  │
│                   │ SQL Alchemy        └──────────────────────────┘  │
│                   │ (airflow db)                                      │
│                   ▼                                                   │
│                         ┌───────────────┐                           │
│                         │     MinIO     │                           │
│                         │   :9000/:9001 │                           │
│                         └───────────────┘                           │
│                                                                       │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Composants Airflow

### Les 3 services Docker

```
airflow-init        (one-shot)
     │
     │ initialise la DB, crée user admin, configure connections
     ▼
airflow-webserver   (long-running)     :8080
     │
     │ partage la même image et les mêmes volumes
     │
airflow-scheduler   (long-running)
     │
     └── lit les DAGs depuis ./orchestration/dags/
         exécute les tâches localement (LocalExecutor)
```

### Flux d'initialisation au 1er démarrage

```
docker compose up
       │
       ├─► postgres (healthcheck OK ?)
       │         │
       │         └── init-scripts/init-user-db.sh
       │               └── CREATE DATABASE airflow (si inexistante)
       │
       └─► airflow-init
               ├── airflow db init      (migrations Alembic)
               ├── airflow connections add postgres_default
               └── airflow users create (admin)
                         │
                         ▼
               airflow-webserver + airflow-scheduler démarrent
```

---

## Structure des fichiers du projet

```
app/
├── docker-compose.yml             # Services Airflow + ancrage YAML
│
├── orchestration/                 # Tout ce qui est Airflow
│   ├── Dockerfile                 # Image personnalisée
│   ├── dags/                      # Logique métier planifiée
│   │   ├── .gitkeep
│   │   └── example_cryptobot.py   # DAG d'exemple / healthcheck
│   ├── logs/                      # Logs d'exécution (monté en volume)
│   │   └── .gitkeep
│   └── plugins/                   # Opérateurs / hooks custom
│       └── .gitkeep
│
└── init-scripts/                  # Bootstrap PostgreSQL
    └── init-user-db.sh            # Crée la base 'airflow' si absente
```

---

## L'image Docker personnalisée

L'image de base est `apache/airflow:2.8.1-python3.11`.  
Un `Dockerfile` dédié la surcharge pour ajouter les dépendances métier :

```
apache/airflow:2.8.1-python3.11  (image de base officielle)
         │
         │ build-essential, git (apt)
         │
         └── providers & libs pip :
               ├── apache-airflow==2.8.1          (version épinglée !)
               ├── apache-airflow-providers-postgres
               ├── apache-airflow-providers-amazon
               ├── pandas==2.3.3
               ├── numpy==2.4.3
               ├── minio==7.2.20
               └── python-binance==1.0.35
```

> ⚠️ La version `apache-airflow==2.8.1` est **ré-épinglée** dans le `pip install` pour
> empêcher une mise à niveau automatique vers Airflow 3.x qui casserait les binaires.

---

## Choix de l'executor

| Executor | Usage | Complexité |
|----------|-------|------------|
| **LocalExecutor** ✅ | Dev local, 1 machine | Simple |
| CeleryExecutor | Multi-workers, prod scale | Besoin de Redis |
| KubernetesExecutor | Cloud-native prod | Besoin K8s |

`LocalExecutor` a été retenu pour l'environnement de développement : aucune dépendance à Redis ou Kubernetes, et suffisant pour les volumes de données traités en phase de développement.
