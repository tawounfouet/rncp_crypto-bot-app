# Diagnostic — Premiers résultats d'entraînement

**Date :** 2026-06-01
**Run de référence :** `20260601-193838` (Random Forest), `20260601-193849` (LSTM)
**Dataset :** `data/processed/BTCUSDT/1h_features.parquet` — 950 lignes, 35 colonnes, 27 features

---

## 1. Résumé exécutif

Le premier pipeline complet (`collect → features → train-rf → train-lstm`) s'exécute sans erreur. Les artefacts sont produits, les runs sont tracés dans `mlruns/`, les model cards sont générées. L'infrastructure fonctionne.

En revanche, les deux modèles sont inexploitables pour générer des signaux de trading. Ils n'ont rien appris de discriminant : ils prédisent la classe majoritaire (HOLD) sur la quasi-totalité des exemples de test. Le problème n'est pas l'architecture, c'est la donnée et la labellisation.

---

## 2. Métriques observées

### Random Forest

| Métrique | Valeur |
|---|---|
| accuracy | 0.3986 |
| precision_macro | 0.3184 |
| recall_macro | 0.4050 |
| f1_macro | 0.2975 |

Accuracy inférieure à la baseline aléatoire (0.333). Le modèle n'est pas un prédicteur neutre — il est activement mauvais sur certaines classes.

### LSTM

| Métrique | Valeur | Interprétation |
|---|---|---|
| accuracy | 0.6125 | Trompeuse — reflète la proportion de HOLD dans le test |
| precision_macro | 0.2041 ≈ 0.6125/3 | Une seule classe prédite |
| recall_macro | 0.3333 = 1/3 | Recall parfait sur HOLD, zéro sur BUY et SELL |
| f1_macro | 0.2532 | Indicateur réel de la qualité discriminante |
| directional_accuracy | 0.6125 | **Identique à accuracy** — métrique redondante |
| best_validation_loss | 1.001 | Proche de ln(3) ≈ 1.099 — quasi aléatoire |
| epochs_trained | 8 | Early stopping après 1 epoch sans amélioration |

### Signal d'alarme : la trahison des chiffres

```
recall_macro = 1/3 exactement
precision_macro ≈ accuracy / 3
```

Quand le recall macro vaut exactement 1/3 sur 3 classes, le modèle attribue toute la masse à une seule classe : recall = 1.0 pour HOLD, recall = 0.0 pour BUY et SELL, moyenne = 0.333. Ce n'est pas de la chance — c'est la signature mathématique d'un modèle dégénéré.

---

## 3. Distribution des labels

### BTCUSDT 1h (950 lignes après dropna)

| Label | Train (665) | Val (142) | Test (143) | % global |
|---|---|---|---|---|
| HOLD | 568 (après label_report) | — | — | ~60% |
| SELL | 203 | — | — | ~21% |
| BUY | 193 | — | — | ~20% |

### BTCETH 1h (950 lignes)

| Label | Count | % |
|---|---|---|
| HOLD | 757 | 79.7% |
| BUY | 102 | 10.7% |
| SELL | 91 | 9.6% |

BTCETH est particulièrement déséquilibré (~80% HOLD). La labellisation actuelle capture mal les mouvements réels du marché.

---

## 4. Causes racines identifiées

### 4.1 Déséquilibre de classes structurel

En crypto horaire, la majorité des bougies ne franchissent pas les seuils BUY/SELL. Le modèle minimise la cross-entropy en prédisant toujours la classe majoritaire — c'est le comportement rationnel face à un déséquilibre non compensé.

`class_weight=balanced` est configuré pour le Random Forest mais pas pour la loss LSTM.

### 4.2 Dataset insuffisant

| Contrainte | Valeur |
|---|---|
| Lignes brutes | 1 000 candles |
| Lignes après dropna | 950 |
| Couverture temporelle | ~41 jours (1 000 × 1h) |
| Séquences LSTM (seq_len=64) | ~886 au total |
| Séquences de test | 80 |

80 exemples de test ne permettent pas d'estimer les métriques de façon fiable. Une variation de 5 prédictions modifie l'accuracy de 6 points. Le signal est noyé dans le bruit statistique.

Pour un LSTM sur données financières, la littérature recommande 50 000+ observations minimum avant d'espérer un apprentissage non trivial.

### 4.3 Sous-entraînement du LSTM

La `best_validation_loss = 1.001` est à comparer à `ln(3) = 1.0986` (entropie d'un prédicteur aléatoire uniforme). Le modèle atteint une loss de 1.001 en apprenant simplement la distribution a priori des classes. Il n'a pas besoin d'apprendre de structure temporelle pour descendre à ce niveau.

L'early stopping s'est déclenché à epoch 8 avec `patience=7` — ce qui signifie que la validation loss n'a pas bougé favorablement après l'epoch 1. La descente s'est bloquée immédiatement.

### 4.4 Métrique `directional_accuracy` redondante

`directional_accuracy = accuracy = 0.6125`. Une vraie directional accuracy mesure si le signe du mouvement prix prédit est correct, indépendamment du label de classe. Ici elle est calculée de façon identique à l'accuracy — elle n'apporte aucune information supplémentaire et peut induire en erreur.

---

## 5. Ce que ça signifie pour le projet

Le pipeline d'infrastructure est validé :
- Collecte Binance → Parquet/CSV/JSONL + metadata ✅
- Feature engineering (10 familles d'indicateurs) ✅
- Tracking MLOps (params, métriques, artefacts, config snapshot) ✅
- Registry best model ✅
- Model card automatique ✅

Ce qui n'est pas validé :
- La capacité des features à discriminer BUY/SELL/HOLD ✗
- La labellisation comme proxy utile du signal de trading ✗
- L'apprentissage LSTM de structure temporelle sur ce volume ✗

---

## 6. Recommandations

### Priorité 1 — Plus de données (bloquant)

Augmenter l'historique de 1 000 → 50 000 candles minimum.

```yaml
# config.yaml
binance:
  limit: 1000   # max par appel Binance
```

Binance limite à 1 000 candles par appel mais n'impose pas de limite sur l'historique paginé. Implémenter une collecte paginée :

```python
# Pseudo-code collecte paginée
end_time = now()
frames = []
while len(total_rows) < target:
    df = fetch_klines(symbol, interval, end_time=end_time, limit=1000)
    frames.append(df)
    end_time = df["open_time"].min() - 1  # page précédente
```

Pour BTCUSDT 1h, 3 ans d'historique = ~26 000 candles. Viser 3–5 ans.

### Priorité 2 — Rééquilibrage des classes

**Option A — Focal Loss (LSTM) :**

```python
class FocalLoss(nn.Module):
    def __init__(self, gamma=2.0, weight=None):
        super().__init__()
        self.gamma = gamma
        self.weight = weight

    def forward(self, logits, targets):
        ce = F.cross_entropy(logits, targets, weight=self.weight, reduction="none")
        pt = torch.exp(-ce)
        return ((1 - pt) ** self.gamma * ce).mean()
```

**Option B — Repondération des seuils de labellisation :**

Le seuil actuel qui génère 60–80% de HOLD est probablement trop conservateur. Ajuster `threshold_pct` dans la fonction de labellisation pour réduire la zone HOLD.

**Option C — SMOTE sur les features (Random Forest) :**

```python
from imblearn.over_sampling import SMOTE
X_resampled, y_resampled = SMOTE(random_state=42).fit_resample(X_train, y_train)
```

### Priorité 3 — Baseline honnête

Avant tout tuning, implémenter deux baselines et les tracer dans mlruns :

| Baseline | Description | Expected accuracy |
|---|---|---|
| Always HOLD | Prédit HOLD à 100% | ~60% sur BTCUSDT |
| Random uniform | Prédit aléatoirement 1/3 chaque | ~33% |

Tout modèle en dessous de la baseline "Always HOLD" en accuracy, ou en dessous du random en f1_macro, doit être considéré comme non formé.

### Priorité 4 — Métriques honnêtes

Remplacer `directional_accuracy` par une vraie mesure directionnelle :

```python
def directional_accuracy(y_true_labels, prices):
    """Fraction des prédictions dont le signe de mouvement prédit est correct."""
    price_moves = np.sign(prices.diff().dropna())
    predicted_moves = label_to_sign(y_true_labels)  # BUY→+1, SELL→-1, HOLD→0
    return (price_moves == predicted_moves).mean()
```

Ajouter systématiquement la matrice de confusion par classe dans les logs :

```
              precision  recall  f1-score
BUY               0.00    0.00      0.00
SELL              0.00    0.00      0.00
HOLD              0.61    1.00      0.76
```

Cet affichage rend le modèle dégénéré immédiatement visible.

### Priorité 5 — Validation croisée temporelle (Random Forest)

Remplacer le split unique par `TimeSeriesSplit` :

```python
from sklearn.model_selection import TimeSeriesSplit
tscv = TimeSeriesSplit(n_splits=5)
scores = cross_val_score(rf, X, y, cv=tscv, scoring="f1_macro")
```

Cela donne une estimation plus robuste sur données financières et détecte le surapprentissage sur une période spécifique.

---

## 7. Plan d'action proposé

| Étape | Action | Impact attendu | Effort |
|---|---|---|---|
| 1 | Collecte paginée → 3 ans BTCUSDT | Débloquer l'apprentissage | Moyen |
| 2 | Baseline always-HOLD + random dans mlruns | Référence honnête | Faible |
| 3 | Matrice de confusion dans les logs | Diagnostic immédiat | Faible |
| 4 | Focal loss LSTM + class_weight explicite | Rééquilibre | Faible |
| 5 | Revue seuils labellisation | Réduire HOLD dominant | Moyen |
| 6 | `directional_accuracy` réelle | Métrique business utile | Faible |
| 7 | TimeSeriesSplit pour RF | Estimation robuste | Faible |

Les étapes 2, 3, 6 sont des changements de métriques/reporting — elles ne modifient pas le comportement du modèle mais rendent le diagnostic immédiat à chaque run.

---

## 8. Conclusion

> En l'état, les deux modèles sont des baselines « toujours HOLD » déguisées. Le problème est moins l'architecture que la quantité de données et la qualité de la labellisation. Le pipeline infrastructure est sain — c'est le point de départ pour les itérations suivantes.

Le risque documenté dans [03-risques-hypotheses.md](03-risques-hypotheses.md) sur le déséquilibre de classes et le volume de données se matérialise dès le premier run. Les recommandations ci-dessus constituent la réponse directe à ces risques.
