# Makefile - Crypto-bot-app
# =========================
# Point d'entree unique pour les commandes Docker Compose.
# Les versions d'images sont centralisees dans versions.env.
#
# /!\ Ne pas utiliser "docker compose" directement.
#     Les variables de versions.env ne seraient pas chargees.

include versions.env
export

.DEFAULT_GOAL := help

help: ## Afficher cette aide
	@echo ""
	@echo "  Crypto-bot-app — commandes disponibles"
	@echo "  ======================================="
	@echo ""
	@echo "  IMPORTANT : ne pas utiliser 'docker compose' directement."
	@echo "  Utiliser 'make <cible>' pour charger automatiquement versions.env."
	@echo ""
	@grep -E '^[a-zA-Z_-]+:.*?## ' Makefile | sort | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'
	@echo ""

# --- Dev ---
dev-up: ## Demarrer l'environnement dev
	docker compose up -d

dev-down: ## Arreter l'environnement dev
	docker compose down

dev-config: ## Valider la configuration dev
	docker compose config

dev-logs: ## Suivre les logs dev
	docker compose logs -f

dev-build: ## Rebuild les images dev (sans cache)
	docker compose build --no-cache

# --- Staging ---
staging-up: ## Demarrer staging
	docker compose -f docker-compose.staging.yml up -d

staging-down: ## Arreter staging
	docker compose -f docker-compose.staging.yml down

staging-config: ## Valider la configuration staging
	docker compose -f docker-compose.staging.yml config

staging-logs: ## Suivre les logs staging
	docker compose -f docker-compose.staging.yml logs -f

# --- Production ---
prod-up: ## Demarrer la production
	docker compose -f docker-compose.prod.yml up -d

prod-down: ## Arreter la production
	docker compose -f docker-compose.prod.yml down

prod-config: ## Valider la configuration prod
	docker compose -f docker-compose.prod.yml config

prod-logs: ## Suivre les logs prod
	docker compose -f docker-compose.prod.yml logs -f

# --- Outils (one-time) ---
dev-init: ## Creer les buckets MinIO (dev)
	docker compose --profile tools up createbuckets

staging-init: ## Creer les buckets MinIO (staging)
	docker compose -f docker-compose.staging.yml --profile tools up createbuckets

prod-init: ## Creer les buckets MinIO (prod)
	docker compose -f docker-compose.prod.yml --profile tools up createbuckets

# --- Debug (admin UIs en prod) ---
prod-debug-up: ## Activer Adminer + Mongo Express en prod
	docker compose -f docker-compose.prod.yml --profile debug up -d adminer mongo-express

prod-debug-down: ## Desactiver Adminer + Mongo Express en prod
	docker compose -f docker-compose.prod.yml --profile debug stop adminer mongo-express

# --- Lint ---
lint: ## Lancer ruff check + format
	ruff check backend/src/ frontend/src/ --output-format=concise
	ruff format --check backend/src/ frontend/src/

lint-fix: ## Corriger automatiquement les erreurs ruff
	ruff check backend/src/ frontend/src/ --fix
	ruff format backend/src/ frontend/src/

# --- Infra check ---
check-infra: ## Valider la coherence versions.env / Dockerfiles / docker-compose
	bash scripts/check-infra.sh
