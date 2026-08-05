---
title: Plan d'itération v1 — après diagnostic premiers résultats
description: Implémentation des correctifs prioritaires suite au diagnostic du run 20260601.
nav_title: Itération v1
---

Ce document est la suite directe de [04-diagnostic-premiers-resultats.md](../analyse/04-diagnostic-premiers-resultats.md). Il décrit l'ordre d'implémentation recommandé pour sortir du modèle dégénéré.

**Prérequis :** le pipeline MVP (collect → features → train → mlops) fonctionne. Les runs sont tracés. Le problème n'est pas l'infrastructure, c'est la donnée et la labellisation.

---

## Step 1 : Collecte paginée — 3+ ans d'historique (bloquant)

Sans données suffisantes, aucun des steps suivants n'est significatif. C'est le déblocant principal.

Pseudo-contrat :

```python
def collect_klines_paginated(
    symbol: str,
    interval: str,
    target_rows: int,
    end_time: datetime | None = None,
) -> pd.DataFrame:
    """
    Fetch klines backwards from end_time until target_rows is reached.
    Returns a time-ordered DataFrame.
    """
```

Logique de pagination :

```python
frames = []
cursor = end_time or datetime.utcnow()

while sum(len(f) for f in frames) < target_rows:
    df = fetch_klines(symbol, interval, end_time=cursor, limit=1000)
    if df.empty:
        break
    frames.append(df)
    cursor = df["open_time"].min() - timedelta(milliseconds=1)

result = pd.concat(frames).drop_duplicates("open_time").sort_values("open_time")
```

Cibles d'historique :

| Symbole | Intervalle | Cible lignes | Couverture approx |
|---|---|---:|---|
| BTCUSDT | 1h | 26 000 | 3 ans |
| BTCETH | 1h | 26 000 | 3 ans |

Paramètre config à ajouter :

```yaml
data:
  collection:
    target_rows: 26000
    mode: paginated   # "single" (actuel) ou "paginated"
```

Friction : la pagination inverse depuis Binance peut retourner des gaps si un symbole n'existait pas à une période donnée.

Résolution : logger chaque page avec `start`, `end`, `rows_fetched`. Détecter les gaps > 2× l'intervalle et les tracer dans le rapport qualité. Ne pas échouer sur un gap — continuer et documenter.

Preuve observable :

```bash
make collect
wc -l data/raw/BTCUSDT/1h.csv   # ~26000
```

Spec complète dans [04-spec-collecte-paginee.md](../specs/04-spec-collecte-paginee.md).

---

## Step 2 : Baselines honnêtes dans mlruns

Avant tout tuning de modèle, implémenter deux baselines et les enregistrer dans le tracker MLOps. Elles servent de plancher de comparaison à chaque run suivant.

```python
# src/models/baselines.py

class AlwaysHoldClassifier:
    """Prédit toujours HOLD. Plancher d'accuracy sur données déséquilibrées."""
    def predict(self, X):
        return np.full(len(X), fill_value=LABEL_HOLD)

class UniformRandomClassifier:
    """Prédit aléatoirement parmi les 3 classes. Plancher f1_macro."""
    def predict(self, X):
        return np.random.choice([LABEL_BUY, LABEL_HOLD, LABEL_SELL], size=len(X))
```

Commande Makefile à ajouter :

```makefile
train-baselines:
    $(PYTHON) -m src.main --config config.yaml train-baselines \
        --dataset data/processed/BTCUSDT/1h_features.parquet
```

Sortie attendue dans mlruns :

```text
mlruns/cryptobot-mvp-models/always_hold/{run_id}/metrics.json
mlruns/cryptobot-mvp-models/random_classifier/{run_id}/metrics.json
```

Friction : les baselines ne sont pas des modèles sklearn ou PyTorch standard — le tracker attend un `model.joblib`.

Résolution : wrapper les baselines dans une interface commune `BasePredictor` qui expose `.predict()` et sérialise via `joblib`. Ne pas forcer une signature sklearn.

Preuve observable :

```bash
make train-baselines
cat mlruns/cryptobot-mvp-models/always_hold/*/metrics.json
# accuracy ~0.60, f1_macro ~0.25 -> plancher connu
```

---

## Step 3 : Métriques honnêtes par classe

Ajouter systématiquement deux éléments à chaque évaluation :

### 3a — Rapport classification par classe

```python
from sklearn.metrics import classification_report

report = classification_report(
    y_test, y_pred,
    target_names=["SELL", "HOLD", "BUY"],
    output_dict=True,
)
# logger chaque classe :
for label in ["SELL", "HOLD", "BUY"]:
    logger.info(
        "classification %s precision=%.4f recall=%.4f f1=%.4f support=%d",
        label,
        report[label]["precision"],
        report[label]["recall"],
        report[label]["f1-score"],
        report[label]["support"],
    )
```

Ce log rend un modèle dégénéré immédiatement visible : recall BUY = 0.0, recall SELL = 0.0.

### 3b — Directional accuracy réelle

Remplacer la métrique actuelle (identique à l'accuracy) par une mesure directionnelle :

```python
def directional_accuracy(y_true: np.ndarray, prices: pd.Series) -> float:
    """
    Fraction des prédictions dont le signe de mouvement correspond
    au mouvement réel du prix sur la période suivante.
    BUY -> +1, SELL -> -1, HOLD -> 0 (exclu du calcul).
    """
    SIGNAL_MAP = {LABEL_BUY: 1, LABEL_SELL: -1, LABEL_HOLD: 0}
    price_direction = np.sign(prices.diff().iloc[-len(y_true):].values)
    predicted_direction = np.array([SIGNAL_MAP[y] for y in y_true])

    mask = predicted_direction != 0  # exclure les HOLD
    if mask.sum() == 0:
        return float("nan")
    return (price_direction[mask] == predicted_direction[mask]).mean()
```

Friction : la série `prices` doit être alignée temporellement sur `y_true`. Le découpage temporel strict doit être respecté.

Résolution : passer `prices_test` aux fonctions d'évaluation depuis le trainer. Tracer `nan` si aucun signal actif n'est émis — c'est un indicateur critique (modèle dégénéré).

Preuve observable :

```text
# Modèle dégénéré :
directional_accuracy = nan   (0 prédictions actives)

# Modèle fonctionnel :
directional_accuracy = 0.52  (52% des signaux actifs ont le bon sens)
```

---

## Step 4 : Rééquilibrage des classes

À appliquer après step 1 (plus de données) pour vérifier l'impact réel.

### 4a — Focal Loss pour LSTM

Remplace `CrossEntropyLoss` standard par une loss qui pénalise davantage les exemples mal classés des classes minoritaires :

```python
# src/models/losses.py

class FocalLoss(nn.Module):
    def __init__(self, gamma: float = 2.0, weight: torch.Tensor | None = None):
        super().__init__()
        self.gamma = gamma
        self.weight = weight

    def forward(self, logits: torch.Tensor, targets: torch.Tensor) -> torch.Tensor:
        ce = F.cross_entropy(logits, targets, weight=self.weight, reduction="none")
        pt = torch.exp(-ce)
        return ((1 - pt) ** self.gamma * ce).mean()
```

Paramètre config à ajouter :

```yaml
lstm:
  loss: focal        # "cross_entropy" (actuel) ou "focal"
  focal_gamma: 2.0
```

### 4b — Pondération explicite LSTM

Alternative plus simple : poids de classe calculés automatiquement depuis la distribution du train.

```python
from sklearn.utils.class_weight import compute_class_weight

weights = compute_class_weight(
    "balanced",
    classes=np.unique(y_train),
    y=y_train,
)
class_weights = torch.tensor(weights, dtype=torch.float32)
criterion = nn.CrossEntropyLoss(weight=class_weights)
```

### 4c — Révision des seuils de labellisation

Si HOLD > 70% sur une paire après step 1, le seuil de labellisation est trop conservateur. Implémenter une analyse du seuil optimal :

```python
# src/features/threshold_analysis.py

def analyse_label_distribution(
    df: pd.DataFrame,
    thresholds: list[float] = [0.001, 0.002, 0.005, 0.01, 0.02],
    horizon: int = 1,
) -> pd.DataFrame:
    """
    Pour chaque seuil, calcule la distribution BUY/SELL/HOLD.
    Retourne un DataFrame de comparaison.
    """
```

Cible : distribution ≥ 15% BUY, ≥ 15% SELL, ≤ 70% HOLD. Sous ces seuils, le modèle ne peut pas apprendre les signaux minoritaires.

Friction : un seuil trop bas génère du bruit (signal dans chaque bougie, même sans mouvement significatif).

Résolution : croiser la distribution des labels avec la volatilité historique. Utiliser un seuil relatif à la volatilité plutôt qu'absolu.

Preuve observable :

```bash
python -m src.features.threshold_analysis --symbol BTCUSDT --interval 1h
# threshold=0.001 : BUY=35%, SELL=33%, HOLD=32%
# threshold=0.005 : BUY=20%, SELL=19%, HOLD=61%
# threshold=0.01  : BUY=12%, SELL=11%, HOLD=77%
```

---

## Step 5 : TimeSeriesSplit pour Random Forest

Remplacer le split unique par 5 folds temporels pour une estimation robuste de la generalization.

```python
from sklearn.model_selection import TimeSeriesSplit, cross_validate

tscv = TimeSeriesSplit(n_splits=5, gap=0)
cv_results = cross_validate(
    rf_model,
    X, y,
    cv=tscv,
    scoring={"f1_macro": "f1_macro", "accuracy": "accuracy"},
    return_train_score=True,
)

logger.info(
    "random_forest cv f1_macro mean=%.4f std=%.4f",
    cv_results["test_f1_macro"].mean(),
    cv_results["test_f1_macro"].std(),
)
```

Friction : avec 1 000 lignes, les 5 folds donnent ~200 lignes de test par fold — trop peu pour être fiable. Cette étape est significative uniquement après step 1.

Résolution : activer seulement si `len(df) >= 5000`. Ajouter une guard clause et un warning explicite sinon.

---

## Ordre d'exécution recommandé

```text
Step 1 — Collecte paginée        ← BLOQUANT, faire en premier
Step 2 — Baselines               ← 30 min, faire avant tout train
Step 3 — Métriques par classe    ← 1h, toujours activé après
Step 4a — Focal loss LSTM        ← après step 1 + 3
Step 4b — Pondération LSTM       ← alternative à 4a
Step 4c — Seuils labellisation   ← si HOLD > 70% après step 1
Step 5 — TimeSeriesSplit RF      ← si len(df) >= 5000
```

---

## Indicateurs de succès itération v1

| Indicateur | Cible | Alerte |
|---|---|---|
| Lignes par symbole | ≥ 26 000 | < 5 000 → stop, step 1 non terminé |
| % HOLD labels | ≤ 70% | > 80% → revoir seuils |
| LSTM directional_accuracy | ≥ 0.50 (non nan) | nan → modèle dégénéré |
| f1_macro RF | > baseline always_hold | ≤ baseline → pas de valeur ajoutée |
| f1_macro LSTM | > baseline random | ≤ baseline → pas de valeur ajoutée |
| Recall BUY LSTM | > 0.10 | 0.0 → modèle dégénéré |
| Recall SELL LSTM | > 0.10 | 0.0 → modèle dégénéré |

---

## Mise à jour Makefile attendue

```makefile
collect-full:
    $(PYTHON) -m src.main --config config.yaml collect \
        --symbols BTCUSDT BTCETH --interval 1h --mode paginated

train-baselines:
    $(PYTHON) -m src.main --config config.yaml train-baselines \
        --dataset data/processed/BTCUSDT/1h_features.parquet

threshold-analysis:
    $(PYTHON) -m src.features.threshold_analysis \
        --symbol BTCUSDT --interval 1h
```
