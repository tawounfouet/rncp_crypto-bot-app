# Résultats — Itération v1

**Date :** 2026-06-01
**Runs de référence :** RF `20260601-200806` · LSTM `20260601-200926`
**Dataset :** `data/processed/BTCUSDC/1h_features.parquet` — 25 950 lignes

Contexte : première itération après le diagnostic du run dégénéré.
Voir [04-diagnostic-premiers-resultats.md](04-diagnostic-premiers-resultats.md) pour la base de comparaison.

---

## 1. Ce qui a changé

| Paramètre | MVP initial | Itération v1 |
|---|---|---|
| Lignes brutes | 1 000 | 26 000 |
| Couverture temporelle | ~41 jours | ~3 ans |
| Mode collecte | single | paginated (26 pages) |
| Pondération LSTM | aucune | class_weight auto (balanced) |
| Baselines de référence | aucune | always_hold + random_classifier |
| Métriques par classe | absentes | loggées à chaque run |
| directional_accuracy | identique à accuracy | accuracy sur signaux actifs seulement |

---

## 2. Distribution des labels

### BTCUSDC (25 950 lignes après features + dropna)

| Label | Count | % |
|---|---|---|
| HOLD | 12 828 | 49.4% |
| BUY | 6 758 | 26.0% |
| SELL | 6 364 | 24.5% |

**Lecture :** distribution quasi-équilibrée. La pondération automatique (`class_weight=balanced`) et les 26 000 candles couvrant plusieurs régimes de marché (bull, bear, sideways) permettent au modèle d'apprendre les trois classes.

### BTCETH (25 950 lignes)

| Label | Count | % |
|---|---|---|
| HOLD | 15 151 | 58.4% |
| BUY | 5 608 | 21.6% |
| SELL | 5 191 | 20.0% |

**Lecture :** BTCETH reste plus déséquilibré. La paire BTC/ETH a des mouvements moins marqués que BTC/USDC — l'horizon de labellisation `h=1` et le seuil fixe `0.002` capturent moins de signaux directionnels. À surveiller lors de l'itération v2.

---

## 3. Métriques des baselines

Ces valeurs sont les **planchers de référence** pour toute comparaison future.

| Baseline | accuracy | f1_macro | Interprétation |
|---|---|---|---|
| `always_hold` | 0.493 | 0.220 | Prédit HOLD à 100% — plancher accuracy sur données déséquilibrées |
| `random_classifier` | 0.334 | 0.325 | Prédit aléatoirement — plancher f1_macro |

Métriques par classe de `always_hold` :

| Label | precision | recall | f1 | support |
|---|---|---|---|---|
| SELL | 0.000 | 0.000 | 0.000 | 999 |
| HOLD | 0.493 | 1.000 | 0.661 | 1 920 |
| BUY | 0.000 | 0.000 | 0.000 | 974 |

---

## 4. Résultats Random Forest

**Run :** `20260601-200806` · Paramètres : `n_estimators=300, max_depth=8, min_samples_leaf=20, class_weight=balanced`

### Métriques globales

| Métrique | Valeur | vs always_hold | vs random |
|---|---|---|---|
| accuracy | 0.455 | — (inférieur, attendu) | +36% |
| f1_macro | **0.422** | **+92%** | **+30%** |
| precision_macro | 0.428 | — | +28% |
| recall_macro | 0.427 | — | +28% |

### Validation croisée temporelle (5 folds, TimeSeriesSplit)

| Métrique CV | Valeur |
|---|---|
| f1_macro mean | 0.405 |
| f1_macro std | 0.020 |

**Lecture :** l'écart-type de 0.020 indique une performance stable sur les 5 fenêtres temporelles. Le modèle n'est pas surappris sur une période particulière. L'écart `test_f1_macro - cv_f1_macro` = 0.017 est faible et dans la marge de variation.

### Statut

- ✅ Bat `always_hold` en f1_macro (+92%)
- ✅ Bat `random_classifier` en f1_macro (+30%)
- ✅ Stable sur 3 ans de données (CV std faible)
- ⚠️ accuracy < `always_hold` — normal sur données déséquilibrées, l'accuracy n'est pas la bonne métrique ici

---

## 5. Résultats LSTM

**Run :** `20260601-200926` · Paramètres : `hidden_size=64, num_layers=2, sequence_length=64, epochs=50, loss=cross_entropy, use_class_weights=true`

### Métriques globales

| Métrique | Valeur | vs always_hold | vs random |
|---|---|---|---|
| accuracy | 0.464 | — | +39% |
| f1_macro | **0.410** | **+86%** | **+26%** |
| precision_macro | 0.439 | — | +31% |
| recall_macro | 0.437 | — | +31% |
| directional_accuracy | 0.328 | — | ≈ random |
| best_validation_loss | 1.051 | — | < ln(3)=1.099 ✅ |
| epochs_trained | 16 | — | 2× plus qu'avant |

### Analyse de la directional_accuracy

`directional_accuracy = 0.328` signifie que parmi les prédictions actives (BUY ou SELL, hors HOLD), 32.8% ont le bon sens. Ce chiffre est légèrement en dessous du hasard (33%) — les signaux directionnels du LSTM ne sont pas encore discriminants.

Interprétation : le LSTM apprend à identifier quand un mouvement va se produire (il émet des signaux plutôt que de tout prédire HOLD), mais pas encore dans quelle direction. Les features actuelles ne capturent pas suffisamment le momentum directionnel.

**Point clé :** `best_validation_loss = 1.051 < ln(3) = 1.099`. Le modèle dépasse la loss d'un prédicteur purement aléatoire — preuve qu'il a appris quelque chose sur la distribution. C'était impossible avec 1 000 lignes.

### Statut

- ✅ Bat les deux baselines en f1_macro
- ✅ Émet des signaux actifs BUY/SELL (directional_accuracy non NaN)
- ✅ best_val_loss < entropie maximale
- ⚠️ directional_accuracy ≈ 1/3 — signaux directionnels non discriminants
- ⚠️ f1_macro LSTM (0.410) légèrement inférieur à RF (0.422) — le LSTM n'exploite pas encore mieux la structure temporelle

---

## 6. Comparaison synthétique

| Modèle | f1_macro | Rang | Statut |
|---|---|---|---|
| always_hold | 0.220 | 4 | Plancher |
| random_classifier | 0.325 | 3 | Plancher |
| LSTM | 0.410 | 2 | Valide — non exploitable |
| Random Forest | **0.422** | **1** | **Valide — non exploitable** |

Le Random Forest est **légèrement meilleur** que le LSTM sur ce dataset. Ce résultat est courant sur des features tabulaires bien construites : le LSTM n'a pas d'avantage évident quand les features ingéniérisées (RSI, MACD, Bollinger) capturent déjà la temporalité implicitement.

---

## 7. Ce que ça signifie pour le projet

**Signal positif :** l'itération v1 sort du modèle dégénéré. Les changements structurels (volume de données × 26, class weights, distribution équilibrée) ont suffi à débloquer l'apprentissage. Aucune modification d'architecture n'a été nécessaire.

**Limite actuelle :** un f1_macro de ~0.42 n'est pas suffisant pour générer des signaux de trading fiables. Un signal sur quatre est incorrect dans la classe la plus discriminante. La `directional_accuracy` LSTM à 0.33 indique que les signaux actifs sont encore équivalents au hasard en termes de direction.

**Ce que les modèles ont appris :** distinguer les régimes "actif" (mouvement ≥ 0.2%) des régimes "neutre". Ils n'ont pas encore appris à prédire la direction de manière fiable.

---

## 8. Analyse par classe LSTM — biais détecté

Les métriques par classe du run `20260601-202607` révèlent un pattern structurel :

| Label | precision | recall | f1 | support | Lecture |
|---|---|---|---|---|---|
| SELL | 0.337 | **0.147** | 0.204 | 983 | Détecte mal les baisses — sous-recall critique |
| HOLD | 0.652 | 0.555 | 0.600 | 1 887 | Classe la mieux apprise |
| BUY | 0.326 | **0.610** | 0.425 | 960 | Surprédit les hausses — recall élevé, beaucoup de faux positifs |

Le LSTM a un **biais BUY asymétrique** : il prédit trop de hausses et manque la majorité des baisses. Ce pattern est typique d'un modèle entraîné sur 3 ans de données BTC majoritairement haussières — il a intégré le biais directionnel du marché sous-jacent.

Conséquence directe sur la `directional_accuracy = 0.328` : les signaux actifs ne sont pas discriminants parce que le recall SELL est effondré. Le modèle émet des BUY corrects dans 61% des cas de hausse réelle, mais rate 85% des baisses réelles.

---

## 9. Prochaines priorités

Trois axes par ordre d'impact, issus de l'analyse du biais SELL :

### Axe 1 — Feature importance RF (30 min, prioritaire)

RF a déjà calculé `feature_importances_` à l'entraînement. Il faut l'exporter et le visualiser pour répondre à : *RSI, MACD et Bollinger apportent-ils vraiment quelque chose, ou 3 features font-elles 80% du travail ?* La réponse oriente directement les axes 2 et 3.

### Axe 2 — Corriger le biais SELL du LSTM

Le recall SELL à 0.15 est le principal blocage de la `directional_accuracy`. Solutions concrètes :

- **Option A — Focal loss** : passer `loss: focal` + `focal_gamma: 3.0` dans `config.yaml`. La focal loss pénalise davantage les exemples difficiles (SELL sous-représentés dans l'apprentissage).
- **Option B — Pondération SELL renforcée** : surpondérer SELL au-delà du `balanced` automatique en calculant les poids manuellement.

Les deux options sont implémentées, il suffit de changer la config.

### Axe 3 — Tuning LSTM (après biais corrigé)

Augmenter la capacité du modèle : `hidden_size: 128`, `sequence_length: 128`, `epochs: 100`, `patience: 15`. Avec 25 000 lignes le modèle peut absorber plus de paramètres — mais ce tuning ne sert à rien tant que le biais SELL persiste.

---

**Ordre d'exécution recommandé :**

```text
Axe 1 → feature importance   (diagnostic, oriente tout)
Axe 2 → biais SELL           (fix le blocage principal)
Axe 3 → tuning LSTM          (amplifier un modèle déjà juste)
```

Voir [06-plan-iteration-v2.md](../implementation/06-plan-iteration-v2.md) pour le détail d'implémentation.
