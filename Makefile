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
	python scripts/generate-requirements.py

# ===========================================================================
# Dev
# ===========================================================================

prepare-dirs: ## Corriger les permissions des dossiers bind-montes ecrits par des conteneurs non-root (uid different de l'hote)
	@mkdir -p data models/logs models/artifacts
	@for d in data models/logs models/artifacts; do \
		chmod -R o+w "$$d" 2>/dev/null && echo ">>> prepare-dirs : $$d ouvert en ecriture (o+w)." || \
		echo ">>> prepare-dirs : ATTENTION, impossible de chmod $$d (pas proprietaire) -- relancer avec 'sudo chmod -R o+w $$d' si un conteneur plante en PermissionError dessus." ; \
	done

dev-up: generate-requirements prepare-dirs ## Demarrer l'environnement dev (retry auto + backoff si le pull echoue)
	@n=5; d=5; for i in $$(seq 1 $$n); do \
		echo ">>> dev-up : tentative $$i/$$n" ; \
		if docker compose up -d ; then \
			docker rm -f airflow-init 2>/dev/null || true ; \
			echo ">>> Pour creer un compte admin : make dev-admin" ; \
			exit 0 ; \
		fi ; \
		if [ $$i -lt $$n ]; then \
			echo ">>> echec (credsStore / Docker Desktop ?), nouvel essai dans $${d}s..." ; \
			sleep $$d ; d=$$((d + 5)) ; \
		fi ; \
	done ; \
	echo ">>> dev-up : echec apres $$n tentatives. Voir docs/04-troubleshooting.md (Probleme 6)." ; exit 1

dev-admin: ## Creer ou reinitialiser le compte admin de demonstration (CLI interactive, saisie email/mot de passe)
	docker compose exec crypto-bot-backend python /app/scripts/create_admin.py

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

bot-sync-templates: ## Reseed les bot_templates integres sans toucher aux bots utilisateur
	docker compose exec crypto-bot-backend python /app/scripts/sync_bot_templates.py --show-active

bot-migrate-templates: ## Reseed les bot_templates et migre les snapshots des bots utilisateur integres
	docker compose exec crypto-bot-backend python /app/scripts/sync_bot_templates.py --migrate-instances --show-active

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

ml-train-bot-rsi: ## Entrainer et versionner le modele MLflow du bot RSI BTCUSDT 1h
	docker compose exec crypto-bot-ml-api python -m src.main train-bot-rsi

# ===========================================================================
# Staging (usage local ou VM)
# ===========================================================================

staging-up: generate-requirements ## Demarrer staging
	docker compose -f docker-compose.staging.yml up -d && (docker rm -f staging-airflow-init 2>/dev/null || true)

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
	docker compose -f docker-compose.prod.yml up -d && (docker rm -f prod-airflow-init 2>/dev/null || true)

prod-down: ## Arreter la production
	docker compose -f docker-compose.prod.yml down

prod-config: generate-requirements ## Valider la configuration prod
	docker compose -f docker-compose.prod.yml config

prod-logs: ## Suivre les logs prod
	docker compose -f docker-compose.prod.yml logs -f

# ===========================================================================
# Tests & Lint (venv local)
# ===========================================================================

test: test-backend test-frontend test-utils test-jobs test-models ## Lancer les tests (backend + frontend + utils + jobs + models)

verify: ## Verifier que tous les services installes sont presents et healthy (playbook Ansible, cf. crypto-bot-infra/ansible/)
	cd ../crypto-bot-infra/ansible && ansible-playbook verify.yml -i inventories/dev

test-backend: ## Lancer les tests unitaires backend
	PYTHONPATH=backend/src:. $(VENV_PYTHON) -m pytest backend/tests -v

test-frontend: ## Lancer les tests frontend mock-first
	cd frontend && ../$(VENV_PYTHON) -m pytest tests -q -o cache_dir=/tmp/frontend-pytest-cache

test-utils: ## Lancer les tests de la couche connecteurs partagee (utils/)
	PYTHONPATH=. $(VENV_PYTHON) -m pytest utils/tests -q -o cache_dir=/tmp/utils-pytest-cache

test-coverage: ## Lancer les tests avec coverage (backend + frontend + utils, un rapport par couche)
# NB: backend/utils et frontend ne peuvent PAS partager un seul process pytest : les deux ont
# chacun leur propre package "utils" (utils/ a la racine vs frontend/src/utils/), qui se
# marchent dessus des que les deux repertoires sont sur le meme PYTHONPATH. D'ou 2 invocations
# separees, comme test-backend/test-frontend/test-utils.
	PYTHONPATH=backend/src:. $(VENV_PYTHON) -m pytest --cov=backend/src --cov=utils --cov-report=term-missing --cov-report=json:coverage.json backend/tests utils/tests
	cd frontend && PYTHONPATH=src ../$(VENV_PYTHON) -m pytest --cov=src --cov-report=term-missing --cov-report=json:coverage.json tests
	$(VENV_PYTHON) scripts/track_coverage.py

test-jobs: ## Lancer les tests unitaires des jobs (backend/src/jobs)
	PYTHONPATH=. $(VENV_PYTHON) -m pytest jobs/tests -q -o cache_dir=/tmp/utils-pytest-cache

test-models: ## Lancer les tests unitaires des models (models/src)
# cd models : le code de models/src/ resout ses chemins relatifs (config.yaml, mlruns/...)
# depuis son propre repertoire, pas depuis la racine du repo.
	cd models && PYTHONPATH=..:. ../$(VENV_PYTHON) -m pytest tests -q -o cache_dir=/tmp/models-pytest-cache

ci-test: ## Rejouer localement le job CI test:integration (build image test + tests contre un vrai Postgres)
	docker build --build-arg PYTHON_VERSION=${PYTHON_VERSION} --target test -f backend/Dockerfile -t crypto-bot-backend:ci-test-local .
	IMAGE_TAG=crypto-bot-backend:ci-test-local docker compose --env-file versions.env -f ci/docker-compose.test.yml up \
		--abort-on-container-exit --exit-code-from test-runner; \
	STATUS=$$?; \
	mkdir -p ci/test-results; \
	docker cp "$$(docker compose -f ci/docker-compose.test.yml ps -q test-runner)":/tmp/test-results/. ci/test-results/ 2>/dev/null || true; \
	docker compose -f ci/docker-compose.test.yml down -v 2>/dev/null || true; \
	exit $$STATUS

lint: ## Lancer ruff check + format
	$(VENV_PYTHON) -m ruff check backend/src/ frontend/src/ utils/ jobs/ models/src/ --output-format=concise
	$(VENV_PYTHON) -m ruff format --check backend/src/ frontend/src/ utils/ jobs/ models/src/

lint-fix: ## Corriger automatiquement les erreurs ruff
	$(VENV_PYTHON) -m ruff check backend/src/ frontend/src/ utils/ jobs/ models/src/ --fix
	$(VENV_PYTHON) -m ruff format backend/src/ frontend/src/ utils/ jobs/ models/src/

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
