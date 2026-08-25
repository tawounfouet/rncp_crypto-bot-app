# Spécifications fonctionnelles MVP

Statut: référence
Derniere revision: 2026-06-10

## Objectif fonctionnel

Le système models-training doit produire un signal `BUY`, `SELL` ou `HOLD` pour `BTCUSDC` et `BTCETH`, à partir de données OHLCV collectées automatiquement.

## Utilisateurs cibles

| Utilisateur | Fonction attendue |
|---|---|
| Data engineer | collecter, valider, versionner les datasets raw/processed |
| Data scientist | entraîner, comparer, évaluer les modèles |
| Machine learning engineer | suivre les expériences, gérer les artefacts, préparer l'inférence |
| Développeur backend | appeler un endpoint stable pour récupérer un signal |
| Chef de projet | suivre l'avancement via KPI et livrables |
| Jury / évaluateur | vérifier une chaîne data complète et reproductible |

## Fonctionnalités incluses

### F1 — Collecter les données

Le système doit collecter les klines Binance pour :

- `BTCUSDC`
- `BTCETH`

Paramètres MVP :

- intervalle par défaut : `1h`
- historique cible : au moins 180 jours si disponible
- sortie brute primaire : `data/raw/{symbol}/{interval}.parquet`
- exports inspectables : `.csv` et `.jsonl`

Critères d'acceptation :

- chaque ligne contient open time, open, high, low, close, volume
- les doublons sont supprimés
- un rapport qualité est généré
- un export JSON/JSONL est disponible pour inspection, API ou livrable

### F2 — Construire les features

Le système doit transformer les OHLCV en features ML :

- rendements
- volatilité glissante
- moyennes mobiles
- RSI
- MACD
- bandes de Bollinger
- features de volume

Critères d'acceptation :

- pas de valeur infinie
- stratégie de traitement des NaN documentée
- liste des features sauvegardée dans l'artefact modèle

### F3 — Générer les labels

Le système doit créer une cible `BUY`, `SELL`, `HOLD`.

Règle initiale :

```text
future_return = close[t + horizon] / close[t] - 1

BUY  si future_return > positive_threshold
SELL si future_return < negative_threshold
HOLD sinon
```

Paramètres recommandés :

- `horizon = 1` bougie pour démarrer
- seuil fixe initial : `0.002` ou seuil dérivé de la volatilité

Critères d'acceptation :

- distribution des classes affichée
- seuils présents dans la config
- aucune ligne future dans les features

### F4 — Entraîner Random Forest

Le système doit entraîner une baseline `RandomForestClassifier`.

Critères d'acceptation :

- split temporel train/validation/test
- métriques `accuracy`, `precision`, `recall`, `f1_macro`
- matrice de confusion sauvegardée
- importance des features exportée

### F5 — Entraîner LSTM

Le système doit entraîner un modèle LSTM sur séquences.

Critères d'acceptation :

- séquences de longueur configurable
- scaler fit sur train uniquement
- early stopping
- courbe loss train/validation
- métriques comparables avec Random Forest

### F6 — Servir le signal

Le système doit exposer le dernier signal sous forme API.

Critères d'acceptation :

- réponse JSON typée
- temps de réponse local mesuré
- modèle chargé au démarrage
- endpoint health indiquant l'état modèle/données

### F7 — Suivre les entraînements en MLOps local

Le système doit tracer chaque entraînement Random Forest et LSTM.

Critères d'acceptation :

- chaque run possède un `run_id`
- la config YAML utilisée est sauvegardée avec le run
- les paramètres, métriques, artefacts et graphiques sont rattachés au run
- le meilleur modèle est copié dans un registry local
- une model card est générée pour expliquer données, métriques, limites et usage prévu

## Exclusions explicites

| Exclusion | Raison |
|---|---|
| Passer des ordres | Risque financier hors MVP |
| Gérer des portefeuilles multiples | Complexité métier non nécessaire |
| Prédire un gain long terme | Hypothèse trop large |
| Backtesting avancé | Peut venir après le premier signal |
| Streaming temps réel | La latence API prioritaire concerne l'inférence, pas le réseau |
| Scheduler de retraining | Le premier objectif est l'entraînement reproductible et tracé manuellement |

## Règles métier

- Un signal ne doit jamais être présenté comme une garantie.
- Le système doit retourner `HOLD` en cas d'incertitude ou de donnée insuffisante.
- Une prédiction doit mentionner le modèle, sa version, la date de données et la latence.
- Une erreur de fraîcheur des données doit être visible dans la réponse ou le healthcheck.

## Definition of Done fonctionnelle

- Les scripts de collecte et d'entraînement tournent sur machine locale.
- Les deux paires cibles disposent d'un dataset nettoyé.
- Les deux modèles produisent un signal.
- Les métriques sont sauvegardées dans `reports/`.
- L'API retourne un signal documenté.
- Les limites sont connues et visibles dans la documentation.
