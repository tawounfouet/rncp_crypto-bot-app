# Guide d'installation - Crypto-Bot App

Statut: référence
Derniere revision: 2026-07-28

## Architecture du projet

```
Crypto-bot-app/                 # Monorepo applicatif
├── backend/                    # Code FastAPI
│   ├── src/                    # Code source + tests
│   ├── ci/                     # parse_test_report.py (inclus dans l'image test Docker)
│   ├── Dockerfile              # Multi-stage : builder, test, runtime
│   ├── requirements.txt        # Dependances de production
│   └── requirements-dev.txt    # Dependances de dev/test (inclut requirements.txt)
├── frontend/                   # Code Streamlit (mock-first multi-pages)
│   ├── src/                    # app.py + pages/ + components/ + services/ + ...
│   ├── tests/                  # unit + integration + smoke
│   ├── Dockerfile
│   ├── pyproject.toml          # Config pytest + ruff specifique frontend
│   └── requirements.txt        # Deps runtime (streamlit, plotly, pandas, pydantic)
├── ci/                         # Tests d'integration CI
│   ├── docker-compose.test.yml # Compose pour tests (Postgres reel)
│   └── test-results/           # Rapports JUnit/Cobertura (trackes pour tracabilite)
├── scripts/
│   ├── check-infra.sh          # Validation coherence versions.env / Dockerfiles (10 checks)
│   ├── run-tests-if-needed.sh  # Pre-commit : lint + tests cibles si code Python modifie
│   ├── dev-deploy.sh           # Build + push + restart K8s namespace dev (outil perso)
│   └── generate-requirements.py # Compilation des requirements depuis versions.env
├── .semgrep/                   # Regles de securite Semgrep
├── init-scripts/               # Scripts d'init PostgreSQL
├── docker-compose.yml          # Dev local
├── docker-compose.staging.yml  # Staging (VM AWS)
├── docker-compose.prod.yml     # Production (VM AWS)
├── versions.env                # Versions des images Docker (source unique, tracke dans git)
├── .env.example                # Template des variables d'environnement (secrets)
├── Makefile                    # Raccourcis dev locaux (charge versions.env), taper `make`
├── pyproject.toml              # Configuration Ruff (linting + formatting)
├── .pre-commit-config.yaml     # Hooks pre-commit (ruff, semgrep, check-infra, tests)
└── .gitlab-ci.yml              # CI/CD
```

**Deploiement principal** : cluster Kubernetes (Talos) via ArgoCD.
Les fichiers `docker-compose.*.yml` servent uniquement pour le dev local et comme
fallback sur la VM AWS Liora.

## Prerequis

- Git >= 2.13
- Docker >= 20.10
- Docker Compose >= 2.0
- Python 3.11.x (aligne sur `PYTHON_CI_IMAGE=python:3.11.15-slim` dans `versions.env` —
  c'est l'image utilisee par la CI pour lint et tests, garder son venv local sur la
  meme version mineure evite les ecarts "ca passe chez moi / ca casse en CI")
- pre-commit (pour les hooks)
- kubectl (pour le deploiement K8s dev)
- kubeseal (pour la gestion des secrets K8s)

> **Windows** : tout ce guide fonctionne aussi bien en PowerShell qu'en Git Bash / WSL2.
> Les seules differences sont l'emplacement des executables dans le venv
> (`.venv/bin/...` sous Linux/macOS/WSL vs `.venv/Scripts/...` sous PowerShell natif)
> et la syntaxe d'activation — chaque commande ci-dessous donne les deux variantes.

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

# MinIO
MINIO_USER_ADMIN=minioadmin
MINIO_PWD_ADMIN=your_minio_password

# Chiffrement des cles API exchange (Binance, Kraken, ...) en BDD
# Generer avec : python -c "import os,base64; print(base64.b64encode(os.urandom(32)).decode())"
EXCHANGE_ENC_KEY=your_base64_encoded_32_byte_key
```

### 3. Creer le venv local (tests + lint)

Le `.venv` racine est **partage entre backend, frontend et models** (un seul
Python 3.11). Cela evite de jongler avec plusieurs venvs en dev local. En prod,
l'isolation est garantie par les images Docker separees (backend / frontend /
ml-api), pas besoin de la dupliquer ici.

La creation et l'installation des dependances sont identiques partout ; seul le
**chemin des executables** dans le venv change selon l'OS :

| OS | Chemin Python du venv |
|----|------------------------|
| Linux / macOS / WSL2 | `.venv/bin/python` |
| Windows (PowerShell / cmd) | `.venv\Scripts\python.exe` |
| Windows (Git Bash) | `.venv/Scripts/python.exe` |

**Linux / macOS / WSL2 :**

```bash
python3.11 -m venv .venv

# Deps backend (FastAPI, SQLAlchemy, PyJWT, pytest, ruff, ...)
.venv/bin/python -m pip install -r backend/requirements-dev.txt

# Deps frontend (Streamlit, Plotly, Pandas, Pydantic v2)
.venv/bin/python -m pip install -r frontend/requirements.txt

# Deps models (scikit-learn, torch, mlflow, matplotlib, ...)
.venv/bin/python -m pip install -r models/requirements-dev.txt
```

**Windows (PowerShell) :**

```powershell
py -3.11 -m venv .venv

.\.venv\Scripts\python.exe -m pip install -r backend\requirements-dev.txt
.\.venv\Scripts\python.exe -m pip install -r frontend\requirements.txt
.\.venv\Scripts\python.exe -m pip install -r models\requirements-dev.txt
```

**Windows (Git Bash) :**

```bash
py -3.11 -m venv .venv

.venv/Scripts/python.exe -m pip install -r backend/requirements-dev.txt
.venv/Scripts/python.exe -m pip install -r frontend/requirements.txt
.venv/Scripts/python.exe -m pip install -r models/requirements-dev.txt
```

> Si `uv` est installe, prefere `uv pip install --python <chemin-python-ci-dessus> -r ...`
> (10x plus rapide, resolution deterministe) — le chemin du Python cible depend de
> l'OS comme indique dans le tableau ci-dessus.

`pytest` et `ruff` sont fournis par `backend/requirements-dev.txt` ; ils
servent aussi aux tests / lint du frontend (pas besoin d'un install dev separe
cote frontend). Ce sont les memes fichiers `requirements-dev.txt` /
`requirements.txt` qu'installe la CI (job `.python_job` / `lint:python` dans
`.gitlab-ci.yml`, sur l'image `$PYTHON_CI_IMAGE`) : un venv local cree avec cette
procedure a donc les memes versions que celles qui font foi en CI.

Le `.venv` est utilise par `make lint`, `make test`, `make test-backend`,
`make test-frontend` et le hook pre-commit `run-tests-if-needed.sh`. Ces trois
outils **detectent automatiquement** le bon chemin d'executable Python
(`.venv/bin/python` ou `.venv/Scripts/python.exe`) — vous n'avez jamais besoin
d'adapter une commande `make` selon votre OS, seule la creation initiale du venv
ci-dessus differe.

### 4. Installer les hooks pre-commit

```bash
pre-commit install
```

Les hooks verifient automatiquement avant chaque commit :
- Qualite basique (trailing whitespace, YAML/JSON valide, merge conflicts)
- Ruff lint + format (si fichiers Python modifies)
- Semgrep securite (si fichiers Python modifies)
- Validation infra (si Dockerfile/docker-compose/versions.env modifies)
- Tests unitaires (si code applicatif modifie)

### 5. Lancer l'application (dev local avec Docker Compose)

```bash
# Demarrer tous les services (charge automatiquement versions.env + .env)
make dev-up

# Verifier la sante du backend
make health

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
| MinIO Console | http://localhost:9001 |
| ml-api | http://localhost:8010 |
| mlflow-ui | http://localhost:5001 |
| Airflow UI | http://localhost:8080 (admin / admin) |

## Developpement

### Lancer les tests

```bash
# Tous les tests (backend + frontend + utils + jobs + models)
make test

# Backend uniquement
make test-backend

# Frontend uniquement (Streamlit)
make test-frontend

# Autres composants
make test-utils
make test-jobs
make test-models
```

Equivalents manuels (remplacer `<python-venv>` par le chemin du tableau de
l'etape 3 : `.venv/bin/python` sous Linux/macOS/WSL2, `.venv\Scripts\python.exe`
ou `.venv/Scripts/python.exe` sous Windows) :

```bash
# Backend
PYTHONPATH=backend/src <python-venv> -m pytest backend/tests -v

# Frontend (depuis frontend/ pour respecter le pythonpath de frontend/pyproject.toml)
cd frontend && ../<python-venv> -m pytest tests -q
```

> `make test-backend`/`make test-frontend` et `run-tests-if-needed.sh` font deja
> cette resolution de chemin automatiquement (variable `VENV_PYTHON` dans le
> `Makefile`) : preferer `make` au quotidien, ces commandes manuelles servent
> surtout au debug.

### Lancer le linting

```bash
# Verifier le code (ruff check + format)
make lint

# Auto-corriger les erreurs
make lint-fix

# Valider la coherence infra (versions.env, Dockerfiles, docker-compose)
make check-infra
```

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
| MinIO      | 9000/9001  | 9100/9101  | 9200/9201  |

## Workflow Git

### Branches et workflow

```
feature/* ou dev_*  --(MR, 0 approbation)-->  staging  --(MR, 1+ approbation)-->  main  --(tag)-->  vX.X
```

- **feature/\* ou dev_\*** : branches de travail. Lint seul a chaque push (feedback rapide).
- **staging** : branche d'integration. Merge Request sans approbation requise.
  Declenche build, test et deploy.
- **main** : branche de production. Merge Request avec au moins 1 approbation.
- **tag vX.X** : cree sur `main` pour declencher le build et le deploy production.

### Stages du pipeline

| Stage | Jobs | Declencheur |
|-------|------|-------------|
| lint | `lint:versions`, `lint:python`, `lint:dockerfile:*`, `semgrep_sast` | MR, dev_\*, feature/\* |
| build | `build:docker`, `scan:images`, `validate_tag` | MR, staging, tag vX.X |
| test | `test:integration` | MR, staging, tag vX.X |
| deploy | `deploy:staging`, `deploy:production`, `create_release`, `update:manifests` | staging / tag vX.X |

### Tags Docker

La CI ne genere que des tags nommes, pas de tags SHA :

| Declencheur | Tags generes |
|-------------|--------------|
| MR | `:test-<pipeline_id>` + `:latest` |
| Push sur staging | `:staging` + `:latest` |
| Tag vX.X | `:vX.X` + `:production` + `:latest` |

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
   deployes sur la VM Liora comme solution de repli si le
   cluster K8s est indisponible.

Le deploiement principal se fait sur le cluster Kubernetes Talos via ArgoCD
(repo `Crypto-bot-infra`).

> **Ne pas utiliser `docker compose` directement.** Les versions d'images sont
> dans `versions.env`, charge automatiquement par le `Makefile`. Utiliser
> `make dev-up`, `make staging-up`, etc. Taper `make` pour voir toutes les commandes.

### Gestion des versions d'images

Les versions d'images Docker sont centralisees dans `versions.env` (tracke dans git) :

```env
POSTGRES_IMAGE=postgres:14
ADMINER_IMAGE=adminer
# ...
```

Les docker-compose referent ces versions via `${POSTGRES_IMAGE}`, etc.
Le `Makefile` et la CI chargent ce fichier automatiquement.

Pour mettre a jour une version :
1. Modifier `versions.env`
2. Tester avec `make dev-config` / `make staging-config` / `make prod-config`
3. Committer et pousser

### Ajouter ou mettre a jour une dependance Python

> **Ne jamais editer `requirements.txt` directement** : ces fichiers sont
> *generes* a partir de `versions.env` + des templates `*.template` par
> `scripts/generate-requirements.py` (lance automatiquement par `make dev-up`,
> `make dev-build`, `make staging-up`, `make prod-up`...). Toute ligne ajoutee a
> la main dans un `requirements.txt` est ecrasee a la regeneration.

Procedure propre :
1. Ajouter la version dans `versions.env` : `MA_LIB_VERSION=x.y.z`
2. Ajouter le paquet dans le(s) template(s) concerne(s) avec le placeholder :
   `ma-lib==$MA_LIB_VERSION`. Templates disponibles :
   - `backend/requirements.txt.template` (API FastAPI)
   - `frontend/requirements.txt.template` (app Streamlit)
   - `jobs/requirements.txt.template` (jobs batch, tournent dans l'image Airflow)
   - `orchestration/requirements.txt.template` (DAGs Airflow)
   - `models/requirements.txt.template` (entrainement ML, conteneur ml-api)
3. Regenerer : `make generate-requirements` (ou `make dev-config`)
4. Committer `versions.env`, le `*.template` **et** le `requirements.txt` regenere
   (les trois doivent rester coherents).

**Dependances partagees backend <-> models** : `SCIKIT_LEARN_VERSION` et
`JOBLIB_VERSION` dans `versions.env` pinent la **meme** version pour le backend
(inference, chargement joblib/pickle) et pour `models/` (entrainement).
`models/pyproject.toml` ne declare **aucune** dependance runtime (metadata de
build uniquement) : la seule source de verite est `requirements.txt`, genere
depuis `versions.env`. Un bump de sklearn/joblib doit donc etre teste ensemble
cote backend et models, sinon risque de mismatch train<->inference
(`InconsistentVersionWarning` sklearn).

### Commandes Makefile

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
| `make test` | Tous les tests (backend + frontend + utils + jobs + models) |
| `make test-backend` | Tests unitaires backend |
| `make test-frontend` | Tests frontend mock-first (Streamlit) |
| `make lint` | Ruff check + format |
| `make lint-fix` | Corriger automatiquement |
| `make check-infra` | Valider coherence infra |
| `make health` | Verifier la sante du backend |

### Services par environnement (VM AWS)

Staging et Production cohabitent sur la meme VM : convention `Prod = Staging + 1` sur
tous les ports externes. MinIO API et Console sont volontairement dans des dizaines
distinctes (9000s / 9010s) pour eviter la confusion entre "prod du port API" et
"console" quand on applique +1.

| Service | Dev | Staging | Prod |
|---------|-----|---------|------|
| Backend | 8009 | 8009 | 8010 |
| Frontend | 8501 | 8501 | 8502 |
| PostgreSQL | 5434 | 5434 | 5435 |
| MinIO API | 9000 | 9000 | 9001 |
| MinIO Console | 9001 | 9010 | 9011 |
| Adminer | 8085 | 8085 | 8086 (profile debug) |
| ml-api | 8010 | 8020 | 8021 |
| mlflow-ui | 5001 | 5001 | 5002 |
| Airflow webserver | 8080 | 8080 | 8081 |

En production, Adminer ne demarre pas par defaut (profile `debug`).
Le service `createbuckets` est sous le profile `tools` dans tous les environnements.

## Depannage

### Erreur "No module named 'src'"

```bash
# Le PYTHONPATH est gere automatiquement par make test
# Pour lancer pytest manuellement (remplacer <python-venv> selon l'OS, cf. etape 3) :
PYTHONPATH=backend/src <python-venv> -m pytest backend/tests -v
```

### Windows : `PytestCacheWarning` / `[WinError 267] Nom de repertoire non valide`

Symptome (frontend, tests lances depuis un dossier synchronise type OneDrive, ou
un chemin de projet tres long/imbrique) :

```
PytestCacheWarning: could not create cache path ... .pytest_cache\v\cache\nodeids:
[WinError 267] Nom de répertoire non valide: '...\pytest-cache-files-...\.gitignore'
```

Cause : pytest cree et nettoie des dossiers temporaires `pytest-cache-files-*`
dans `.pytest_cache/` a la racine du projet frontend ; certains environnements
Windows (synchronisation OneDrive active sur le dossier, chemin trop long,
antivirus qui verrouille un fichier pendant le cleanup) empechent cette
creation/suppression. Ce n'est pas un bug general de Windows — la plupart des
setups Windows n'y sont jamais confrontes — donc **pas de contournement dans la
config partagee** (`frontend/pyproject.toml`) : un `cache_dir` en dur type
`%TEMP%/...` y a deja ete tente et cassait les tests sous Linux/macOS (pytest
n'expanse `%VAR%` que via `ntpath.expandvars`, pas sous POSIX — le dossier
`%TEMP%` etait alors cree littéralement).

Corrections locales, a essayer dans l'ordre :
1. Sortir le clone du dossier synchronise OneDrive (ou mettre le dossier du
   projet en exclusion de synchronisation).
2. Raccourcir le chemin du projet (eviter les repertoires trop imbriques).
3. Si le probleme persiste, rediriger le cache pytest **localement** en creant
   `frontend/pytest.ini` (prioritaire sur `pyproject.toml`, donc pas besoin de
   modifier ce dernier) avec un chemin Windows absolu explicite, sans variable
   `%...%` :
   ```ini
   [pytest]
   cache_dir = C:/Users/<vous>/AppData/Local/Temp/crypto-bot-app-pytest-cache
   ```
   **Ne pas commiter ce fichier** — c'est un reglage propre a votre poste,
   pas a la config partagee de l'equipe.

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
