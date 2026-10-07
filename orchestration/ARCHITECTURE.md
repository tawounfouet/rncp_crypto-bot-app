# Architecture — orchestration/

> Document de référence de la couche **Airflow**. Les jobs exécutés sont décrits dans [`../jobs/ARCHITECTURE.md`](../jobs/ARCHITECTURE.md) ; la vue globale dans [`../ARCHITECTURE.md`](../ARCHITECTURE.md).

---

## 1. Vue d'ensemble

Apache Airflow **2.8.1** (Python 3.11) planifie les pipelines de données et ML. Il ne contient **pas** de logique métier : chaque tâche est un `PythonOperator` qui importe un job (`jobs/`) ou appelle une API interne (backend, ml-api). Executor retenu : **`LocalExecutor`** (pas de Redis ni K8s requis en dev).

```
orchestration/
├── Dockerfile               # image custom (base apache/airflow:2.8.1-python3.11)
├── requirements.txt(.template)
├── dags/                    # logique planifiée
│   ├── example_cryptobot.py       # DAG d'exemple / healthcheck
│   ├── ingest_ohlcv.py            # 1 DAG par exchange : collecte → MinIO → Postgres
│   ├── backfill_ohlcv.py          # 1 DAG par exchange, déclenchement MANUEL
│   ├── ml_pipeline.py             # features → training → deploy → sync catalogue
│   └── purge_inactive_users.py    # purge RGPD hebdomadaire (appelle le backend)
├── plugins/                 # opérateurs/hooks custom (vide aujourd'hui)
├── docs/                    # 01-architecture, 02-setup, 03-dags, 04-troubleshooting, 05-adr
└── tests/test_purge_inactive_users_dag.py
```

Métriques : **823 lignes / 6 fichiers** Python.

---

## 2. Services et image

Trois conteneurs (définis dans `docker-compose*.yml`) :
- `airflow-init` (one-shot) : `airflow db init` (migrations Alembic), création des connections et de l'utilisateur admin ;
- `airflow-webserver` (`:8080`) ;
- `airflow-scheduler` : lit les DAGs depuis `orchestration/dags/` et exécute les tâches localement.

L'image (`orchestration/Dockerfile`) part de `apache/airflow:2.8.1-python3.11`, ajoute `build-essential`/`git`, installe `orchestration/requirements.txt` (dont `apache-airflow==2.8.1` **ré-épinglé** pour éviter Airflow 3.x, providers postgres/amazon, et `-r jobs/requirements.txt`), puis `COPY` `dags/`, `plugins/`, `jobs/`, `models/`, `utils/`. En dev, `dags/` et `jobs/` sont bind-montés.

Bases : PostgreSQL — base `airflow` (métadonnées) et `crypto_bot_db` (applicative) créées par `init-scripts/init-user-db.sh`. Voir `orchestration/docs/01-architecture.md`.

---

## 3. DAGs

| DAG | `dag_id` | Planification | Rôle |
|---|---|---|---|
| `example_cryptobot.py` | — | `timedelta(hours=1)` | Ping `/health` du backend + vérification d'accès BDD (`_ping_backend`, `_check_db_orders`) |
| `ingest_ohlcv.py` | `ingest_ohlcv_{exchange}_to_minio` | `@hourly` | Pour chaque exchange configuré : collecte (`jobs/ingest/collect_ohlcv.py`) puis chargement (`jobs/transform/load_ohlcv.py`) |
| `backfill_ohlcv.py` | `backfill_ohlcv_{exchange}` | `None` (**manuel**) | Reprise historique par exchange (job `jobs/backfill/backfill_ohlcv.py`) |
| `ml_pipeline.py` | `cryptobot_ml_pipeline` | `0 6 * * *` (quotidien 06:00 UTC) | features par (symbole, interval) → entraînement par modèle → déploiement artefacts → vérification inférence → **sync catalogue de bots** |
| `purge_inactive_users.py` | `cryptobot_purge_inactive_users` | `0 3 * * 0` (dimanche 03:00 UTC) | Appelle le backend pour purger les comptes inactifs |

Tous les DAGs sont créés avec `catchup=False`.

### 3.1 `ml_pipeline` — interactions inter-services

Les tâches appellent :
- **ml-api** (`:8010`) : `/internal/pipeline/features`, `/train-*` (voir [`../models/ARCHITECTURE.md`](../models/ARCHITECTURE.md)) ;
- **backend** (`:8009`) : `POST /internal/bot-templates/sync` (`_sync_bot_templates_callable`, `ml_pipeline.py:199`) pour rafraîchir le catalogue après entraînement ;
- **MinIO** via `jobs/deploy_model.py`.

Ces appels inter-services sont aujourd'hui **sans authentification** (V4, V5) — à protéger par jeton de service (cf. [`../RECOMMANDATIONS.md`](../RECOMMANDATIONS.md)).

---

## 4. Tests et qualité

- `orchestration/tests/test_purge_inactive_users_dag.py` — vérifie la structure/le câblage du DAG de purge.
- **Aucun lint ni test `orchestration/` n'est exécuté en CI**, et le hook ruff ne couvre pas ce dossier → lancer `make lint` manuellement après modification.

---

## 5. Limites structurelles (renvoi)

1. Appels Airflow → backend/ml-api sans authentification (V4, V5).
2. Aucune vérification automatique (lint/test) en CI sur les DAGs.
3. Doc d'architecture locale existante : `orchestration/docs/` (à maintenir avec ce fichier).

Argumentation : [`../ANALYSE_CRITIQUE.md`](../ANALYSE_CRITIQUE.md).
