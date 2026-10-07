# Crypto-Bot App

Statut: référence
Derniere revision: 2026-07-28

Projet de trading automatise de cryptomonnaies — monorepo **100 % Python** (backend FastAPI + frontend Streamlit + ML + jobs Airflow).

> ⚠️ **Avertissement sécurité.** Un audit complet (voir [`CODEBASE_ANALYSIS.md`](./CODEBASE_ANALYSIS.md)) a identifié des **endpoints non authentifiés destructifs ou d'exécution** (purge de comptes, exécution de déploiements, entraînement ML) ainsi que des **ports internes publiés** et la **lecture anonyme du bucket MinIO**. Ces routes sont joignables dès que le backend est exposé sur un réseau non fiable. **Ne pas déployer publiquement avant d'avoir appliqué la Phase 1 de [`RECOMMANDATIONS.md`](./RECOMMANDATIONS.md)** (auth centralisée, jeton de service, fermeture des ports internes).

## Documentation d'audit

| Document | Contenu |
|----------|---------|
| [CODEBASE_ANALYSIS.md](CODEBASE_ANALYSIS.md) | Faits : architecture, endpoints, bugs `B1…B14`, vulnérabilités `V1…V13`, dette |
| [ANALYSE_CRITIQUE.md](ANALYSE_CRITIQUE.md) | Verdict et critiques (sécurité, architecture, frontend, processus) |
| [RECOMMANDATIONS.md](RECOMMANDATIONS.md) | Plan de remédiation priorisé et correctifs prêts à l'emploi |
| [ARCHITECTURE.md](ARCHITECTURE.md) | Référence technique : flux, modèle de données, conventions |
| [INDEX.md](INDEX.md) | Sommaire et navigation par tâche |

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
├── models/                     # Entrainement ML + API ml-api (:8010) + MLflow
│   ├── src/
│   └── tests/
├── jobs/                       # Jobs batch Airflow (ingest -> MinIO, transform -> Postgres)
├── orchestration/              # DAGs Airflow + plugins
├── utils/                      # Package partage (connecteurs exchanges, MinIO, Postgres)
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

### Tests & lint (local)

```bash
make lint           # ruff check + format (ruff epingle dans le venv)
make test           # backend + frontend + utils + jobs + models
make test-backend   # ou test-frontend / test-utils / test-jobs / test-models
make ci-test        # rejoue le test d'integration CI (image Docker + Postgres reel)
```

> **Aucun couple de variables ne doit rester vide.** `JWT_SIGNING_KEY` est obligatoire
> au demarrage du backend ; `EXCHANGE_ENC_KEY` est requis pour chiffrer les identifiants
> d'echange. `.env.example` ne fournit que des placeholders de developpement.

## Mode démonstration (soutenance)

Un jeu de données déterministe et un environnement dédié permettent de dérouler un parcours
utilisateur complet sans dépendre d'un exchange réel (worker de bots désactivé).

> Guide complet (mise en place, déroulé, dépannage) : **[DEMO_SOUTENANCE.md](DEMO_SOUTENANCE.md)**.

```bash
make demo-up      # démarre la stack (surcharge docker-compose.demo.yml) + seed
make demo-seed    # (re)peuple uniquement le jeu de données
make demo-reset   # reset complet (volumes) puis redémarrage + seed
make demo-down    # arrête l'environnement de démonstration
```

Comptes créés par le seed :

| Compte | Email | Mot de passe |
|---|---|---|
| Utilisateur démo | `demo@cryptobot.dev` | `Demo12345!` |
| Administrateur | `admin@cryptobot.dev` | `Admin12345!` |

Le seed (`backend/scripts/seed_demo.py`) crée un exchange configuré (mode sandbox), 3 bots
verrouillés dans différents états, leurs décisions/ordres/trades/positions, ~60 jours de
bougies 1h (BTCUSDC/ETHUSDC), des backtests et un portefeuille Spot.

> **Dépendances live** : les pages *Marché* et *Portefeuille* interrogent l'exchange réel
> (prix publics, soldes) — elles nécessitent un accès réseau et des clés valides. Les autres
> écrans (Tableau de bord, Performances, Contrôle/Paramétrage de bots, Backtesting, Compte,
> Admin) sont entièrement servis par les données seedées.

## Variables d'environnement

Le fichier `.env` (non versionne) est la source des secrets ; `versions.env` est la source
unique des versions d'images. Les principales variables (voir `.env.example`) :

| Variable | Role |
|---|---|
| `JWT_SIGNING_KEY` | Cle de signature des JWT (obligatoire, distincte de `EXCHANGE_ENC_KEY`) |
| `EXCHANGE_ENC_KEY` | Chiffrement au repos des identifiants d'exchange |
| `CORS_ORIGINS` / `ALLOWED_HOSTS` | Origines CORS et hotes autorises (`TrustedHost`) |
| `POSTGRES_USER` / `POSTGRES_PWD` | Identifiants PostgreSQL |
| `MINIO_ROOT_USER` / `MINIO_ROOT_PASSWORD` | Identifiants MinIO (pas de valeur par defaut en prod) |
| `AIRFLOW_ADMIN_USER` / `_PASSWORD` / `_FERNET_KEY` / `_WEBSERVER_SECRET_KEY` | Airflow |
| `ML_API_URL` | URL du service ml-api (defaut conteneur `http://crypto-bot-ml-api:8010`) |

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
| [docs/06-testnet-simulation-modes.md](docs/06-testnet-simulation-modes.md) | Modes testnet / simulation |
| [docs/07-bot-strategy-architecture.md](docs/07-bot-strategy-architecture.md) | Architecture des bots et strategies (catalogue verrouille) |
| [docs/08-archi-mutualisation-data-layer.md](docs/08-archi-mutualisation-data-layer.md) | Mutualisation de la couche data |
| [INDEX.md](INDEX.md) | Sommaire des documents d'audit et navigation par tache |
