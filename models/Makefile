.PHONY: help install install-dev config collect features train-rf train-lstm api check test compile clean

PYTHON ?= ../../.venv/bin/python
PIP ?= $(PYTHON) -m pip
CONFIG ?= config.yaml
SYMBOLS ?= BTCUSDT BTCETH
INTERVAL ?= 1h
DATASET ?= data/processed/BTCUSDT/1h_features.parquet
HOST ?= 0.0.0.0
PORT ?= 8010

help: ## Affiche les commandes disponibles
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  %-14s %s\n", $$1, $$2}'

install: ## Installe les dépendances runtime
	$(PIP) install -r requirements.txt

install-dev: ## Installe les dépendances runtime + dev
	$(PIP) install -r requirements-dev.txt

config: ## Valide et affiche un résumé de config.yaml
	$(PYTHON) -m src.main --config $(CONFIG) config

collect: ## Collecte les données raw (mode défini dans config.yaml — paginated par défaut)
	$(PYTHON) -m src.main --config $(CONFIG) collect --symbols $(SYMBOLS) --interval $(INTERVAL)

collect-single: ## Collecte 1 000 lignes uniquement (mode single, pour tests rapides)
	$(PYTHON) -m src.main --config $(CONFIG) collect --symbols $(SYMBOLS) --interval $(INTERVAL)

features: ## Construit les features processed pour SYMBOLS et INTERVAL
	$(PYTHON) -m src.main --config $(CONFIG) features --symbols $(SYMBOLS) --interval $(INTERVAL)

train-baselines: ## Évalue AlwaysHold et UniformRandom sur DATASET (planchers de comparaison)
	$(PYTHON) -m src.main --config $(CONFIG) train-baselines --dataset $(DATASET)

train-rf: ## Entraîne la baseline Random Forest sur DATASET
	$(PYTHON) -m src.main --config $(CONFIG) train-rf --dataset $(DATASET)

train-lstm: ## Lance l'entraînement LSTM
	$(PYTHON) -m src.main --config $(CONFIG) train-lstm --dataset $(DATASET)

mlflow-ui: ## Démarre l'UI MLflow sur http://localhost:5001
	$(PYTHON) -m mlflow ui --backend-store-uri sqlite:///mlflow.db --port 5001

api: ## Démarre l'API FastAPI de signal
	$(PYTHON) -m src.main --config $(CONFIG) api --host $(HOST) --port $(PORT)

check: ## Vérifie l'état MVP
	$(PYTHON) -m src.main --config $(CONFIG) check

test: ## Lance les tests unitaires disponibles
	$(PYTHON) -m unittest discover -s tests

compile: ## Vérifie la syntaxe Python
	$(PYTHON) -m compileall -q src tests

clean: ## Supprime les caches Python locaux
	find src tests -type d -name "__pycache__" -prune -exec rm -rf {} +
	find src tests -type f -name "*.pyc" -delete
