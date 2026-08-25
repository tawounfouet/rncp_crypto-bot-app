# Retour d'expérience des labs précédents

Statut: référence
Derniere revision: 2026-06-10

Ce document synthétise ce qu'il faut reprendre des travaux antérieurs et ce qu'il faut volontairement écarter pour le MVP models-training.

## Sources analysées

| Source | Apport principal |
|---|---|
| `projects/ai-coding-platforms/cursor/crypto-lstm-models` | Pipeline crypto LSTM, Binance, preprocessing, FastAPI, scheduler |
| `projects/ai-coding-platforms/cursor/rnn-models-training` | Structure simple RNN/LSTM/GRU, configs YAML, tests unitaires de base |
| `projects/ai-coding-platforms/cursor/forex-rnn-models` | MLOps, Kafka, TimescaleDB, MLflow, monitoring, analyses critiques |
| `_dst-crypto-bot_v2/app` | Backend FastAPI existant, domaines `market`, `strategy`, `trading`, modèles OHLCV |

## Ce qu'on reprend

### Collecte Binance

Le lab `crypto-lstm-models` contient une bonne base conceptuelle : client Binance, collecte OHLCV, multi-symboles, sauvegarde CSV. Pour le MVP, on reprend l'idée mais on réduit :

- deux symboles seulement : `BTCUSDC`, `BTCETH`
- un intervalle prioritaire : `1h`
- sauvegarde locale simple : `data/raw`, `data/processed`
- pas de WebSocket pour la première version

### Preprocessing temporel

Les labs rappellent trois règles importantes :

- split temporel, jamais de shuffle global avant train/test
- normalisation ajustée sur le train uniquement
- création de séquences glissantes pour LSTM

Le MVP doit traiter ces règles comme des critères d'acceptation. Les analyses critiques ont repéré des fuites de données dans certains pipelines. On les évite dès la conception.

### Indicateurs techniques

L'app v2 contient déjà des indicateurs dans `strategy/engine/indicators/technical_indicators.py`. Le MVP reprend un set court :

- returns
- volatility rolling
- SMA 20
- SMA 50
- EMA 12
- EMA 26
- RSI 14
- MACD
- Bollinger Bands
- volume rolling mean

Le but est d'avoir des features explicables, pas de maximiser le nombre d'indicateurs.

### Entraînement robuste

À reprendre des labs RNN/LSTM :

- early stopping
- gradient clipping pour LSTM
- métriques de régression et de classification selon la cible
- sauvegarde de l'historique d'entraînement
- sauvegarde du scaler avec le modèle

Point non négociable : le scaler et la liste des features doivent être persistés avec l'artefact modèle. Un ancien lab chargeait le modèle API sans scaler, ce qui rendait la prédiction inexploitable.

### Logging et métriques

Les anciens projets ont des loggers riches, mais souvent trop dispersés. Pour le MVP :

- logging standard Python structuré simplement
- un fichier de métriques par run
- latence d'inférence mesurée
- erreurs de collecte tracées
- pas de stack Prometheus/Grafana obligatoire au départ

## Ce qu'on écarte du MVP

| Élément | Raison |
|---|---|
| Kafka | Surdimensionné pour deux symboles et un flux batch court |
| Airflow | Ajoute de la dette avant d'avoir stabilisé le pipeline |
| TimescaleDB | Utile plus tard, mais parquet/csv/jsonl suffit pour entraîner et auditer le MVP |
| Kubernetes | Déjà géré côté infra projet, inutile pour prouver le modèle |
| MultiTaskLSTM | Les anciens trainers ne supportent pas correctement les sorties multiples |
| Portefeuille et ordres réels | Risque métier et réglementaire hors validation ML initiale |
| Prédiction de gain long terme | Plus incertain, moins compatible avec un MVP court |

## Anti-patterns observés

| Anti-pattern | Conséquence | Règle MVP |
|---|---|---|
| Infrastructure avant valeur métier | Beaucoup de services, peu de démonstration | Docker simple seulement après pipeline local OK |
| README plus ambitieux que le code | Perte de confiance dans les livrables | Documenter uniquement ce qui est prévu ou vérifié |
| Normalisation avant split | Data leakage, métriques optimistes | Fit scaler sur train, transform val/test |
| Modèles avec signatures différentes | Trainer cassé | Interface modèle unique |
| API de prédiction factice | Démo trompeuse | API branchée sur artefact réel ou non livrée |
| Absence de tests | Bugs invisibles | Tests dès data/features/labels |

## Décision de capitalisation

Le nouveau `models-training` ne doit pas copier un ancien projet. Il doit en extraire un noyau plus propre :

```text
crypto-lstm-models      -> collecte Binance + LSTM
rnn-models-training     -> simplicité structurelle + tests
forex-rnn-models        -> métriques, monitoring, leçons critiques
_dst-crypto-bot_v2/app  -> contrats backend et modèle MarketData
```

Le résultat attendu est un projet plus petit, mais plus vérifiable.
