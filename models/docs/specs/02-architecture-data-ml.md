# Architecture data et ML

## Vue logique

```text
config.yaml
Makefile
src/
  main.py
  config/
    __init__.py
    config_loader.py
    dependencies.py
    exceptions.py
    settings.py
  data/
    collect.py
    validate.py
    storage.py
  features/
    indicators.py
    labels.py
    build.py
  models/
    random_forest.py
    lstm.py
    registry.py
  training/
    train_random_forest.py
    train_lstm.py
    evaluate.py
  mlops/
    tracking.py
    registry.py
    model_card.py
  inference/
    predict.py
    signal.py
  api/
    main.py
    schemas.py
tests/
data/
  raw/
  processed/
artifacts/
  random_forest/
  lstm/
  registry/
mlruns/
reports/
```

## Flux cible

```text
1. collect
   Binance klines -> raw dataset

2. validate
   contrôle colonnes, doublons, trous temporels

3. features
   OHLCV -> indicateurs -> labels

4. split
   train -> validation -> test, ordre temporel conservé

5. train
   Random Forest + LSTM

6. evaluate
   métriques classification + latence

7. track
   paramètres + métriques + artefacts + model card

8. package
   modèle + scaler + feature list + config + métriques

9. serve
   API locale -> signal
```

## Configuration centrale

Le MVP utilise `config.yaml` comme source de vérité pour les paramètres non secrets :

- paires supportées : `BTCUSDT`, `BTCETH`
- mapping source exchange : `BTCETH` est collecté depuis `ETHBTC` puis inversé pour conserver le vocabulaire métier `BTCETH`
- intervalle principal : `1h`
- seuils de labellisation `BUY` / `SELL` / `HOLD`
- split temporel
- indicateurs techniques
- hyperparamètres Random Forest et LSTM
- tracking MLOps local
- métriques et cible de latence API

Les clés Binance ne doivent pas être stockées dans le YAML. Le fichier référence seulement les noms de variables d'environnement à lire au runtime.

Convention de nommage :

- `config.yaml` est le fichier déclaratif racine, visible dès l'ouverture du projet.
- `src/config/config_loader.py` charge le YAML, lit les variables d'environnement nécessaires et applique les valeurs par défaut.
- `src/config/settings.py` expose des objets typés validés pour le reste du code.
- `src/config/exceptions.py` et `src/config/dependencies.py` regroupent les erreurs et garde-fous transverses utilisés au démarrage.

Le raw dataset conserve les colonnes d'audit `source_symbol` et `price_inverted` pour distinguer le symbole métier du symbole réellement interrogé côté exchange.

## Choix de stockage MVP

| Zone | Format recommandé | Raison |
|---|---|---|
| `data/raw` | Parquet primaire, CSV + JSONL en exports | Parquet pour l'entraînement, CSV/JSONL pour inspection et livrables |
| `data/processed` | Parquet primaire, CSV + JSONL en exports | Reproductibilité des features et compatibilité API/docs |
| `artifacts` | `joblib`, `torch`, `json` | Compatible scikit-learn et PyTorch |
| `artifacts/registry` | dossiers versionnés + pointeur best model | Registry local MVP |
| `mlruns` | MLflow local | Suivi des expériences en équipe |
| `reports` | JSON + PNG | Lisible en soutenance |

PostgreSQL et TimescaleDB sont utiles pour la suite, mais non requis pour valider le MVP modèle.

Convention :

- `parquet` est le format de travail prioritaire pour conserver les types et accélérer les lectures pandas.
- `csv` est l'export tabulaire le plus simple à ouvrir dans un tableur.
- `jsonl` est recommandé pour `raw` et `processed`, car chaque ligne représente une bougie ou une ligne de features complète.
- `json` est réservé aux petits exemples, contrats API, métriques, rapports et échantillons. Un gros dataset en JSON tableau devient vite lourd à lire et à versionner.
- chaque fichier physique écrit dans `data/raw` ou `data/processed` doit avoir un sidecar `*.meta.json` contenant au minimum la couche, le symbole, l'intervalle, le format, le nombre de lignes, les colonnes, les types, la taille fichier et la période couverte.

Exemples attendus :

```text
data/raw/BTCUSDT/1h.parquet
data/raw/BTCUSDT/1h.parquet.meta.json
data/raw/BTCUSDT/1h.csv
data/raw/BTCUSDT/1h.csv.meta.json
data/raw/BTCUSDT/1h.jsonl
data/raw/BTCUSDT/1h.jsonl.meta.json
data/processed/BTCUSDT/1h_features.parquet
data/processed/BTCUSDT/1h_features.parquet.meta.json
data/processed/BTCUSDT/1h_features.csv
data/processed/BTCUSDT/1h_features.jsonl
```

## MLOps MVP

Le MLOps est inclus dans le MVP, mais dans une forme locale et légère. Il doit répondre à trois besoins d'équipe :

- comparer les runs Random Forest et LSTM
- retrouver la config et le dataset utilisés pour produire un modèle
- charger le meilleur modèle sans deviner quel fichier utiliser

Composants :

| Composant | Rôle MVP |
|---|---|
| MLflow local | suivi des paramètres, métriques, artefacts et graphiques |
| `run_id` | identifiant unique pour relier dataset, modèle et rapports |
| registry local | copie du meilleur modèle par famille et pointeur `best` |
| model card | résumé lisible : données, métriques, limites, usage prévu |
| snapshot config | copie de `config.yaml` dans chaque run |

Structure attendue :

```text
mlruns/
artifacts/
  random_forest/{run_id}/
  lstm/{run_id}/
  registry/
    random_forest/best/
    lstm/best/
reports/
  model_comparison.md
```

Le registry distant et le déploiement automatisé des modèles restent post-MVP. Le tracking local, lui, est obligatoire dès le premier entraînement.

## Schéma feature store local

Colonnes minimales :

| Colonne | Type | Description |
|---|---|---|
| `symbol` | string | `BTCUSDT` ou `BTCETH` |
| `interval` | string | `1h` par défaut |
| `timestamp` | datetime UTC | début de bougie |
| `open` | float | prix ouverture |
| `high` | float | prix haut |
| `low` | float | prix bas |
| `close` | float | prix clôture |
| `volume` | float | volume |
| `return_1` | float | rendement une période |
| `volatility_20` | float | volatilité rolling |
| `sma_20` | float | moyenne mobile 20 |
| `sma_50` | float | moyenne mobile 50 |
| `rsi_14` | float | RSI |
| `macd` | float | ligne MACD |
| `bb_width` | float | largeur Bollinger |
| `target` | string | `BUY`, `SELL`, `HOLD` |

## Random Forest

Rôle : baseline robuste et explicable.

Configuration initiale :

```yaml
random_forest:
  n_estimators: 300
  max_depth: 8
  min_samples_leaf: 20
  class_weight: balanced
  random_state: 42
```

Entrée :

- une ligne = une bougie avec features tabulaires
- pas de séquence explicite

Sortie :

- probabilités par classe
- classe prédite
- importance des features

## LSTM

Rôle : tester l'apport séquentiel.

Configuration initiale :

```yaml
lstm:
  sequence_length: 64
  hidden_size: 64
  num_layers: 2
  dropout: 0.2
  batch_size: 32
  epochs: 50
  patience: 7
  learning_rate: 0.001
```

Entrée :

- tenseur `(batch, sequence_length, n_features)`

Sortie :

- logits de classification sur 3 classes

Règle d'interface :

- tous les modèles doivent exposer une méthode d'inférence qui retourne `SignalPrediction`
- aucun modèle MVP ne retourne de tuple non standard

## Artefact modèle

Chaque entraînement doit produire :

```text
artifacts/{model_name}/{run_id}/
  model.joblib ou model.pt
  scaler.joblib
  feature_columns.json
  label_mapping.json
  config.yaml
  metrics.json
  training_summary.md
```

Pour LSTM, `model.pt` doit contenir le `state_dict` et la configuration minimale nécessaire pour reconstruire le réseau.

## Métriques

| Métrique | Usage |
|---|---|
| `accuracy` | Vue globale, insuffisante seule |
| `f1_macro` | Mesure équilibrée entre classes |
| `precision_by_class` | Risque de faux BUY/SELL |
| `recall_by_class` | Capacité à détecter BUY/SELL |
| `directional_accuracy` | Pertinence directionnelle |
| `latency_ms` | Compatibilité API |
| `data_quality_score` | Fiabilité dataset |

## Intégration avec l'app v2

Le backend `app/backend` possède déjà un domaine `market` et un moteur `strategy`. Le MVP models-training doit rester indépendant, puis exposer des contrats compatibles :

- même vocabulaire symbole : `BTCUSDT`, `BTCETH`
- OHLCV compatible avec `MarketData.to_dict()`
- signal numérique compatible stratégie : `BUY=1`, `SELL=-1`, `HOLD=0`
- endpoint API consommable par le backend ou Streamlit

Cette séparation évite de casser l'application existante pendant la construction du modèle.
