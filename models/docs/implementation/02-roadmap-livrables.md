# Roadmap et livrables

## Roadmap courte

| Phase | Durée cible | Objectif | Livrable |
|---|---:|---|---|
| 0. Cadrage | 0,5 jour | Valider périmètre et contrats | Docs analyse/specs/implementation |
| 1. Socle projet | 0,5 jour | Structure, config, dépendances, tests initiaux | squelette `config.yaml`, `src/`, `tests/` |
| 2. Data pipeline | 1 jour | Collecte et validation BTC | datasets raw + rapport qualité |
| 3. Features & labels | 1 jour | Features explicables et cible 3 classes | dataset processed + distribution labels |
| 4. Random Forest | 1 jour | Baseline mesurable | artefact RF + métriques |
| 5. MLOps local | 0,5 jour | Suivre les runs et registry local | MLflow local + model cards |
| 6. LSTM | 1,5 jour | Modèle séquentiel comparable | artefact LSTM + métriques |
| 7. API signal | 1 jour | Endpoint de démo rapide | FastAPI + contrats JSON |
| 8. Validation | 0,5 jour | Tests, README, limites | rapport MVP + checklist |

## Jalons

### Jalon 1 — Donnée exploitable

Critères :

- `BTCUSDT` et `BTCETH` collectés
- données triées, dédupliquées
- rapport qualité disponible

Livrables :

- `data/raw/...` en parquet, CSV et JSONL
- `reports/data_quality.json`
- tests de mapping kline

### Jalon 2 — Dataset ML

Critères :

- features générées
- labels `BUY/SELL/HOLD`
- split temporel
- aucune fuite de données

Livrables :

- `data/processed/features.parquet`
- `data/processed/features.csv`
- `data/processed/features.jsonl`
- `reports/label_distribution.json`
- tests features/labels

### Jalon 3 — Baseline

Critères :

- Random Forest entraîné
- métriques exportées
- importance des features lisible

Livrables :

- `artifacts/random_forest/{run_id}/`
- `reports/random_forest/{run_id}/`

### Jalon 4 — Modèle séquentiel

Critères :

- LSTM entraîné sans signature exotique
- comparaison avec Random Forest
- courbes d'entraînement disponibles

Livrables :

- `artifacts/lstm/{run_id}/`
- `reports/lstm/{run_id}/`
- `reports/model_comparison.md`

### Jalon 5 — MLOps local

Critères :

- chaque entraînement produit un `run_id`
- paramètres, métriques, config et artefacts sont tracés
- le meilleur modèle est copié dans `artifacts/registry/{model}/best`
- une model card est générée

Livrables :

- `mlruns/`
- `artifacts/registry/random_forest/best/`
- `artifacts/registry/lstm/best/`
- `model_card.md` par modèle

### Jalon 6 — API MVP

Critères :

- `/health` OK
- `/signals/latest` retourne un signal réel
- latence mesurée

Livrables :

- `src/api/main.py`
- tests API
- capture curl ou rapport JSON

## Backlog post-MVP

| Évolution | Précondition |
|---|---|
| Registry distant | registry local MVP stable |
| TimescaleDB | besoin de requêtes historiques plus riche |
| Scheduler retraining | pipeline manuel robuste |
| Dashboard Streamlit | endpoint signal stable |
| Backtesting avancé | labels et métriques validés |
| Trading testnet | conformité, garde-fous et risk management documentés |

## Ressources nécessaires

Le MVP est pensé pour une équipe de 4 personnes. Les rôles ci-dessous peuvent être portés par quatre personnes dédiées ou combinés selon la disponibilité réelle, mais les responsabilités doivent rester visibles.

| Rôle | Charge MVP | Responsabilité |
|---|---:|---|
| Data engineer | élevée | collecte, validation, stockage raw/processed, qualité et contrats de données |
| Data scientist | élevée | features, labels, expérimentation, choix des métriques et interprétation |
| Machine learning engineer | élevée | pipeline d'entraînement, tracking MLOps, artefacts, registry local, inférence |
| Backend/DevOps engineer | moyenne | API de signal, Docker simple, variables d'environnement, intégration app |

La responsabilité Product owner est portée collectivement pour le MVP : arbitrage périmètre, KPI, préparation de soutenance et priorisation des exclusions.

## Indicateurs de suivi

- nombre de bougies collectées par symbole
- taux de validation data
- distribution des labels
- `f1_macro` par modèle
- nombre de runs tracés
- meilleur modèle enregistré dans le registry local
- latence p50/p95 API
- nombre de tests passants
- écarts documentés vs périmètre
