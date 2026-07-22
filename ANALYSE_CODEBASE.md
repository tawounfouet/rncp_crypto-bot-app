# Analyse approfondie de la codebase — CryptoBot App

## 1. Vue d'ensemble

**Projet :** CryptoBot App — Monorepo d'une plateforme de trading automatisé de cryptomonnaies
**Stack :** Python 3.14 / FastAPI / Streamlit / Apache Airflow / PostgreSQL / MinIO / MLflow
**CI/CD :** GitLab CI
**Déploiement :** Docker Compose (dev, staging, prod)

Le projet est structuré en **5 domaines métier** clairement séparés, orchestrés via Docker Compose.

---

## 2. Architecture globale

```
┌────────────────────────────────────────────────────────────────────┐
│                        dev-network (Docker)                         │
│                                                                      │
│  ┌──────────────┐     HTTP      ┌──────────────────────┐           │
│  │  Frontend     │ ────────────► │  Backend FastAPI     │           │
│  │  Streamlit    │              │  :8009                │           │
│  │  :8501        │              └────────┬─────────────-┘           │
│  └──────────────┘                       │                          │
│                                         │ SQLAlchemy                │
│  ┌──────────────────────────────────┐   │                          │
│  │  Airflow                          │   ▼                          │
│  │  ┌──────────┐ ┌──────────┐       │  ┌────────────────────────┐ │
│  │  │Webserver │ │Scheduler │       │  │  PostgreSQL :5432       │ │
│  │  │:8080     │ │          │       │  │  ├─ crypto_bot_db       │ │
│  │  └────┬─────┘ └────┬─────┘       │  │  ├─ airflow             │ │
│  │       └──────┬─────┘              │  │  └─ mlflow              │ │
│  └──────────────│───────────────────┘  └────────────────────────┘ │
│                 │ SQLAlchemy                                        │
│                 ▼                                                   │
│       ┌────────────────┐     ┌──────────────────────┐              │
│       │   MinIO :9000  │     │  crypto-bot-ml-api   │              │
│       │  S3-compatible │     │  FastAPI :8010        │              │
│       └────────────────┘     │  MLflow UI :5001      │              │
│                              └──────────────────────┘              │
└────────────────────────────────────────────────────────────────────┘
```

### Services Docker

| Service | Technologie | Port | Rôle |
|---------|-------------|------|------|
| `postgres` | PostgreSQL | 5434 (host) | Base de données principale |
| `adminer` | Adminer | 8085 | UI d'administration PostgreSQL |
| `minio` | MinIO | 9000/9001 | Stockage objet S3 (données brutes) |
| `crypto-bot-backend` | FastAPI | 8009 | API REST backend |
| `crypto-bot-frontend` | Streamlit | 8501 | Interface utilisateur |
| `airflow-webserver` | Airflow | 8080 | UI d'orchestration |
| `airflow-scheduler` | Airflow | — | Scheduler de tâches |
| `crypto-bot-ml-api` | FastAPI | 8010 | API de prédiction ML |
| `mlflow-ui` | MLflow | 5001 | Tracking d'experiments |
| `createbuckets` | MinIO mc | — | Init buckets (one-shot, profile `tools`) |

---

## 3. Backend (`backend/`)

**Stack :** FastAPI / SQLAlchemy 2.0 / Pydantic V2 / PyJWT / Argon2

### Structure modulaire

```
backend/src/
├── main.py                  # Point d'entrée FastAPI + lifespan + middlewares
├── auth/                    # Authentification complète
│   ├── router.py            # POST /register, /login, /login/json, /refresh, /logout
│   ├── users_router.py      # CRUD utilisateurs
│   ├── service.py           # Logique métier (hash, JWT, sessions)
│   ├── user_service.py      # Gestion des utilisateurs
│   ├── schemas.py           # LoginRequest, TokenResponse, UserCreate, etc.
│   ├── models.py            # SQLAlchemy models (User, Session)
│   └── dependencies.py      # Injection de dépendances FastAPI
├── trading/                 # Trading (router, service, models, schemas)
├── market/                  # Données marché (router, service, clients Binance)
│   └── clients/             # Clients API Binance
├── strategy/                # Stratégies de trading
│   └── engine/              # Moteur d'exécution des stratégies
└── shared/                  # Code partagé
    ├── config/
    │   ├── settings.py      # Settings Pydantic (350 lignes) — auto-détection Docker, fallback SQLite
    │   └── constants.py     # 30+ Enums : UserRole, OrderType, StrategyType, ErrorCode, etc.
    ├── database/
    │   ├── connection.py    # DatabaseManager — fallback PostgreSQL → SQLite
    │   ├── init_database.sql # Schéma SQL complet (13 tables, 4 vues, indexes)
    │   ├── migrations/      # Dossier migrations Alembic (vide / {versions})
    │   ├── seeds/           # Données de seed
    │   └── sql/             # Scripts SQL (triggers, views)
    ├── models/base.py       # Base Model SQLAlchemy avec mixins (UUID, Timestamps, SoftDelete, Audit)
    ├── schemas/common.py    # Schemas Pydantic communs
    └── core/exceptions.py   # Exceptions personnalisées
```

### Points clés

- **Authentification réelle** : JWT (HS256), Argon2 pour le hash, refresh tokens, sessions tracks (IP, user-agent)
- **Base de données** : PostgreSQL en production, SQLite fallback automatique en local
- **Health checks** : `/health`, `/health/detailed` (statut DB, features flags)
- **Sécurité** : CORS, TrustedHost middleware, rate limiting configurable, error codes enum
- **Constants extensives** : 30+ enums couvrant tous les domaines (trading, stratégies, risques, alertes, transactions)
- **Backend complet mais** : les routers trading/market/strategy sont importés mais les endpoints réels ne sont pas encore câblés (routes vides)

---

## 4. Frontend (`frontend/`)

**Stack :** Streamlit / Plotly / Pydantic / Mock Database

### Architecture "Mock-First"

```
frontend/src/
├── app.py                  # Page de connexion principale
├── pages/                  # Pages Streamlit
│   ├── 02_Inscription.py
│   ├── 03_Portefeuille_Spot.py
│   ├── 04_Performances_Spot.py
│   ├── 05_Controle_Bot_Spot.py
│   ├── 06_Parametrage_Bot_Spot.py
│   ├── 07_Gestion_de_compte.py
│   └── 08_Admin.py
├── components/             # Composants réutilisables
│   ├── navigation.py       # Sidebar publique/privée, sélecteur de scénario
│   ├── headers.py          # En-têtes de page
│   ├── tables.py           # Tableaux stylisés
│   ├── cards.py            # Cartes premium
│   ├── badges.py           # Badges de statut
│   ├── alerts.py           # Alertes/notifications
│   └── prerequisites.py    # Vérification des prérequis Binance
├── layouts/
│   └── page_shell.py       # Shell commun (setup_page, auth guard, navigation)
├── services/               # Couche service
│   ├── auth_service.py     # Auth réelle (login, register, refresh, logout)
│   ├── auth_api_client.py  # Client HTTP vers le backend FastAPI
│   ├── account_service.py
│   ├── admin_service.py
│   ├── portfolio_service.py
│   ├── performance_service.py
│   ├── bot_config_service.py
│   └── bot_control_service.py
├── mocks/                  # Données mockées
│   ├── db.py               # MockStore — base en mémoire (utilisateurs, bots, configs)
│   ├── factories.py        # Génération de données mockées
│   └── scenarios.py        # Scénarios de test (normal, edges, empty, error)
├── schemas/                # Modèles Pydantic (auth, bot, portfolio, etc.)
├── theme/                  # Système de thème complet
│   ├── tokens.py           # Design tokens (couleurs, espacements, typo)
│   ├── styles.py           # CSS injecté global
│   ├── manager.py          # Gestionnaire de thème clair/sombre
│   └── plotly.py           # Thème Plotly synchronisé
├── state/session.py        # Session state Streamlit (tokens, user, sync)
├── navigation/rules.py     # Règles de navigation (public/privé/admin)
└── utils/                  # Utilitaires
    ├── validators.py       # Validation email, password, username
    ├── formatters.py       # Formatage monétaire, dates
    ├── constants.py        # Constantes UI
    └── streamlit_compat.py # Shim compatibilité versions Streamlit
```

### Points clés

- **Stratégie mock-first** : l'authentification est réelle (appelle le backend), mais toutes les pages métier utilisent des données mockées via `MockStore` (base en mémoire avec scénarios)
- **Auth réelle** : `AuthService` appelle le backend FastAPI, gère les JWT, le refresh automatique et la synchronisation utilisateur
- **Session TTL** : synchronisation de l'utilisateur toutes les 60s avec le backend
- **Thème complet** : design tokens, mode clair/sombre, Plotly synchronisé, CSS global
- **Contrôle d'accès** : règles de navigation par rôle (USER, ADMIN), sidebar adaptative
- **Tests** : 20+ fichiers de tests unitaires et d'intégration

---

## 5. Modèles ML (`models/`)

**Stack :** PyTorch (LSTM) / Scikit-learn (Random Forest) / MLflow / XGBoost (baselines)

### Structure

```
models/src/
├── main.py                  # CLI centralisée (config, collect, features, train-rf, train-lstm, train-baselines, api, check)
├── config/
│   ├── config_loader.py     # Charge config.yaml
│   ├── settings.py          # Settings Pydantic
│   └── dependencies.py      # Injection des dépendances
├── data/                    # Collecte et stockage des données
│   └── collect.py           # Collecte OHLCV depuis Binance
├── features/
│   ├── build.py             # Construction du feature set
│   ├── indicators.py        # Indicateurs techniques (SMA, EMA, RSI, MACD, Bollinger)
│   └── labels.py            # Génération des labels BUY/SELL/HOLD
├── models/
│   ├── random_forest.py     # Modèle Random Forest
│   ├── lstm.py              # Modèle LSTM (PyTorch)
│   ├── baselines.py         # Baselines (AlwaysHold, UniformRandom)
│   └── losses.py            # Loss functions (Focal Loss)
├── training/
│   ├── train_random_forest.py
│   ├── train_lstm.py
│   └── train_baselines.py
├── inference/signal.py      # Inférence pour API
├── api/main.py              # API FastAPI pour servir les prédictions (/signals/latest)
├── mlops/                   # MLflow tracking
├── backtesting/             # Backtesting engine
└── validation/mvp_check.py  # Vérification MVP
```

### Pipeline ML typique

```
Collect (Binance API) → Features Engineering → Train Random Forest / LSTM → MLflow tracking → API inference
```

### Configuration (`config.yaml` — 215 lignes)

- 3 classes : SELL(0) / HOLD(1) / BUY(2)
- Features techniques : returns, volatilité, SMA, EMA, RSI, MACD, Bollinger Bands, volume
- Split temporel : 70/15/15
- Random Forest : 300 estimators, max_depth 8, class_weight balanced
- LSTM : 128 hidden, 2 layers, dropout 0.2, sequence 128
- MLflow : tracking SQLite → PostgreSQL en production

---

## 6. Orchestration (`orchestration/`)

**Stack :** Apache Airflow 2.8.1 (LocalExecutor)

### Pipeline d'ingestion

```
DAG: ingest_ohlcv_binance_to_minio
Planification: @hourly
Max active runs: 1

start → collect_BTCUSDT_1h ─┐
                              ├→ notify_success
        collect_ETHUSDT_1h ─┘
```
1. **collect_ohlcv** (PythonOperator) : Binance API → DataFrame → Parquet → MinIO (`raw/ohlcv/<SYMBOL>/<interval>/<date>.parquet`)
2. **load_ohlcv** (PythonOperator) : MinIO → PostgreSQL (`market_data` table avec upsert via UUIDv5 déterministe)

### Architecture Airflow

- 3 services : `airflow-init` (one-shot) → `airflow-webserver` + `airflow-scheduler`
- Image personnalisée basée sur `apache/airflow:2.8.1-python3.11`
- Logs sur volume nommé (évite `Permission denied`)

---

## 7. Jobs batch (`jobs/`)

### Module `ingest/collect_ohlcv.py` (282 lignes)

- Fonctions pures de collecte Binance (sans dépendance AppSettings)
- Mapping klines → OHLCV normalisé
- Upload Parquet vers MinIO
- Usage CLI ou Airflow (PythonOperator)

### Module `transform/load_ohlcv.py` (221 lignes)

- Téléchargement Parquet depuis MinIO
- Transformation et upsert dans PostgreSQL (`market_data`)
- IDs UUIDv5 déterministes pour l'idempotence
- Fallback SQLite pour développement local

---

## 8. Infrastructure et CI/CD

### Docker Compose multi-environnement

| Fichier | Usage |
|---------|-------|
| `docker-compose.yml` | Dev (make dev-up) |
| `docker-compose.staging.yml` | Staging (make staging-up) |
| `docker-compose.prod.yml` | Production (make prod-up) |
| `ci/docker-compose.test.yml` | Tests CI |

### Makefile (154 lignes)

- `dev-up/down/config/logs/build/rebuild`
- `ml-up/down/logs/train-rf`
- `staging-*`, `prod-*`
- `test`, `test-backend`, `test-frontend`
- `lint`, `lint-fix`
- `check-infra`, `health`, `verify`

### GitLab CI/CD (`603 lignes`)

**Stages :** lint → build → test → deploy

| Job | Description |
|-----|-------------|
| `lint:versions` | Vérifie synchronisation `versions.env` ↔ `.gitlab-ci.yml` |
| `lint:dockerfile:backend/frontend` | Hadolint |
| `semgrep_sast` | Scan de sécurité Semgrep |
| `lint:python` | Ruff check + format |
| `build:docker` | Build multi-stage backend (runtime + test) + frontend |
| `test:integration` | Tests avec Postgres réel |
| `scan:images` | Trivy (vulnérabilités, CRITICAL bloquant) |
| `validate_tag` | Validation semver (vX.Y.Z) |
| `create_release` | GitLab Release |
| `deploy:staging` | Déploiement VM AWS (staging) |
| `deploy:production` | Déploiement VM AWS (prod, manuel) |
| `update:manifests` | GitOps — mise à jour manifests Kustomize pour ArgoCD |

### Workflow branches

```
dev_*/feature/* → lint seul (feedback rapide)
MR → pipeline complet (lint + build + test)
staging → build + deploy staging automatique
tag vX.Y → build + deploy production (manuel) + release
```

### Scripts (9 scripts)

| Script | Rôle |
|--------|------|
| `check-infra.sh` | Validation cohérence versions/Dockerfiles/CI |
| `dev-deploy.sh` | Déploiement local automatisé |
| `verify.sh` | Vérification de santé de tous les services |
| `generate-requirements.py` | Compilation des requirements depuis versions.env |
| `run_tests.sh` / `run-lint.sh` | Exécution tests/lint |
| `push.sh` | Push avec hooks |

---

## 9. Base de données

### Schéma cible PostgreSQL (`init_database.sql` — 517 lignes)

**13 tables :**

| Table | Description |
|-------|-------------|
| `users` | Utilisateurs (email, username, password hash Argon2) |
| `user_sessions` | Sessions JWT (token, expires_at, IP, user-agent) |
| `user_accounts` | Multi-providers (OAuth, credentials) |
| `user_settings` | Préférences (thème, API keys, risk profile) |
| `strategies` | Définitions de stratégies |
| `strategy_deployments` | Instances de trading live |
| `strategy_states` | États temps réel des stratégies |
| `trading_sessions` | Sessions de trading |
| `backtest_results` | Résultats de backtest |
| `orders` | Ordres (compatibles Binance API) |
| `order_fills` | Exécutions partielles |
| `transactions` | Mouvements financiers |
| `market_data` | Données OHLCV |

**4 vues :** `v_user_statistics`, `v_strategy_performance`, `v_active_deployments`, `v_trading_activity`

### Modèle SQLAlchemy (`models/base.py`)

- `BaseModel` : UUID PK, created_at, updated_at, `to_dict()`, `update_from_dict()`
- `BaseModelWithSoftDelete` : + soft delete
- `BaseAuditModel` : + created_by, updated_by
- `BaseFullAuditModel` : tout combiné
- `get_or_create`, `bulk_create_or_update`

### Initialisation (`init-user-db.sh`)

- Crée les bases `airflow` et `mlflow` si absentes (requête conditionnelle)

---

## 10. Version management

### `versions.env` — source unique de vérité

Centralise toutes les versions : Python, PostgreSQL, Airflow, MinIO, outils CI, dépendances Python.

`generate-requirements.py` compile les `.txt.template` → `requirements.txt`.

---

## 11. Qualité et sécurité

### Linting
- **Ruff** : F/E/W/I/UP/B/S/RUF (line-length 120)
- **Hadolint** : Dockerfile best practices
- **Semgrep** : SAST rules personnalisées (`.semgrep/security.yml`)
- **Trivy** : Scan CVE images (CRITICAL bloquant)

### Pre-commit
- `.pre-commit-config.yaml` configuré

### Sécurité
- `.env` jamais commité (`.gitignore`)
- Argon2 pour le hash des mots de passe
- JWT avec expiration configurables
- CORS restreint
- TrustedHost middleware
- PR production nécessite approbation manuelle

---

## 12. Forces et axes d'amélioration

### Points forts

1. **Architecture monorepo claire** : séparation nette backend / frontend / ML / orchestration / jobs
2. **Mock-first pragmatique** : authentification réelle + pages métier mockées = itération rapide
3. **Fallback intelligents** : PostgreSQL → SQLite, MinIO → fichier local
4. **CI/CD industrialisée** : lint → build → test → scan → deploy (staging auto, prod manuelle)
5. **Pipelines de données** : Airflow orchestre collecte OHLCV → MinIO → PostgreSQL
6. **MLOps** : MLflow tracking, Random Forest + LSTM, API de prédiction
7. **Version centralisée** : `versions.env` unique + script de génération des requirements
8. **Thème complet** : design cohérent, dark/light mode, Plotly synchronisé
9. **Sécurité** : Argon2, JWT, Semgrep, Trivy, TrustedHost
10. **Documentation** : architecture, setup, troubleshooting, ADR, specs fonctionnelles

### Axes d'amélioration

1. **Routers backend vides** : les endpoints trading/market/strategy sont importés mais les routes métier ne sont pas encore implémentées
2. **Tests backend** : dossiers `tests/unit/`, `tests/integration/`, `fixtures/` existent mais semblent peu fournis
3. **Migrations** : dossier `migrations/{versions}/` est vide (pas d'Alembic configuré)
4. **Script SQL MySQL** : `init_database.sql` utilise la syntaxe MySQL (`UUID()`, `CURRENT_TIMESTAMP ON UPDATE`, `USE`), pas PostgreSQL — incohérent avec le reste
5. **Schemas Pydantic backend** : `shared/schemas/` ne contient que `common.py`, les schemas métier sont dans chaque module
6. **Mix Pydantic V1/V2** : certaines parties du code frontend utilisent encore des patterns Pydantic V1 (selon l'historique git)
7. **Pas de pagination API** : bien que configurable dans les settings, la pagination n'est pas implémentée
8. **Dette technique FL** : le `config.yaml` du module ML fait 215 lignes et mériterait d'être modularisé
9. **SQLite en backend** : le fichier `backend/src/shared/database/db.sqlite3` est commité (résidu de dev local)
10. **Pas de monitoring / alerting** : pas de Prometheus, Grafana, ou Sentry dans la stack
