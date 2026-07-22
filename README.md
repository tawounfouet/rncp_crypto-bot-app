# Crypto-Bot App

Projet de trading automatise de cryptomonnaies — monorepo applicatif (backend + frontend).

## Architecture

```
Crypto-bot-app/                 # Monorepo applicatif
├── backend/                    # Code FastAPI
│   ├── src/
│   ├── ci/                     # Script parse_test_report.py (inclus dans l'image test)
│   ├── Dockerfile
│   └── requirements.txt
├── frontend/                   # Code Streamlit
│   ├── src/
│   ├── Dockerfile
│   └── requirements.txt
├── ci/                         # Docker Compose tests d'integration + resultats
│   ├── docker-compose.test.yml
│   └── test-results/           # Rapports JUnit/Cobertura (trackes pour tracabilite)
├── scripts/
│   ├── check-infra.sh          # Validation coherence versions.env / Dockerfiles
│   ├── run-tests-if-needed.sh  # Pre-commit : lint + tests si code modifie
│   ├── dev-deploy.sh           # Build + push + restart K8s namespace dev
│   ├── push.sh                 # Push sur le remote
│   ├── run_lint.sh             # Linting local (legacy, preferer make lint)
│   ├── run_tests.sh            # Tests locaux (legacy, preferer make test)
│   └── docker_status.sh        # Statut des containers Docker
├── .semgrep/                   # Regles de securite Semgrep
├── init-scripts/               # Scripts d'init PostgreSQL
├── docker-compose.yml          # Developpement local
├── docker-compose.staging.yml  # Environnement staging (VM AWS)
├── docker-compose.prod.yml     # Environnement production (VM AWS)
├── versions.env                # Versions des images Docker (source unique, tracke dans git)
├── .env.example                # Template des variables d'environnement (secrets)
├── Makefile                    # Raccourcis dev locaux (charge versions.env), taper `make` pour l'aide
├── pyproject.toml              # Configuration Ruff (linting + formatting)
├── .pre-commit-config.yaml     # Hooks pre-commit (ruff, semgrep, check-infra, tests)
└── .gitlab-ci.yml              # CI/CD
```

Le repo d'infrastructure Kubernetes est separe : `dst_crypto/Crypto-bot-infra` (Kustomize, overlays, ArgoCD).

## Installation

```bash
# Cloner le projet
git clone git@gitlab.com:dst_crypto/Crypto-bot-app.git
cd Crypto-bot-app

# Configurer l'environnement
cp .env.example .env
# Editer .env avec vos valeurs
```

## Environnement de developpement local

### Venv Python (lint + tests)

```bash
# Creer le venv a la racine du projet (Python 3.11 requis)
python3.11 -m venv .venv

# Activer le venv
source .venv/bin/activate

# Installer les dependances
pip install -r backend/requirements-dev.txt

# Installer les hooks pre-commit
pre-commit install
```

Le `.venv` est utilise par `make lint`, `make test` et le hook pre-commit.

### Lancer l'application

```bash
# Demarrer tous les services (charge automatiquement versions.env + .env)
make dev-up

# Verifier la sante du backend
make health

# Initialiser les buckets MinIO (premiere fois)
make dev-init

# Voir les logs
make dev-logs

# Arreter
make dev-down
```

> **Important** : le `Makefile` charge `versions.env` (versions d'images, tracke dans git)
> et `.env` (secrets, gitignore) via `include` + `export`. Utiliser `make` plutot que
> `docker compose` directement pour garantir la resolution de toutes les variables.

## Services (developpement local)

| Service | Port | URL |
|---------|------|-----|
| Backend API | 8009 | http://localhost:8009/api/v1/docs |
| Frontend | 8501 | http://localhost:8501 |
| PostgreSQL | 5434 | - |
| MinIO Console | 9001 | http://localhost:9001 |
| Adminer | 8085 | http://localhost:8085 |

## Tests et qualite

```bash
make test              # Tests unitaires (venv local)
make lint              # Verifier le code (ruff check + format)
make lint-fix          # Corriger automatiquement les erreurs ruff
make check-infra       # Valider coherence versions.env / Dockerfiles / docker-compose
make health            # Verifier la sante du backend (PORT=9009 make health pour prod)
```

### Pre-commit hooks

Les hooks sont configures dans `.pre-commit-config.yaml` :

| Hook | Declencheur | Action |
|------|------------|--------|
| trailing-whitespace, end-of-file, check-yaml/toml/json | Tous fichiers | Qualite basique |
| ruff check + format | `backend/src/` ou `frontend/src/` | Lint Python |
| semgrep | Fichiers Python | Scan securite |
| check-infra | Dockerfile, docker-compose, Makefile, versions.env, requirements, pyproject.toml | Validation infra (8 checks) |
| run-tests | `backend/src/**/*.py` ou `frontend/src/**/*.py` | `make lint` + `make test` |

## Workflow CI/CD

### Branches et merge requests

```
feature/* ou dev_*                                   Branches de travail
    |
    |  push --> CI : lint seul (feedback rapide)
    |
    |  MR (0 approbation requise)
    v
staging                                              Integration
    |
    |  MR --> CI : lint + build + test
    |  push --> CI : build + test + deploy VM AWS
    |
    |  MR (1+ approbation requise)
    v
main                                                 Branche stable (pas de pipeline)
    |
    |  tag vX.X --> CI : build + deploy production (manuel)
    v
tag vX.X                                             Release
```

### Stages du pipeline

| Stage | Jobs | Declencheur |
|-------|------|-------------|
| lint | `lint:versions`, `lint:python`, `lint:dockerfile:*`, `semgrep_sast` | MR, dev_\*, feature/\* |
| build | `build:docker`, `scan:images`, `validate_tag` | MR, staging, tag vX.X |
| test | `test:integration` | MR, staging, tag vX.X |
| deploy | `deploy:staging`, `deploy:production`, `create_release`, `update:manifests` | staging / tag vX.X |

### Tags des images Docker

| Declencheur | Tags pushes |
|-------------|-------------|
| MR | `:test-<pipeline_id>` + `:latest` |
| Branche `staging` | `:staging` + `:latest` |
| Tag `vX.X` | `:vX.X` + `:production` + `:latest` |

Les images sont pushees sur `registry.gitlab.com/dst_crypto/crypto-bot-app/backend` et `.../frontend`.

### Variables CI/CD requises

| Variable | Niveau | Description |
|----------|--------|-------------|
| `GROUP_PAT_TOKEN` | Groupe dst_crypto | PAT avec scope `write_repository` |
| `SSH_PRIVATE_KEY` | Projet Crypto-bot-app | Cle SSH privee pour deployer sur la VM AWS |
| `VM_HOST` | Projet Crypto-bot-app | IP de la VM AWS |
| `SSH_USER` | Projet Crypto-bot-app | Utilisateur SSH |

## Infrastructure Kubernetes (Talos / ArgoCD)

L'environnement principal de deploiement est un cluster Kubernetes Talos installe sur
Proxmox (3 noeuds : 1 control plane + 2 workers).

### Composants du cluster

| Composant | Version | Role |
|-----------|---------|------|
| Talos Linux | - | OS Kubernetes immutable |
| MetalLB | v0.14.9 | Load balancer L2 (pool 10.10.0.240-250) |
| Ingress NGINX | v1.12.0 | Ingress controller |
| local-path-provisioner | v0.0.30 | StorageClass par defaut |
| Sealed Secrets | v0.29.0 | Gestion des secrets chiffres dans Git |
| ArgoCD | - | GitOps : deploiement depuis Crypto-bot-infra |
| Loki + Promtail + Grafana | - | Monitoring et logs centralises (namespace `monitoring`) |

### Environnements Kubernetes

| Namespace | Source image | Sync ArgoCD | Acces |
|-----------|-------------|-------------|-------|
| `dev` | `:dev` (build local) | - | Port-forward uniquement |
| `staging` | `:staging` (CI) | Auto-sync | Port-forward / Tailscale |
| `production` | `:vX.X` / `:production` (CI) | Sync manuel | Port-forward / Tailscale |

ArgoCD surveille le repo `Crypto-bot-infra` et applique les manifestes Kustomize.
En staging, les changements sont appliques automatiquement. En production, un sync
manuel est requis pour valider le deploiement.

## VM AWS DataScientest (fallback)

La VM AWS est conservee en tant qu'environnement de fallback. La CI deploie en parallele
sur la VM et sur le cluster K8s.

| Environnement | Repertoire | Compose file | Ports |
|---------------|------------|--------------|-------|
| Staging | `/opt/crypto-bot-staging` | `docker-compose.staging.yml` | Backend 8009, Frontend 8501, PostgreSQL 5434, MinIO 9000/9001, Adminer 8085 |
| Production | `/opt/crypto-bot-prod` | `docker-compose.prod.yml` | Backend 9009, Frontend 8502, PostgreSQL 5435, MinIO 9002/9003, Adminer 8086* |

\* En production, Adminer est sous le profile `debug` et ne demarre pas par defaut.
Pour les activer ponctuellement : `make prod-debug-up` / `make prod-debug-down`.

## Scripts utilitaires

| Script | Description |
|--------|-------------|
| `scripts/check-infra.sh` | Validation coherence infra (8 checks) |
| `scripts/run-tests-if-needed.sh` | Pre-commit : lint + tests si code Python modifie |
| `scripts/dev-deploy.sh` | Build + push + restart K8s namespace dev |
| `scripts/docker_status.sh` | Statut des containers Docker |

## Commandes Makefile

Taper `make` pour afficher toutes les commandes disponibles.

| Commande | Description |
|----------|-------------|
| `make dev-up` | Demarrer l'env dev |
| `make dev-down` | Arreter l'env dev |
| `make dev-logs` | Suivre les logs dev |
| `make dev-config` | Valider la config dev |
| `make dev-build` | Rebuild les images dev (sans cache) |
| `make dev-init` | Creer les buckets MinIO (dev) |
| `make staging-up` | Demarrer staging |
| `make staging-down` | Arreter staging |
| `make staging-config` | Valider la config staging |
| `make staging-logs` | Suivre les logs staging |
| `make staging-init` | Creer les buckets MinIO (staging) |
| `make prod-up` | Demarrer la prod |
| `make prod-down` | Arreter la prod |
| `make prod-config` | Valider la config prod |
| `make prod-logs` | Suivre les logs prod |
| `make prod-init` | Creer les buckets MinIO (prod) |
| `make prod-debug-up` | Activer Adminer en prod |
| `make prod-debug-down` | Desactiver Adminer en prod |
| `make test` | Tests unitaires (venv local) |
| `make lint` | Ruff check + format |
| `make lint-fix` | Corriger automatiquement |
| `make check-infra` | Valider coherence infra |
| `make health` | Verifier la sante du backend |

## Monitoring

Loki, Promtail et Grafana sont deployes dans le namespace `monitoring` du cluster K8s.
Promtail collecte les logs de tous les pods, Loki les stocke, et Grafana fournit une
interface de visualisation et d'alerte.

## Depannage

### Erreur "No module named 'src'"

```bash
# Le PYTHONPATH est gere automatiquement par make test
# Pour lancer pytest manuellement :
PYTHONPATH=backend/src .venv/bin/pytest backend/src/tests -v
```

### Les containers ne demarrent pas

```bash
make dev-logs          # Voir les logs
make dev-build         # Reconstruire les images
make dev-up            # Relancer
```

### Le cluster K8s ne repond pas

```bash
# Verifier que Tailscale est connecte avec les routes acceptees
tailscale status
tailscale up --accept-routes

# Tester la connexion au cluster
kubectl --context admin@crypto-bot get nodes
```
