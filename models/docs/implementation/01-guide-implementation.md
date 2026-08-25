---
title: Construire le MVP models-training du CryptoBot
description: Guide pour implémenter la collecte BTC, le preprocessing, Random Forest, LSTM et l'API de signal.
nav_title: Guide MVP
status: référence
updated: 2026-06-10
---

Ce guide décrit l'ordre d'implémentation recommandé pour obtenir un MVP démontrable. L'objectif est de faire fonctionner une chaîne complète avant d'ajouter de l'infrastructure.

## Exemple

Nous allons construire un pipeline qui collecte `BTCUSDC` et `BTCETH`, fabrique des features, entraîne deux modèles, puis expose le dernier signal via API.

Nous commençons par la donnée brute, puis nous ajoutons les features et labels, puis nous branchons les modèles et l'API.

Source de contexte : anciens labs `crypto-lstm-models`, `rnn-models-training`, `forex-rnn-models`, et app v2 `_dst-crypto-bot_v2/app`.

### Step 1: Poser la structure minimale

Créer une structure simple et testable :

```text
config.yaml
Makefile
src/
  main.py
  config/
    config_loader.py
    dependencies.py
    exceptions.py
    settings.py
  data/
  features/
  models/
  training/
  mlops/
  inference/
  api/
tests/
data/
artifacts/
reports/
```

Le premier test doit vérifier que la configuration charge les symboles MVP.

Friction : si la structure imite directement les anciens labs, le projet va embarquer scheduler, monitoring avancé et services inutilisés.

Résolution : garder uniquement les dossiers nécessaires au flux collecter -> entraîner -> servir.

Preuve observable :

```bash
make config
make test
```

La config doit être chargée avant les scripts métier :

```python
from src.config.config_loader import load_config

config = load_config("config.yaml")
assert config.data.symbols == ["BTCUSDC", "BTCETH"]
```

Convention : `config.yaml` est le fichier de configuration déclaratif à la racine. `src/config/` contient le code de chargement, validation, exceptions et dépendances.

### Step 2: Collecter et valider les OHLCV

Implémenter un collecteur Binance avec une sortie locale stable.

Pseudo-contrat :

```python
def collect_klines(symbol: str, interval: str, start: str, end: str) -> pd.DataFrame:
    """Return columns: open_time, open, high, low, close, volume, close_time."""
```

Ajouter ensuite une validation :

- colonnes obligatoires présentes
- timestamps triés
- doublons supprimés
- continuité temporelle mesurée

Écrire les données dans plusieurs formats :

- `parquet` comme format primaire
- `csv` pour ouverture manuelle
- `jsonl` pour inspection ligne à ligne et compatibilité API/livrables

Écrire aussi un sidecar `*.meta.json` pour chaque fichier généré, par exemple `data/raw/BTCUSDC/1h.csv.meta.json`, avec `layer`, `dataset`, `source`, `symbol`, `interval`, `row_count`, `columns`, `dtypes`, `file_size_bytes` et `time_range`.

Friction : l'appel réseau peut être lent ou indisponible, ce qui rend les tests instables.

Résolution : isoler le mapping Binance dans une fonction pure et tester avec une fixture de klines. Pour `BTCETH`, Binance Spot fournit `ETHBTC`; le collecteur doit interroger `ETHBTC`, inverser les prix OHLC, puis stocker la ligne sous le symbole canonique `BTCETH`.

Preuve observable :

```bash
make collect
python -m unittest tests.test_data
```

### Step 3: Construire les features sans fuite de données

Créer `src/features/build.py` et `src/features/labels.py`.

Pipeline :

```text
raw OHLCV
  -> indicateurs techniques
  -> labels futurs
  -> split temporel
  -> fit scaler train
  -> transform validation/test
```

Friction : si le scaler est ajusté avant le split, les statistiques du test entrent dans l'entraînement.

Résolution : le split temporel doit arriver avant `fit`. Sauvegarder le scaler dans l'artefact.

Preuve observable :

```bash
make features
python -m unittest tests.test_features
```

### Step 4: Entraîner Random Forest comme baseline

Random Forest est la première cible car elle est rapide et explicable.

Sorties attendues :

```text
artifacts/random_forest/{run_id}/model.joblib
artifacts/random_forest/{run_id}/scaler.joblib
artifacts/random_forest/{run_id}/feature_columns.json
artifacts/random_forest/{run_id}/metrics.json
artifacts/random_forest/{run_id}/model_card.md
reports/random_forest/{run_id}/confusion_matrix.png
```

Friction : une classe `HOLD` dominante peut donner une accuracy correcte et un modèle inutile.

Résolution : suivre `f1_macro`, métriques par classe et matrice de confusion.

Preuve observable :

```bash
python -m src.training.train_random_forest
cat artifacts/random_forest/latest/metrics.json
```

### Step 5: Tracer les runs avec un MLOps local

Créer un module `src/mlops/` pour centraliser le suivi des expériences.

Les utilitaires transverses sont placés dans `src/utils/` :

- `logger.py` configure les logs console/fichier depuis `config.yaml`
- `visualization.py` exporte les graphiques de validation dans les artefacts modèle

Contrat minimal :

```python
with start_run(model_name="random_forest", config=config) as run:
    run.log_params(params)
    run.log_metrics(metrics)
    run.log_artifacts(artifact_dir)
```

Friction : sans suivi des runs, une équipe de quatre personnes ne sait plus quel modèle correspond à quelle config.

Résolution : utiliser MLflow en backend local (`file:./mlruns`) et copier le meilleur modèle dans `artifacts/registry/{model}/best`.

Preuve observable :

```bash
ls mlruns
ls artifacts/registry/random_forest/best
cat artifacts/registry/random_forest/best/model_card.md
```

### Step 6: Entraîner LSTM avec une interface standard

Le LSTM doit faire de la classification 3 classes comme Random Forest.

Règle d'interface :

```python
class LSTMClassifier(nn.Module):
    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """Return logits shaped (batch, 3)."""
```

Friction : les anciens labs contenaient des modèles qui retournaient parfois un tuple. Les trainers cassaient au moment de calculer la loss.

Résolution : une seule signature de sortie pour le MVP. Les poids d'attention ou sorties secondaires restent hors périmètre.

Preuve observable :

```bash
make train-lstm
ls artifacts/registry/lstm/best
cat artifacts/registry/lstm/best/metrics.json
```

### Step 7: Servir le dernier signal

Créer une API FastAPI légère.

Endpoints MVP :

```text
GET /health
GET /models
GET /signals/latest?symbol=BTCUSDC&model=random_forest
```

Friction : si `/signals/latest` collecte les données depuis Binance à chaque appel, la latence dépend du réseau.

Résolution : l'endpoint lit les dernières features locales et utilise un modèle déjà chargé.

Preuve observable :

```bash
uvicorn src.api.main:app --reload --port 8010
curl "http://localhost:8010/signals/latest?symbol=BTCUSDC&model=random_forest"
```

### Step 8: Brancher la validation MVP

Ajouter un script de validation qui exécute le parcours complet sur un petit dataset.

```bash
python -m src.validation.mvp_check
```

Le script doit vérifier :

- datasets présents
- artefacts complets
- runs MLOps tracés
- registry local alimenté
- métriques présentes
- API chargeable
- inférence locale sous seuil de latence

## Next steps

Vous avez maintenant un chemin de construction progressif pour livrer un MVP models-training mesurable.

Prochaines extensions après MVP :

- brancher un registry distant si le registry local devient insuffisant
- ajouter `15m` et `4h` pour comparer la granularité
- exposer le signal dans le frontend Streamlit
- étudier un stockage TimescaleDB si le volume historique augmente
