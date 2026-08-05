---
title: Explorer les runs dans l'UI MLflow
description: Guide pratique pour naviguer, comparer et interpréter les runs dans l'interface MLflow locale.
nav_title: MLflow UI
status: référence
updated: 2026-06-10
---

Ce guide couvre l'exploration des runs produits par ce pipeline dans l'UI MLflow locale. Tous les runs — modèles entraînés et baselines — sont visibles dans une interface unifiée.

---

## Démarrer l'UI

```bash
# Depuis la racine du projet models-training
make mlflow-ui
# équivalent à :
# ../.venv/bin/mlflow ui --backend-store-uri sqlite:///mlflow.db --port 5001
```

Puis ouvrir : [http://localhost:5001](http://localhost:5001)

> Les warnings Pydantic au démarrage (`Field "model_name" has conflict...`) sont inoffensifs — ils viennent des dépendances MLflow, pas du projet.

> Le port 5001 évite le conflit avec d'autres services locaux. Changer si nécessaire.

Le `tracking_uri` est défini dans `config.yaml` → `mlops.tracking_uri: sqlite:///mlflow.db`. Les runs sont enregistrés dans cette base à chaque `make train-*` ou `make train-baselines`.

### Note — backend SQLite vs file store

MLflow 3.13+ a déprécié le backend `file:./mlruns`. Ce projet utilise SQLite (`mlflow.db`) depuis l'itération v1. Les sidecars JSON dans `mlruns/<experiment>/<model>/<run_id>/` restent écrits pour accès CLI sans serveur.

---

## Navigation de base

### Vue principale — liste des expériences

À l'ouverture, MLflow affiche la liste des **expériences**. L'expérience de ce projet s'appelle **`cryptobot-mvp-models`** (définie dans `config.yaml → mlops.experiment_name`).

Cliquer sur `cryptobot-mvp-models` pour entrer dans l'expérience.

### Vue des runs

Dans l'expérience, chaque ligne est un **run** : un entraînement horodaté. Les colonnes affichées sont configurables.

Colonnes utiles à activer (bouton **Columns** en haut à droite) :
- `f1_macro`
- `accuracy`
- `recall_macro`
- `precision_macro`
- `directional_accuracy` (LSTM uniquement)
- `cv_f1_macro_mean` (RF uniquement)
- `best_validation_loss` (LSTM uniquement)

Les runs de ce projet :

| Run name (model) | Type |
|---|---|
| `random_forest` | Modèle entraîné |
| `lstm` | Modèle entraîné |
| `always_hold` | Baseline plancher |
| `random_classifier` | Baseline plancher |

---

## Comparer plusieurs runs

### Méthode 1 — Sélection manuelle

1. Cocher les runs à comparer (checkbox à gauche de chaque ligne)
2. Cliquer **Compare** en haut de la liste
3. La vue comparative affiche toutes les métriques côte à côte

**Cas d'usage typique :** comparer RF vs LSTM vs baselines sur un même dataset.

### Méthode 2 — Filtrer par modèle

Utiliser la barre de recherche avec le filtre `tags.mlflow.runName = "random_forest"` pour ne voir que les runs RF.

### Vue graphique comparative

Dans la vue Compare, onglet **Chart** :
- Axe X : run name ou paramètre
- Axe Y : `f1_macro`
- Visualiser l'évolution de f1_macro entre les runs

---

## Lire un run individuel

Cliquer sur un run pour ouvrir sa fiche détaillée. Elle contient 4 sections :

### Parameters

Hyperparamètres logués au moment de l'entraînement. Pour RF :

```
n_estimators   300
max_depth      8
class_weight   balanced
...
```

Pour LSTM :
```
hidden_size    64
sequence_length 64
loss           cross_entropy
use_class_weights true
...
```

### Metrics

Métriques finales du run. Repères de lecture :

| Métrique | Ce qu'elle mesure | Plancher à battre |
|---|---|---|
| `f1_macro` | Performance équilibrée entre classes | > 0.325 (random) |
| `accuracy` | % de prédictions correctes — trompeuse sur déséquilibre | > 0.493 (always_hold) non requis |
| `recall_macro` | Capacité à détecter les 3 classes | > 0.333 |
| `directional_accuracy` | Accuracy sur signaux actifs BUY/SELL (NaN si modèle dégénéré) | > 0.333 |
| `best_validation_loss` | Loss LSTM optimale — doit être < ln(3) ≈ 1.099 | < 1.099 |
| `cv_f1_macro_mean` | f1_macro moyen sur 5 folds temporels (RF) | Stable vs `f1_macro` |
| `cv_f1_macro_std` | Dispersion inter-folds — fort = instabilité temporelle | < 0.05 conseillé |

### Artifacts

Fichiers produits et copiés dans mlruns depuis `artifacts/` :

| Fichier | Contenu |
|---|---|
| `confusion_matrix.png` | Matrice de confusion test — **premier endroit à regarder** |
| `training_history.png` | Courbes train/val loss LSTM — détecter surapprentissage |
| `model.joblib` / `model.pt` | Artefact modèle rechargeable |
| `scaler.joblib` | Scaler StandardScaler aligné sur train |
| `feature_columns.json` | Liste ordonnée des features utilisées |
| `metrics.json` | Métriques en JSON (pour scripts) |
| `model_card.md` | Fiche de synthèse lisible |
| `config_snapshot.json` | Snapshot exact de config.yaml au moment du run |

Cliquer sur **confusion_matrix.png** pour l'afficher directement dans l'UI.

### Tags

Métadonnées MLflow automatiques (date, version Python, etc.).

---

## Lire la confusion matrix

C'est l'artefact le plus informatif pour diagnostiquer un modèle.

**Modèle dégénéré (run initial) :**
```
              SELL  HOLD  BUY
Réel SELL   [   0    48    0 ]
Réel HOLD   [   0    80    0 ]
Réel BUY    [   0    52    0 ]
```
Toute la colonne HOLD est pleine — le modèle prédit HOLD à 100%.

**Modèle valide (itération v1) :**
```
              SELL  HOLD  BUY
Réel SELL   [  X     Y    Z ]  → recall SELL = X / (X+Y+Z)
Réel HOLD   [  A     B    C ]  → recall HOLD = B / (A+B+C)
Réel BUY    [  D     E    F ]  → recall BUY  = F / (D+E+F)
```
Les 3 lignes ont des valeurs non nulles sur plusieurs colonnes. Les erreurs fréquentes à chercher :
- SELL prédit comme HOLD → le modèle hésite sur les baisses
- BUY prédit comme HOLD → le modèle hésite sur les hausses
- SELL prédit comme BUY → erreur directionnelle grave (signal inversé)

---

## Courbes d'entraînement LSTM

Dans les artifacts d'un run LSTM, ouvrir **`training_history.png`**.

| Forme de la courbe | Diagnostic |
|---|---|
| val_loss descend et se stabilise | Entraînement normal |
| val_loss remonte après quelques epochs | Surapprentissage — réduire `epochs` ou augmenter `dropout` |
| val_loss ne bouge pas dès epoch 1 | Modèle dégénéré — vérifier class weights et distribution |
| train_loss descend, val_loss stagne | Légère divergence — normal, early stopping gère |

---

## Comparer RF et LSTM méthodiquement

Workflow recommandé après chaque run :

```text
1. Ouvrir l'expérience cryptobot-mvp-models
2. Sélectionner le nouveau run + always_hold + random_classifier
3. Cliquer Compare → vérifier que f1_macro > 0.325
4. Ouvrir le run → Artifacts → confusion_matrix.png
5. Pour LSTM : ouvrir training_history.png
6. Comparer config_snapshot.json si deux runs sont proches
```

---

## Retrouver le meilleur run rapidement

Trier la liste par `f1_macro` décroissant (cliquer sur la colonne) pour identifier immédiatement le meilleur run par métrique.

Le modèle enregistré dans `artifacts/registry/{model}/best/` correspond au run avec le meilleur `f1_macro` au moment de l'entraînement — pas nécessairement le dernier run.

---

## Commandes utiles en complément

```bash
# Voir les métriques JSON directement sans UI
cat mlruns/cryptobot-mvp-models/random_forest/20260601-200806/metrics.json

# Comparer deux runs en CLI
diff \
  mlruns/cryptobot-mvp-models/random_forest/20260601-200806/params.json \
  mlruns/cryptobot-mvp-models/random_forest/20260601-*/params.json

# Lister tous les runs d'un modèle
ls -lt mlruns/cryptobot-mvp-models/random_forest/

# Ouvrir une confusion matrix sans navigateur
open artifacts/random_forest/20260601-200806/confusion_matrix.png
```
