# 02 — Guide de mise en place

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
mkdir -p orchestration/dags orchestration/logs orchestration/plugins
touch orchestration/dags/.gitkeep
touch orchestration/logs/.gitkeep
touch orchestration/plugins/.gitkeep
```

### À quoi servent ces dossiers ?

```
orchestration/
├── dags/      → Montés sur /opt/airflow/dags    (lus par le scheduler)
├── logs/      → Montés sur /opt/airflow/logs    (écrits par Airflow)
└── plugins/   → Montés sur /opt/airflow/plugins (hooks/opérateurs custom)
```

---

## Étape 4 — Le Dockerfile Airflow (orchestration/Dockerfile)

```dockerfile
ARG AIRFLOW_IMAGE
FROM ${AIRFLOW_IMAGE}

USER root
RUN apt-get update \
  && apt-get install -y --no-install-recommends \
         build-essential \
         git \
  && apt-get autoremove -yqq --purge \
  && apt-get clean \
  && rm -rf /var/lib/apt/lists/*

USER airflow

# IMPORTANT : épingler la même version qu'en base pour éviter une upgrade vers Airflow 3.x
RUN pip install --no-cache-dir \
    apache-airflow==2.8.1 \
    apache-airflow-providers-postgres \
    apache-airflow-providers-mongo \
    apache-airflow-providers-amazon \
    pymongo==4.16.0 \
    pandas==2.3.3 \
    numpy==2.4.3 \
    minio==7.2.20 \
    python-binance==1.0.35
```

---

## Étape 5 — Configurer le script d'initialisation PostgreSQL

Créer `init-scripts/init-user-db.sh` :

```bash
#!/bin/bash
set -e

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-EOSQL
    SELECT 'CREATE DATABASE airflow'
    WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'airflow')\gexec
EOSQL
```

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
    - AIRFLOW__DATABASE__SQL_ALCHEMY_CONN=postgresql+psycopg2://...@postgres:5432/airflow
    - AIRFLOW__CORE__FERNET_KEY=${AIRFLOW_FERNET_KEY}
    - AIRFLOW__CORE__DAGS_ARE_PAUSED_AT_CREATION=true
    - AIRFLOW__CORE__LOAD_EXAMPLES=false
    - AIRFLOW__WEBSERVER__SECRET_KEY=${AIRFLOW_WEBSERVER_SECRET_KEY}
  volumes:
    - ./orchestration/dags:/opt/airflow/dags
    - ./orchestration/logs:/opt/airflow/logs
    - ./orchestration/plugins:/opt/airflow/plugins
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
| Mongo Express | http://localhost:8081 | voir `.env` |

---

## Résumé des fichiers créés / modifiés

```
Créés :
├── orchestration/Dockerfile
├── orchestration/dags/example_cryptobot.py
├── orchestration/dags/.gitkeep
├── orchestration/logs/.gitkeep
├── orchestration/plugins/.gitkeep
└── init-scripts/init-user-db.sh

Modifiés :
├── docker-compose.yml     (ajout ancre + 3 services Airflow)
├── versions.env           (ajout AIRFLOW_IMAGE)
├── .env.example           (ajout AIRFLOW_FERNET_KEY, etc.)
└── scripts/check-infra.sh (ajout healthcheck Airflow)
```
