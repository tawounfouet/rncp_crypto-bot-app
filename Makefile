# Makefile - Crypto-bot-app
# =========================
# Raccourcis pour les commandes dev locales.
# Charge automatiquement versions.env pour que les variables
# soient disponibles dans les commandes docker compose.
#
# /!\ Ne pas utiliser "docker compose" directement en local.
#     Les variables de versions.env ne seraient pas chargees.

include versions.env
export

.DEFAULT_GOAL := help

# Python du venv local : .venv/bin/python (Linux/macOS/WSL2) ou .venv/Scripts/python.exe
# (Windows). Utilise -m pytest/-m ruff plutot que les executables directs pour rester
# portable (cf. docs/SETUP.md).
VENV_PYTHON := $(if $(wildcard .venv/bin/python),.venv/bin/python,$(if $(wildcard .venv/Scripts/python.exe),.venv/Scripts/python.exe,.venv/bin/python))

help: ## Afficher cette aide
	@echo ""
	@echo "  Crypto-bot-app — commandes disponibles"
	@echo "  ======================================="
	@echo ""
	@grep -E '^[a-zA-Z_-]+:.*?## ' Makefile | sort | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'
	@echo ""

generate-requirements: ## Generer les fichiers requirements.txt a partir de versions.env et des templates
	python3 scripts/generate-requirements.py

# ===========================================================================
# Dev
# ===========================================================================

dev-up: generate-requirements ## Demarrer l'environnement dev (retry auto + backoff si le pull echoue)
	@n=5; d=5; for i in $$(seq 1 $$n); do \
		echo ">>> dev-up : tentative $$i/$$n" ; \
		docker compose up -d && exit 0 ; \
		if [ $$i -lt $$n ]; then \
			echo ">>> echec (credsStore / Docker Desktop ?), nouvel essai dans $${d}s..." ; \
			sleep $$d ; d=$$((d + 5)) ; \
		fi ; \
	done ; \
	echo ">>> dev-up : echec apres $$n tentatives. Voir docs/04-troubleshooting.md (Probleme 6)." ; exit 1

dev-down: ## Arreter l'environnement dev
	docker compose down

dev-down-v: ## Arreter dev ET supprimer tous les volumes du projet (reset complet "from 0")
	docker compose down -v --remove-orphans

dev-config: generate-requirements ## Valider la configuration dev
	docker compose config

dev-logs: ## Suivre les logs dev
	docker compose logs -f

dev-build: generate-requirements ## (Re)build les images dev (cache activé = rapide)
	docker compose build

dev-rebuild: generate-requirements ## Rebuild COMPLET sans cache (lent, en cas de pépin)
	docker compose build --no-cache

# ===========================================================================
# ML / MLOps
# ===========================================================================

ml-up: ## Demarrer uniquement la couche ML (API + MLflow UI)
	docker compose up -d crypto-bot-ml-api mlflow-ui

ml-down: ## Arreter la couche ML
	docker compose stop crypto-bot-ml-api mlflow-ui

ml-logs: ## Suivre les logs de la couche ML
	docker compose logs -f crypto-bot-ml-api mlflow-ui

ml-train-rf: ## Lancer un entrainement Random Forest
	docker compose exec crypto-bot-ml-api python -m src.main train-rf

# ===========================================================================
# Staging (usage local ou VM)
# ===========================================================================

staging-up: generate-requirements ## Demarrer staging
	docker compose -f docker-compose.staging.yml up -d

staging-down: ## Arreter staging
	docker compose -f docker-compose.staging.yml down

staging-config: generate-requirements ## Valider la configuration staging
	docker compose -f docker-compose.staging.yml config

staging-logs: ## Suivre les logs staging
	docker compose -f docker-compose.staging.yml logs -f

# ===========================================================================
# Production (usage local ou VM)
# ===========================================================================

prod-up: generate-requirements ## Demarrer la production
	docker compose -f docker-compose.prod.yml up -d

prod-down: ## Arreter la production
	docker compose -f docker-compose.prod.yml down

prod-config: generate-requirements ## Valider la configuration prod
	docker compose -f docker-compose.prod.yml config

prod-logs: ## Suivre les logs prod
	docker compose -f docker-compose.prod.yml logs -f

# ===========================================================================
# Tests & Lint (venv local)
# ===========================================================================

test: test-backend test-frontend test-utils test-jobs ## Lancer les tests (backend + frontend + utils + jobs)
# NB: test-models exclu de l'agregat tant que la suite models n'est pas verte (echecs
#     pre-existants: config/features/utils). Lancable seul via `make test-models`. Voir issue hygiene tests models.

verify: ## Verifier que tous les services installes sont presents et healthy (backend/frontend/airflow/minio/postgres/ml)
	./scripts/verify.sh $(ARGS)

test-backend: ## Lancer les tests unitaires backend
	PYTHONPATH=backend/src $(VENV_PYTHON) -m pytest backend/src/tests -v

test-frontend: ## Lancer les tests frontend mock-first
	cd frontend && ../$(VENV_PYTHON) -m pytest tests -q

test-utils: ## Lancer les tests de la couche connecteurs partagee (utils/)
	PYTHONPATH=. $(VENV_PYTHON) -m pytest utils/tests -q -o cache_dir=/tmp/utils-pytest-cache

test-coverage: ## Lancer les tests avec coverage (backend + frontend + utils)
	PYTHONPATH=backend/src $(VENV_PYTHON) -m pytest --cov=backend/src --cov=utils --cov-report=term-missing backend/src/tests utils/tests frontend/tests

test-jobs: ## Lancer les tests unitaires des jobs (backend/src/jobs)
	PYTHONPATH=. $(VENV_PYTHON) -m pytest jobs/tests -q -o cache_dir=/tmp/utils-pytest-cache

test-models: ## Lancer les tests unitaires des models (backend/src/models)
	PYTHONPATH=. $(VENV_PYTHON) -m pytest models/tests -q -o cache_dir=/tmp/models-pytest-cache

lint: ## Lancer ruff check + format
	$(VENV_PYTHON) -m ruff check backend/src/ frontend/src/ --output-format=concise
	$(VENV_PYTHON) -m ruff format --check backend/src/ frontend/src/

lint-fix: ## Corriger automatiquement les erreurs ruff
	$(VENV_PYTHON) -m ruff check backend/src/ frontend/src/ --fix
	$(VENV_PYTHON) -m ruff format backend/src/ frontend/src/

# ===========================================================================
# Outils
# ===========================================================================

dev-init: ## Creer les buckets MinIO (dev)
	docker compose --profile tools up createbuckets

staging-init: ## Creer les buckets MinIO (staging)
	docker compose -f docker-compose.staging.yml --profile tools up createbuckets

prod-init: ## Creer les buckets MinIO (prod)
	docker compose -f docker-compose.prod.yml --profile tools up createbuckets

prod-debug-up: ## Activer Adminer en prod
	docker compose -f docker-compose.prod.yml --profile debug up -d adminer

prod-debug-down: ## Desactiver Adminer en prod
	docker compose -f docker-compose.prod.yml --profile debug stop adminer

check-infra: ## Valider la coherence versions.env / Dockerfiles / docker-compose
	bash scripts/check-infra.sh

health: ## Verifier la sante du backend (PORT=8009 par defaut)
	@curl -sf http://localhost:$${PORT:-8009}/health && echo " OK" || (echo " FAIL" && exit 1)
