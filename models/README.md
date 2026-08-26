# CryptoBot v2 — Models Training

Statut: référence
Derniere revision: 2026-06-10

Ce dépôt porte le MVP **Data Engineering + Machine Learning** du CryptoBot v2. Il transforme des cours de marché BTC en datasets fiables, en features exploitables, en runs d'entraînement traçables, puis expose un signal opérationnel `BUY`, `SELL` ou `HOLD`.

Le périmètre est volontairement réduit pour valider l'hypothèse de valeur sans multiplier les risques techniques :

- collecte automatisée des paires `BTCUSDC` et `BTCETH`
- dataset OHLCV reproductible
- exports raw et processed en Parquet, CSV et JSONL
- baseline `RandomForestClassifier`
- modèle séquentiel `LSTM`
- génération d'un signal `BUY` / `SELL` / `HOLD`
- suivi MLOps local des runs, métriques, artefacts et model cards
- mesure de latence, qualité de données et métriques de modèle

Sont exclus du MVP : trading réel, exécution d'ordres, portefeuilles multiples, prédiction de gains long terme, optimisation de portefeuille, Airflow, Kafka et Kubernetes côté modèle.

## Documentation

| Dossier | Contenu |
|---|---|
| [docs/](docs/README.md) | Vue d'ensemble de la documentation models-training |
| [docs/analyse/](docs/analyse/README.md) | Cadrage MVP, retour d'expérience des labs, risques et hypothèses |
| [docs/specs/](docs/specs/README.md) | Spécifications fonctionnelles, techniques, données et API |
| [docs/implementation/](docs/implementation/README.md) | Guide d'implémentation, roadmap, plan de tests |
| [config.yaml](config.yaml) | Configuration centrale du MVP |
| [Makefile](Makefile) | Commandes courtes pour l'équipe |

## Décision d'architecture MVP

Le MVP privilégie un flux court et testable :

```text
Binance klines
  -> stockage local parquet/csv/jsonl
  -> validation qualité
  -> features OHLCV + indicateurs
  -> labels BUY/SELL/HOLD
  -> Random Forest baseline
  -> LSTM séquentiel
  -> tracking MLOps local
  -> endpoint /signals/latest
```

Cette approche reprend les éléments robustes des anciens labs (`crypto-lstm-models`, `rnn-models-training`, `forex-rnn-models`) tout en évitant le surdimensionnement identifié dans leurs analyses critiques.

## Commandes

Commandes d'équipe via Makefile :

```bash
make config
make collect
make features
make train-rf
make train-lstm
make mlflow-ui
make api
make test
```

Les mêmes actions sont disponibles via le CLI central :

```bash
python -m src.main config
python -m src.main collect --symbols BTCUSDC BTCETH --interval 1h
python -m src.main features --symbols BTCUSDC BTCETH --interval 1h
python -m src.main check
```

La configuration par défaut est centralisée dans `config.yaml`. Les secrets Binance ne sont pas stockés dans ce fichier : seules les variables d'environnement attendues y sont référencées.

Note symbole : `BTCETH` reste le nom canonique côté MVP. Comme Binance Spot expose la paire inverse `ETHBTC`, `config.yaml` déclare un mapping qui collecte `ETHBTC` puis inverse les prix OHLC avant stockage.

Note data lineage : chaque fichier généré dans `data/raw` et `data/processed` est accompagné d'un sidecar `*.meta.json` décrivant la couche, le symbole, l'intervalle, le format, les colonnes, les types, le nombre de lignes, la taille fichier et la période couverte.

## Critères de fin MVP

Le MVP est considéré démontrable quand :

- les deux paires cibles sont collectées automatiquement
- le dataset nettoyé est versionné localement
- les deux modèles produisent un signal sur les dernières bougies
- les métriques `accuracy`, `f1_macro`, `directional_accuracy` et `latence_api_ms` sont produites
- chaque entraînement est tracé avec un `run_id`, sa config, ses métriques et ses artefacts
- l'API retourne une réponse en moins de 300 ms hors appel réseau externe
- les tests couvrent la collecte, le preprocessing, la génération de labels et l'inférence
