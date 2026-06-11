---
title: Plan d'itération v2 — feature importance, biais SELL, tuning LSTM
description: Implémentation des trois axes post-analyse itération v1.
nav_title: Itération v2
---

Ce document est la suite directe de [05-resultats-iteration-v1.md](../analyse/05-resultats-iteration-v1.md).

**Situation de départ :** modèles valides (f1_macro RF=0.422, LSTM=0.410), mais LSTM avec biais BUY fort (recall SELL=0.15, recall BUY=0.61) et directional_accuracy≈ random.

**Ordre d'exécution :**

```text
Step 1 → feature importance RF  (diagnostic — 30 min)
Step 2 → biais SELL LSTM        (fix bloquant)
Step 3 → tuning LSTM            (amplification)
```

---

## Step 1 : Feature importance RF

### Objectif

Identifier quelles features discriminent réellement BUY/SELL/HOLD. Si 5 features représentent 80% de l'importance, les autres peuvent être supprimées — ce qui réduit le bruit et améliore potentiellement le LSTM.

### Implémentation

Ajouter l'export de l'importance dans `src/models/random_forest.py`, dans `save_random_forest_artifacts` :

```python
import json
import numpy as np

importance_data = sorted(
    zip(result["feature_columns"], result["model"].feature_importances_),
    key=lambda x: x[1],
    reverse=True,
)
(destination / "feature_importance.json").write_text(
    json.dumps([{"feature": f, "importance": float(i)} for f, i in importance_data], indent=2),
    encoding="utf-8",
)
```

Ajouter la visualisation dans `src/utils/visualization.py` :

```python
def plot_feature_importance(
    feature_names: list[str],
    importances: list[float],
    output_path: Path,
    top_n: int = 20,
    title: str = "Feature importance",
) -> None:
    """Bar chart of top_n most important features."""
    import matplotlib.pyplot as plt

    pairs = sorted(zip(feature_names, importances), key=lambda x: x[1], reverse=True)[:top_n]
    names, values = zip(*pairs)

    fig, ax = plt.subplots(figsize=(10, 6))
    ax.barh(range(len(names)), values[::-1])
    ax.set_yticks(range(len(names)))
    ax.set_yticklabels(list(reversed(names)))
    ax.set_xlabel("Importance (Gini)")
    ax.set_title(title)
    fig.tight_layout()
    fig.savefig(output_path, dpi=120)
    plt.close(fig)
    logger.info("feature importance plot saved to %s", output_path)
```

Appeler depuis `save_random_forest_artifacts` après l'export JSON :

```python
from src.utils.visualization import plot_feature_importance

plot_feature_importance(
    result["feature_columns"],
    result["model"].feature_importances_.tolist(),
    destination / "feature_importance.png",
    title="Random Forest — feature importance",
)
```

### Ce qu'on cherche

Après `make train-rf`, ouvrir `artifacts/random_forest/{run_id}/feature_importance.png` ou dans MLflow UI → Artifacts.

Questions auxquelles répondre :
- Quelle famille d'indicateurs domine ? (returns ? RSI ? MACD ?)
- Est-ce que `sma_20` et `sma_50` apportent quelque chose au-delà de `ema_12` et `ema_26` ?
- Est-ce que les features de volume (`volume_sma_20`) ont de l'importance ?
- Y a-t-il des features avec importance < 0.5% qu'on peut supprimer ?

### Preuve observable

```bash
make train-rf
open artifacts/random_forest/$(ls -t artifacts/random_forest/ | head -1)/feature_importance.png
```

---

## Step 2 : Corriger le biais SELL du LSTM

### Diagnostic

recall SELL=0.15 signifie que le LSTM manque 85% des baisses réelles. Cause probable : les 3 ans de données BTC (2023-2026) couvrent une période majoritairement haussière. Le modèle a appris que "la plupart du temps, ça monte ou ça reste stable" — ce qui est statistiquement vrai mais inutile pour un signal de trading.

### Option A — Focal loss avec gamma élevé (recommandée)

Modifier `config.yaml` :

```yaml
training:
  loss: focal
  focal_gamma: 3.0       # 2.0 par défaut, augmenter pénalise davantage les exemples difficiles
  use_class_weights: true
```

Le gamma plus élevé (3.0 vs 2.0) concentre l'apprentissage sur les exemples où le modèle est le moins confiant — typiquement les SELL, qui sont sous-représentés dans la dynamique apprise.

Lancer `make train-lstm` et comparer le recall SELL dans les logs :

```text
# Cible itération v2 :
lstm class_metrics label=SELL precision=? recall=>0.30 f1=>0.30
```

### Option B — Pondération SELL renforcée manuellement

Si la focal loss seule ne suffit pas, surpondérer SELL au-delà du `balanced` automatique :

```python
# Dans src/models/lstm.py, remplacer le calcul auto des class_weights par :
SELL_ID = settings.label_to_id["SELL"]
HOLD_ID = settings.label_to_id["HOLD"]
BUY_ID  = settings.label_to_id["BUY"]

manual_weights = {SELL_ID: 2.0, HOLD_ID: 0.5, BUY_ID: 1.0}
class_weights_tensor = torch.tensor(
    [manual_weights[i] for i in sorted(manual_weights)],
    dtype=torch.float32,
)
```

Exposer ces poids dans `config.yaml` si on veut les rendre configurables :

```yaml
training:
  use_class_weights: true
  class_weight_override:
    SELL: 2.0
    HOLD: 0.5
    BUY: 1.0
```

### Friction attendue

Un recall SELL élevé peut dégrader la precision SELL (plus de faux positifs SELL). L'objectif n'est pas d'optimiser SELL isolément mais d'équilibrer le recall entre les trois classes. Cible :

| Label | recall cible v2 |
|---|---|
| SELL | > 0.30 |
| HOLD | > 0.45 |
| BUY | > 0.40 |

### Preuve observable

```bash
make train-lstm
# Chercher dans les logs :
# lstm class_metrics label=SELL recall=0.XX
```

Si recall SELL > 0.30 et directional_accuracy > 0.40, le biais est corrigé.

---

## Step 3 : Tuning LSTM

À exécuter uniquement après step 2 (biais SELL corrigé).

### Hyperparamètres à modifier dans `config.yaml`

```yaml
models:
  lstm:
    hidden_size: 128       # 64 → 128 : capacité de représentation
    sequence_length: 128   # 64 → 128 : contexte temporel plus long (~5 jours)

training:
  epochs: 100              # 50 → 100
  early_stopping:
    patience: 15           # 7 → 15 : laisser plus de temps avant d'arrêter
    min_delta: 0.0002      # 0.0005 → 0.0002 : détecter des améliorations plus fines
```

### Pourquoi ces valeurs

| Paramètre | Avant | Après | Raison |
|---|---|---|---|
| `hidden_size` | 64 | 128 | 25 000 lignes justifient plus de paramètres |
| `sequence_length` | 64 | 128 | ~5 jours de contexte vs ~2.7 jours — capturer les cycles hebdomadaires |
| `patience` | 7 | 15 | Éviter l'early stopping prématuré sur des plateaux de validation |

### Risque

Avec `hidden_size=128` et `sequence_length=128`, la mémoire GPU/CPU augmente. Sur CPU :
- Temps d'entraînement estimé : 3-5× plus long
- Si trop lent, réduire `batch_size: 16` (vs 32) pour compenser

### Preuve observable

```bash
make train-lstm
# Comparer avec le run précédent dans MLflow UI :
make mlflow-ui  # → http://localhost:5001
# Sélectionner les deux runs LSTM → Compare → f1_macro, directional_accuracy
```

---

## Indicateurs de succès itération v2

| Indicateur | Valeur actuelle | Cible v2 | Alerte |
|---|---|---|---|
| LSTM recall SELL | 0.147 | > 0.30 | < 0.20 → biais non corrigé |
| LSTM recall BUY | 0.610 | 0.40–0.55 | > 0.65 → toujours biaisé |
| LSTM directional_accuracy | 0.328 | > 0.42 | ≤ 0.333 → signaux non discriminants |
| LSTM f1_macro | 0.410 | > 0.44 | < 0.41 → régression |
| RF f1_macro | 0.422 | > 0.43 (après features simplifiées) | < 0.40 → régression |

---

## Makefile — aucun changement requis

Les steps 1, 2 et 3 utilisent les mêmes commandes :

```bash
make train-rf       # step 1 — après ajout feature_importance
make train-lstm     # step 2 et 3 — config.yaml modifié suffit
make mlflow-ui      # comparer les runs entre eux
```
