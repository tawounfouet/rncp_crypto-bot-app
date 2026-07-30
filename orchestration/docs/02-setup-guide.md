# 02 — Guide de mise en place

Statut: référence
Derniere revision: 2026-07-28

## Prérequis

- Docker Desktop installé et actif
- `make` disponible (utilisé à la place de `docker compose` direct)
- Accès au fichier `.env` (copié depuis `.env.example`)

---

## Étape 1 — Configurer les variables d'environnement

Copier l'exemple et compléter les valeurs Airflow :

```bash
cp .env.example .env
```

Valeurs à renseigner dans `.env` :

```ini
# Clé de chiffrement Airflow (générée une seule fois)
AIRFLOW_FERNET_KEY=<générer avec la commande ci-dessous>

# Clé secrète pour le webserver
AIRFLOW_WEBSERVER_SECRET_KEY=<chaîne aléatoire>

# Identifiants de l'admin Airflow
AIRFLOW_ADMIN_USER=admin
AIRFLOW_ADMIN_PASSWORD=admin
```

**Générer une Fernet Key :**

```bash
python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

> ⚠️ Ne jamais commiter `.env` en clair dans le dépôt. Il est listé dans `.gitignore`.

---

## Étape 2 — Vérifier les versions (versions.env)

Le fichier `versions.env` est la **source unique de vérité** pour les versions d'images :

```ini
AIRFLOW_IMAGE=apache/airflow:2.8.1-python3.11
```

Ce fichier est chargé automatiquement par le `Makefile` avant tout `docker compose`.

---

## Étape 3 — Créer la structure de dossiers Airflow

```bash
mkdir -p orchestration/dags orchestration/plugins
touch orchestration/dags/.gitkeep
touch orchestration/plugins/.gitkeep
```

### À quoi servent ces dossiers ?

```
orchestration/
├── dags/      → Bind-monté sur /opt/airflow/dags    (lus par le scheduler)
└── plugins/   → Bind-monté sur /opt/airflow/plugins (hooks/opérateurs custom)
```

Les logs Airflow (`/opt/airflow/logs`) vivent dans un **volume Docker nommé**
(`airflow_logs`), pas dans un dossier `orchestration/logs/` bind-monté — ça évite
un `Permission denied` côté hôte, l'UID Airflow (50000) n'ayant pas les droits sur
un dossier créé en root.

---

## Étape 4 — Le Dockerfile Airflow (orchestration/Dockerfile)

```dockerfile
ARG AIRFLOW_IMAGE
FROM ${AIRFLOW_IMAGE} AS runtime

USER root
RUN apt-get update \
  && apt-get install -y --no-install-recommends \
         build-essential \
         git \
  && apt-get autoremove -yqq --purge \
  && apt-get clean \
  && rm -rf /var/lib/apt/lists/*

USER airflow

# Dépendances : versions.env + orchestration/requirements.txt (généré depuis
# le .template), pas de pip install en dur — cf. docs/01-setup.md.
COPY --chown=airflow:root jobs/requirements.txt /opt/airflow/jobs/requirements.txt
COPY --chown=airflow:root orchestration/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r /tmp/requirements.txt

# Code applicatif copié en dur pour que l'image soit autonome en staging/prod
# (bind-monté en dev via x-airflow-common, cf. étape 6)
COPY --chown=airflow:root orchestration/dags/ /opt/airflow/dags/
COPY --chown=airflow:root orchestration/plugins/ /opt/airflow/plugins/
COPY --chown=airflow:root jobs/ /opt/airflow/jobs/
COPY --chown=airflow:root models/ /opt/airflow/models/
COPY --chown=airflow:root utils/ /opt/airflow/utils/
```

`orchestration/requirements.txt` ré-épingle `apache-airflow==2.8.1` (même raison
qu'avant : éviter une upgrade automatique vers Airflow 3.x) et inclut
`apache-airflow-providers-postgres`, `apache-airflow-providers-amazon`, plus
`-r jobs/requirements.txt` (dépendances des jobs d'ingestion, dont `ccxt`). Les
dépendances lourdes de `models/` (torch, scikit-learn, mlflow) ne sont **pas**
installées ici : le DAG `ml_pipeline` les appelle via HTTP sur `crypto-bot-ml-api`
plutôt que de les exécuter dans le conteneur Airflow (cf. `04-troubleshooting.md`,
Problème 8).

---

## Étape 5 — Configurer le script d'initialisation PostgreSQL

Créer `init-scripts/init-user-db.sh` :

```bash
#!/bin/bash
set -e

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-EOSQL
    SELECT 'CREATE DATABASE airflow'
    WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'airflow')\gexec

    SELECT 'CREATE DATABASE mlflow'
    WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'mlflow')\gexec
EOSQL
```

Le script crée aussi la base `mlflow` (utilisée par le tracking MLflow de `models/`),
au passage et avec le même mécanisme idempotent que `airflow`.

Ce script est exécuté **automatiquement** par l'image PostgreSQL au 1er démarrage
grâce au montage de volume dans `docker-compose.yml` :

```yaml
postgres:
  volumes:
    - ./init-scripts:/docker-entrypoint-initdb.d   # ← convention PostgreSQL Docker
```

---

## Étape 6 — Intégration dans docker-compose.yml

### L'ancre YAML (DRY)

Pour éviter la duplication entre `airflow-webserver`, `airflow-scheduler` et `airflow-init`,
on utilise une **ancre YAML** (`x-airflow-common`) :

```yaml
x-airflow-common: &airflow-common
  build:
    context: .
    dockerfile: orchestration/Dockerfile
    args:
      AIRFLOW_IMAGE: ${AIRFLOW_IMAGE}
  environment:
    - AIRFLOW__CORE__EXECUTOR=LocalExecutor
    - PYTHONPATH=/opt/airflow
    - AIRFLOW__DATABASE__SQL_ALCHEMY_CONN=postgresql+psycopg2://...@postgres:5432/airflow
    - AIRFLOW__CORE__FERNET_KEY=${AIRFLOW_FERNET_KEY}
    - AIRFLOW__CORE__DAGS_ARE_PAUSED_AT_CREATION=true
    - AIRFLOW__CORE__LOAD_EXAMPLES=false
    - AIRFLOW__WEBSERVER__SECRET_KEY=${AIRFLOW_WEBSERVER_SECRET_KEY}
    # MinIO — requis par les jobs d'ingestion
    - MINIO_ENDPOINT=minio:9000
    - MINIO_ACCESS_KEY=${MINIO_ROOT_USER:-minioadmin}
    - MINIO_SECRET_KEY=${MINIO_ROOT_PASSWORD:-minioadmin}
    - MINIO_SECURE=0
    - MINIO_BUCKET=crypto-bot-data
    - BINANCE_BASE_URL=https://api.binance.com
  volumes:
    - ./orchestration/dags:/opt/airflow/dags
    # Volume nommé (pas un bind-mount) : Docker gère l'ownership pour l'user
    # airflow (UID 50000), évite un "Permission denied" sur un dossier hôte
    # créé en root.
    - airflow_logs:/opt/airflow/logs
    - ./orchestration/plugins:/opt/airflow/plugins
    - ./jobs:/opt/airflow/jobs       # jobs batch importés par les DAGs
    - ./models:/opt/airflow/models   # scripts ML — requis par le DAG ml_pipeline
    - ./utils:/opt/airflow/utils     # package transverse partagé
    - ./data:/app/data
  depends_on:
    postgres:
      condition: service_healthy
```

### Les 3 services Airflow

```yaml
services:
  airflow-init:          # One-shot : migrations DB + création user admin
    <<: *airflow-common
    entrypoint:
      - /bin/bash
      - -c
      - |
        airflow db init
        airflow connections add 'postgres_default' ...
        airflow users create ...

  airflow-webserver:     # UI web :8080
    <<: *airflow-common
    command: webserver
    ports: ["8080:8080"]
    depends_on:
      airflow-init:
        condition: service_completed_successfully

  airflow-scheduler:     # Planificateur de DAGs
    <<: *airflow-common
    command: scheduler
    depends_on:
      airflow-init:
        condition: service_completed_successfully
```

---

## Étape 7 — Démarrer l'environnement

```bash
# Toujours utiliser make (charge versions.env automatiquement)
make dev-up

# Vérifier l'état des services
make check-infra

# Suivre les logs Airflow
docker compose logs -f airflow-webserver airflow-scheduler
```

### Ordre de démarrage

```
postgres ──(healthy)──► airflow-init ──(completed)──► airflow-webserver
                                    └──(completed)──► airflow-scheduler
```

---

## Étape 8 — Accéder à l'interface

| Interface | URL | Identifiants |
|-----------|-----|--------------|
| Airflow UI | http://localhost:8080 | admin / admin |
| Adminer (PG) | http://localhost:8085 | voir `.env` |

---

## Résumé des fichiers créés / modifiés

```
Créés :
├── orchestration/Dockerfile
├── orchestration/requirements.txt(.template)
├── orchestration/dags/example_cryptobot.py
├── orchestration/dags/ingest_ohlcv.py
├── orchestration/dags/ml_pipeline.py
├── orchestration/plugins/.gitkeep
└── init-scripts/init-user-db.sh

Modifiés :
├── docker-compose.yml     (ajout ancre + 3 services Airflow)
├── versions.env           (ajout AIRFLOW_IMAGE)
├── .env.example           (ajout AIRFLOW_FERNET_KEY, etc.)
└── scripts/check-infra.sh (ajout healthcheck Airflow)
```
