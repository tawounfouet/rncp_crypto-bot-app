# Crypto-Bot App

Statut: référence
Derniere revision: 2026-07-28

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
│   ├── run-tests-if-needed.sh  # Pre-commit : lint + tests cibles si code modifie
│   ├── dev-deploy.sh           # Build + push + restart K8s namespace dev (outil perso)
│   └── generate-requirements.py # Compilation des requirements depuis versions.env
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

## Demarrage rapide

```bash
git clone git@gitlab.com:dst_crypto/Crypto-bot-app.git
cd Crypto-bot-app
cp .env.example .env   # puis editer .env avec vos valeurs

make dev-up            # demarre tous les services (charge versions.env + .env)
make dev-init           # premiere fois : cree les buckets MinIO
make health             # verifie la sante du backend
```

Guide d'installation complet (venv, hooks pre-commit, tests, lint, workflow Git/CI,
depannage) : **[docs/01-setup.md](docs/01-setup.md)**.

## Services (developpement local)

Backend : http://localhost:8009/api/v1/docs — Frontend : http://localhost:8501

Liste complete des ports (dev/staging/prod, VM AWS, port-forward K8s) : voir
[docs/01-setup.md](docs/01-setup.md#services-par-environnement-vm-aws).

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

## VM AWS Liora (fallback)

La VM AWS est conservee en tant qu'environnement de fallback. La CI deploie en parallele
sur la VM et sur le cluster K8s.

| Environnement | Repertoire | Compose file |
|---------------|------------|--------------|
| Staging | `/opt/crypto-bot-staging` | `docker-compose.staging.yml` |
| Production | `/opt/crypto-bot-prod` | `docker-compose.prod.yml` |

Ports detailles : voir [docs/01-setup.md](docs/01-setup.md#services-par-environnement-vm-aws).
En production, Adminer est sous le profile `debug` et ne demarre pas par defaut.
Pour les activer ponctuellement : `make prod-debug-up` / `make prod-debug-down`.

## Scripts utilitaires

| Script | Description |
|--------|-------------|
| `scripts/check-infra.sh` | Validation coherence infra (10 checks) |
| `scripts/run-tests-if-needed.sh` | Pre-commit : lint + tests cibles sur les zones modifiees |
| `scripts/dev-deploy.sh` | Build + push + restart K8s namespace dev (outil perso) |
| `scripts/generate-requirements.py` | Compilation des requirements depuis versions.env |

## Monitoring

Loki, Promtail et Grafana sont deployes dans le namespace `monitoring` du cluster K8s.
Promtail collecte les logs de tous les pods, Loki les stocke, et Grafana fournit une
interface de visualisation et d'alerte.

## Pour aller plus loin

| Document | Contenu |
|----------|---------|
| [docs/01-setup.md](docs/01-setup.md) | Installation complete, commandes Makefile, workflow Git/CI, gestion des versions, depannage |
| [docs/02-interfaces.md](docs/02-interfaces.md) | Carte des interfaces et contrats entre services (frontend, backend, DB, exchanges, Airflow, ML, MinIO) |
| [docs/03-architecture-data-ml.md](docs/03-architecture-data-ml.md) | Flux de donnees Binance -> MinIO -> ML -> backend |
| [docs/04-architecture-db.md](docs/04-architecture-db.md) | Schema de la base de donnees (tables, vues, index) |
| [docs/05-multi-exchange-layer.md](docs/05-multi-exchange-layer.md) | Abstraction multi-exchange (drivers de marche, clients d'execution) |
