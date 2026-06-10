# Plan de tests et validation

## Objectif

Prouver que le MVP fonctionne de bout en bout sans dépendre d'une démonstration fragile.

## Niveaux de tests

| Niveau | Cible | Exemples |
|---|---|---|
| Unitaires | fonctions pures | labels, indicateurs, mapping Binance |
| Intégration locale | pipeline fichier | collect fixture -> features -> train mini modèle |
| API | contrats FastAPI | `/health`, `/signals/latest`, erreurs |
| Non-régression ML | artefacts | modèle + scaler + features rechargeables |
| MLOps | tracking et registry | run id, métriques, artefacts, model card |
| Performance | inférence | latence locale sous 300 ms |

## Tests configuration

Cas à tester :

- `config.yaml` existe
- les symboles MVP sont exactement `BTCUSDT` et `BTCETH`
- les ratios de split totalisent `1.0`
- le scaler est fit sur `train`
- les classes de labels sont `SELL=0`, `HOLD=1`, `BUY=2`
- le MLOps est activé et pointe vers un tracking local
- aucun secret Binance réel n'est présent dans le YAML

## Tests data

### Mapping Binance

Vérifier qu'une kline brute est convertie correctement :

- timestamps en UTC
- prix convertis en float ou Decimal selon choix
- colonnes obligatoires présentes

### Qualité OHLCV

Cas à tester :

- doublons supprimés
- bougies triées
- `high` incohérent détecté
- `low` incohérent détecté
- volume négatif rejeté
- trous temporels reportés

### Exports raw et processed

Cas à tester :

- le dataset raw est exporté en `parquet`, `csv` et `jsonl`
- le dataset processed est exporté en `parquet`, `csv` et `jsonl`
- le nombre de lignes est identique entre les formats d'une même zone
- un échantillon JSON peut être chargé et respecte le contrat OHLCV/features

## Tests features

Cas à tester :

- les indicateurs créent les colonnes attendues
- les NaN initiaux des rolling windows sont traités
- aucune valeur infinie
- la liste des features ne contient pas `target`
- les features ne contiennent pas de valeur future

## Tests labels

Cas simples :

```text
close = [100, 101] avec seuil 0.005 -> BUY
close = [100, 99]  avec seuil 0.005 -> SELL
close = [100, 100.1] avec seuil 0.005 -> HOLD
```

Vérifier aussi :

- horizon configurable
- dernière ligne sans futur retirée ou marquée invalide
- mapping label stable

## Tests modèles

### Random Forest

- entraînement sur dataset miniature
- sauvegarde `model.joblib`
- rechargement identique
- `predict_proba` retourne 3 classes

### LSTM

- forward pass shape `(batch, 3)`
- loss calculable avec `CrossEntropyLoss`
- sauvegarde et rechargement `state_dict`
- inférence sur une séquence de test

## Tests MLOps

Cas à tester :

- chaque entraînement crée un `run_id`
- la config YAML du run est copiée dans le dossier d'artefacts
- les métriques principales sont présentes dans le tracking local
- le meilleur modèle est copié dans `artifacts/registry/{model}/best`
- la model card existe et mentionne dataset, métriques, limites et usage prévu

## Tests API

| Endpoint | Cas nominal | Cas erreur |
|---|---|---|
| `/health` | modèle chargé | artefact absent -> degraded |
| `/models` | liste non vide | aucun modèle -> liste vide + warning |
| `/signals/latest` | signal JSON | symbole inconnu -> 400 |
| `/signals/latest` | latence mesurée | modèle absent -> 404 |

## Validation performance

Mesurer séparément :

- temps de chargement du modèle au démarrage
- temps de preprocessing de la dernière fenêtre locale
- temps d'inférence
- temps total endpoint

Cible MVP :

```text
GET /signals/latest p95 < 300 ms
```

Cette cible exclut la collecte réseau. La collecte peut avoir son propre KPI.

## Validation livrable

Checklist finale :

- [ ] `README.md` explique le MVP
- [ ] scripts de collecte documentés
- [ ] dataset raw présent ou générable
- [ ] dataset processed présent ou générable
- [ ] Random Forest entraîné
- [ ] LSTM entraîné
- [ ] runs MLOps tracés
- [ ] registry local alimenté
- [ ] model cards générées
- [ ] comparaison modèle disponible
- [ ] API retourne un signal réel
- [ ] tests passants
- [ ] limites et risques documentés

## Commande cible

À terme, une validation complète doit tenir dans une commande :

```bash
python -m src.validation.mvp_check
```

Sortie attendue :

```text
DATA        ok
FEATURES    ok
RF MODEL    ok
LSTM MODEL  ok
MLOPS       ok
API         ok
LATENCY     ok
```
