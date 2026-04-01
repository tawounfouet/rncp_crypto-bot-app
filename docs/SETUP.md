# Guide d'installation - Crypto-Bot App

## Architecture du projet

```
Crypto-bot-app/                 # Monorepo applicatif
├── backend/                    # Code FastAPI
├── frontend/                   # Code Streamlit
├── scripts/                    # Scripts utilitaires
│   ├── push.sh                 # Push sur le remote
│   ├── dev-deploy.sh           # Build/push/deploy sur K8s namespace dev
│   ├── run_tests.sh            # Lancer les tests
│   ├── run_lint.sh             # Linting local (ruff)
│   ├── check-infra.sh          # Validation coherence versions.env / Dockerfiles
│   └── docker_status.sh        # Statut des containers Docker
├── docs/                       # Documentation
├── init-scripts/               # Scripts d'init PostgreSQL
├── docker-compose.yml          # Dev local / fallback VM AWS
├── docker-compose.staging.yml  # Fallback VM AWS (staging)
├── docker-compose.prod.yml     # Fallback VM AWS (production)
├── versions.env                # Versions des images Docker (source unique, tracke dans git)
├── Makefile                    # Point d'entree (charge versions.env + .env), taper `make` pour l'aide
├── pyproject.toml              # Configuration Ruff (linting + formatting)
├── .pre-commit-config.yaml     # Hooks pre-commit (ruff, semgrep, check-infra)
└── .gitlab-ci.yml              # CI/CD
```

**Deploiement principal** : cluster Kubernetes (Talos) via ArgoCD.
Les fichiers `docker-compose.*.yml` servent uniquement pour le dev local et comme
fallback sur la VM AWS DataScientest.

## Prerequis

- Git >= 2.13
- Docker >= 20.10
- Docker Compose >= 2.0
- Python 3.11+ (pour le developpement local)
- kubectl (pour le deploiement K8s dev)
- kubeseal (pour la gestion des secrets K8s)

## Installation

### 1. Cloner le projet

```bash
git clone git@gitlab.com:dst_crypto/Crypto-bot-app.git
cd Crypto-bot-app
```

### 2. Configurer l'environnement

```bash
# Copier le fichier d'environnement
cp .env.example .env

# Editer les variables selon votre configuration
nano .env
```

Variables importantes dans `.env` :
```env
# Base de donnees
POSTGRES_USER=postgres
POSTGRES_PWD=your_password
POSTGRES_DB=crypto_bot_db

# API Binance (optionnel pour dev)
BINANCE_TESTNET_API_KEY=your_key
BINANCE_TESTNET_API_SECRET=your_secret

# JWT
SECRET_KEY=your_secret_key
```

### 3. Lancer l'application (dev local avec Docker Compose)

```bash
# Demarrer tous les services (charge automatiquement versions.env + .env)
make dev-up

# Verifier le statut
./scripts/docker_status.sh

# Initialiser les buckets MinIO (premiere fois)
make dev-init
```

> **Important** : le `Makefile` charge `versions.env` (versions d'images, tracke dans git)
> et `.env` (secrets, gitignore) via `include` + `export`. Utiliser `make` plutot que
> `docker compose` directement pour garantir la resolution de toutes les variables.

Services disponibles (dev local) :
| Service | URL |
|---------|-----|
| Backend API | http://localhost:8009/api/v1/docs |
| Frontend | http://localhost:8501 |
| Adminer (PostgreSQL) | http://localhost:8085 |
| Mongo Express | http://localhost:8081 |
| MinIO Console | http://localhost:9001 |

## Developpement

### Installer les dependances (developpement local)

```bash
# Backend
cd backend
python -m venv venv
source venv/bin/activate  # Linux/Mac
pip install -r requirements-dev.txt

# Frontend (dans un autre terminal)
cd frontend
python -m venv venv
source venv/bin/activate
pip install -r requirements-dev.txt
```

### Lancer les tests

```bash
# Tests backend uniquement
./scripts/run_tests.sh backend

# Tests avec coverage
./scripts/run_tests.sh backend --coverage

# Tous les tests
./scripts/run_tests.sh all
```

### Lancer le linting

```bash
# Verifier le code (ruff check + format)
make lint

# Auto-corriger les erreurs
make lint-fix

# Valider la coherence infra (versions.env, Dockerfiles, docker-compose)
make check-infra
```

Les commandes `./scripts/run_lint.sh all` et `./scripts/run_lint.sh all --fix` sont aussi disponibles.

## Deploiement K8s dev

Pour tester ses modifications sur le cluster Kubernetes (namespace `dev`) sans
passer par la CI, utiliser le script `dev-deploy.sh` :

```bash
# Prerequis : docker login registry.gitlab.com (une seule fois)
# Prerequis : acces au cluster (Tailscale + kubeconfig)

# Build et deploy backend + frontend
./scripts/dev-deploy.sh

# Build et deploy un seul composant
./scripts/dev-deploy.sh backend
./scripts/dev-deploy.sh frontend
```

Le script build les images Docker localement, les pousse sur le registry GitLab
avec le tag `:dev`, puis relance les pods dans le namespace `dev`.

### Port-forward pour acceder aux services K8s

Le script de port-forward se trouve dans le repo infra :

```bash
# Depuis le repo Crypto-bot-infra
./scripts/port-forward.sh dev       # ou staging, production
```

Ports par environnement :

| Service    | Dev        | Staging    | Production |
|------------|------------|------------|------------|
| Frontend   | 8501       | 8601       | 8701       |
| Backend    | 8009       | 8109       | 8209       |
| PostgreSQL | 5432       | 5532       | 5632       |
| MongoDB    | 27017      | 27117      | 27217      |
| MinIO      | 9000/9001  | 9100/9101  | 9200/9201  |

## Workflow Git

### Branches et workflow

```
feature/* ou dev_*  --(MR, 0 approbation)-->  staging  --(MR, 1+ approbation)-->  main  --(tag)-->  vX.X
```

- **feature/\* ou dev_\*** : branches de travail. Lint seul a chaque push (feedback rapide).
- **staging** : branche d'integration. Merge Request sans approbation requise.
  Declenche build et deploy.
- **main** : branche de production. Merge Request avec au moins 1 approbation.
- **tag vX.X** : cree sur `main` pour declencher le build et le deploy production.

### Stages du pipeline

| Stage | Jobs | Declencheur |
|-------|------|-------------|
| lint | `lint:dockerfile:*`, `semgrep_sast` | MR, dev_\*, feature/\* |
| test | `check:backend`, `lint:frontend` | MR, staging, tag |
| build | `build:docker`, `scan:images` | staging, tag vX.X |
| deploy | `deploy:staging`, `deploy:production`, `update:manifests` | staging / tag vX.X |

### Tags Docker

La CI ne genere que des tags nommes, pas de tags SHA :

| Declencheur | Tags generes |
|-------------|--------------|
| Push sur staging | `:staging`, `:latest` |
| Tag vX.X | `:vX.X`, `:production`, `:latest` |

### Deploiement

- **K8s (principal)** : ArgoCD surveille le repo `Crypto-bot-infra`.
  - **staging** : auto-sync (deploiement automatique).
  - **production** : sync manuel dans ArgoCD.
- **VM AWS (fallback)** : deploy via SSH dans les jobs `deploy:staging` et
  `deploy:production`. Utilise `docker-compose.staging.yml` / `docker-compose.prod.yml`.

### Variable CI : GROUP_PAT_TOKEN

Un seul PAT (Personal Access Token) avec le scope `write_repository`, configure
comme **variable de groupe** sur `dst_crypto`. Cela rend le token disponible
dans les repos du groupe.

## Docker Compose (dev local et fallback VM AWS)

Les fichiers Docker Compose ne sont **pas** le mode de deploiement principal.
Ils servent pour :

1. **Dev local** : `docker-compose.yml` pour lancer tous les services sur sa machine.
2. **VM AWS fallback** : `docker-compose.staging.yml` et `docker-compose.prod.yml`
   deployes sur la VM DataScientest comme solution de repli si le
   cluster K8s est indisponible.

Le deploiement principal se fait sur le cluster Kubernetes Talos via ArgoCD
(repo `Crypto-bot-infra`).

> **Ne pas utiliser `docker compose` directement.** Les versions d'images sont
> dans `versions.env`, charge automatiquement par le `Makefile`. Utiliser
> `make dev-up`, `make staging-up`, etc. Taper `make` pour voir toutes les commandes.

### Gestion des versions d'images

Les versions d'images Docker sont centralisees dans `versions.env` (tracke dans git) :

```env
MONGO_IMAGE=mongo:4.4
POSTGRES_IMAGE=postgres:14
ADMINER_IMAGE=adminer
# ...
```

Les docker-compose referent ces versions via `${MONGO_IMAGE}`, `${POSTGRES_IMAGE}`, etc.
Le `Makefile` et la CI chargent ce fichier automatiquement.

Pour mettre a jour une version :
1. Modifier `versions.env`
2. Tester avec `make dev-config` / `make staging-config` / `make prod-config`
3. Committer et pousser

### Commandes Makefile

| Commande | Description |
|----------|-------------|
| `make dev-up` | Demarrer l'env dev |
| `make dev-down` | Arreter l'env dev |
| `make dev-logs` | Suivre les logs dev |
| `make dev-config` | Valider la config dev |
| `make dev-init` | Creer les buckets MinIO (dev) |
| `make staging-up` | Demarrer staging |
| `make staging-down` | Arreter staging |
| `make staging-config` | Valider la config staging |
| `make staging-init` | Creer les buckets MinIO (staging) |
| `make prod-up` | Demarrer la prod |
| `make prod-down` | Arreter la prod |
| `make prod-config` | Valider la config prod |
| `make prod-init` | Creer les buckets MinIO (prod) |
| `make prod-debug-up` | Activer Adminer + Mongo Express en prod |
| `make prod-debug-down` | Desactiver Adminer + Mongo Express en prod |
| `make dev-build` | Rebuild les images dev (sans cache) |
| `make lint` | Lancer ruff check + format |
| `make lint-fix` | Corriger automatiquement les erreurs ruff |
| `make check-infra` | Valider coherence versions.env / Dockerfiles / docker-compose |

### Services par environnement

| Service | Dev | Staging | Prod |
|---------|-----|---------|------|
| Backend | 8009 | 8009 | 9009 |
| Frontend | 8501 | 8501 | 8502 |
| PostgreSQL | 5434 | 5434 | 5435 |
| MongoDB | 27017 | 27017 | 27018 |
| MinIO API | 9000 | 9000 | 9002 |
| MinIO Console | 9001 | 9001 | 9003 |
| Adminer | 8085 | 8085 | 8086 (profile debug) |
| Mongo Express | 8081 | 8081 | 8082 (profile debug) |

En production, Adminer et Mongo Express ne demarrent pas par defaut (profile `debug`).
Le service `createbuckets` est sous le profile `tools` dans tous les environnements.

## Depannage

### Erreur "No module named 'src'"

```bash
# Definir le PYTHONPATH
export PYTHONPATH=$(pwd)/backend  # ou frontend
```

### Les containers ne demarrent pas (Docker Compose local)

```bash
# Voir les logs
make dev-logs

# Reconstruire les images
make dev-build
make dev-up
```

### Le cluster K8s ne repond pas

```bash
# Verifier que Tailscale est connecte avec les routes acceptees
tailscale status
tailscale up --accept-routes

# Tester la connexion au cluster
kubectl --context admin@crypto-bot get nodes
```
