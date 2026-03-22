# Crypto-Bot App

Projet de trading automatise de cryptomonnaies — monorepo applicatif (backend + frontend).

## Architecture

```
Crypto-bot-app/                 # Monorepo applicatif
├── backend/                    # Code FastAPI
│   ├── src/
│   ├── Dockerfile
│   └── requirements.txt
├── frontend/                   # Code Streamlit
│   ├── src/
│   ├── Dockerfile
│   └── requirements.txt
├── scripts/
│   ├── push.sh                 # Push sur le remote
│   ├── dev-deploy.sh           # Build + push + restart K8s namespace dev
│   ├── run_lint.sh             # Linting local
│   └── run_tests.sh            # Tests locaux
├── docker-compose.yml          # Developpement local
├── docker-compose.staging.yml  # Environnement staging (VM AWS)
├── docker-compose.prod.yml     # Environnement production (VM AWS)
├── .gitlab-ci.yml              # CI/CD
└── README.md
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

## Lancement local

```bash
# Demarrer tous les services
docker compose up -d

# Voir les logs
docker compose logs -f

# Arreter
docker compose down
```

## Services (developpement local)

| Service | Port | URL |
|---------|------|-----|
| Backend API | 8009 | http://localhost:8009/docs |
| Frontend | 8501 | http://localhost:8501 |
| PostgreSQL | 5434 | - |
| MongoDB | 27017 | - |
| MinIO Console | 9001 | http://localhost:9001 |
| Adminer | 8085 | http://localhost:8085 |
| Mongo Express | 8081 | http://localhost:8081 |

## Workflow CI/CD

### Branches et merge requests

```
feature/* ou dev_*                                   Branches de travail
    |
    |  push --> CI : lint + tests
    |
    |  MR (0 approbation requise)
    v
staging                                              Integration
    |
    |  push --> CI : lint + tests + build + deploy VM AWS
    |
    |  MR (1+ approbation requise)
    v
main                                                 Branche stable
    |
    |  tag vX.X --> CI : build + deploy production (manuel)
    v
tag vX.X                                             Release
```

### Tags des images Docker

Les images sont taguees selon la branche ou le tag Git :

| Declencheur | Tags pushes |
|-------------|-------------|
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
| Staging | `/opt/crypto-bot-staging` | `docker-compose.staging.yml` | Backend 8009, Frontend 8501, PostgreSQL 5434, MongoDB 27017, MinIO 9000/9001 |
| Production | `/opt/crypto-bot-prod` | `docker-compose.prod.yml` | Backend 9009, PostgreSQL 5435, MongoDB 27018, MinIO 9002/9003 |

## Scripts utilitaires

### `scripts/push.sh` -- Push sur le remote

```bash
./scripts/push.sh                # Push la branche courante
./scripts/push.sh feature/auth   # Push une branche specifique
```

### `scripts/dev-deploy.sh` -- Build + deploy K8s dev

Build les images Docker, les pousse sur le registry GitLab avec le tag `:dev`, et
redemarre les pods dans le namespace `dev` du cluster K8s.

```bash
./scripts/dev-deploy.sh           # Build et deploy backend + frontend
./scripts/dev-deploy.sh backend   # Backend uniquement
./scripts/dev-deploy.sh frontend  # Frontend uniquement
```

Prerequis : `docker login registry.gitlab.com` et acces au cluster (Tailscale ou tunnel SSH).

## Monitoring

Loki, Promtail et Grafana sont deployes dans le namespace `monitoring` du cluster K8s.
Promtail collecte les logs de tous les pods, Loki les stocke, et Grafana fournit une
interface de visualisation et d'alerte.
