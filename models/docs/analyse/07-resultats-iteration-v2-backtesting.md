# Résultats — Itération v2 : order flow, backtesting, roadmap papier

**Date :** 2026-06-02
**Contexte :** Itération post-feature importance RF. Ajout features order flow + module backtesting.

---

## 1. LSTM v4 — order flow + balanced weights

**Run :** `20260601-235709` · Config : cross_entropy + balanced, hidden=128, seq=128, epochs=100

| Métrique | v1 (baseline) | v4 (order flow) | Delta |
|---|---|---|---|
| f1_macro | 0.410 | **0.415** | +0.005 |
| accuracy | 0.464 | **0.480** | +0.016 |
| SELL recall | 0.147 | 0.161 | +0.014 |
| HOLD recall | 0.555 | **0.644** | +0.089 |
| BUY recall | 0.610 | **0.485** | −0.125 |
| directional_accuracy | 0.328 | **0.334** | +0.006 |

**Lecture :** Les features order flow (`buy_pressure_ratio`, `volume_delta`, `trade_size_avg`) ont partiellement corrigé le biais BUY (−0.125) et amélioré le recall HOLD (+0.089). Le modèle distingue mieux les régimes neutres des hausses. SELL reste le point faible (recall 0.161).

### Historique des runs LSTM

| Config | f1_macro | SELL recall | HOLD recall | BUY recall | Verdict |
|---|---|---|---|---|---|
| v1 : CE + balanced 64/64 | 0.410 | 0.147 | 0.555 | 0.610 | Référence |
| v2 : Focal γ=3 + balanced 128/128 | 0.327 | 0.288 | 0.166 | 0.744 | Sur-correction |
| v3 : CE + asym 128/128 | 0.327 | 0.288 | 0.166 | 0.744 | Identique v2 |
| **v4 : CE + balanced + order flow** | **0.415** | **0.161** | **0.644** | **0.485** | **Meilleur** |

---

## 2. Premier backtesting — découverte critique

### Résultats RF sans filtre de signal (min_hold_bars=1)

| Métrique trading | RF | Interprétation |
|---|---|---|
| strategy_return | **−71.9%** | Capital quasi-détruit |
| buy_and_hold_return | −18.7% | Période test baissière |
| excess_return | **−53.2%** | Pire que rien |
| max_drawdown | −72.1% | Quasi-faillite |
| sharpe_ratio | −1.59 | Signal négatif |
| win_rate | 69% | 69% des trades gagnants individuellement |
| **n_trades** | **481** | ← Problème principal |
| **fees_paid** | **55.8%** | Frais seuls = destruction du capital |

**Diagnostic :** f1_macro=0.42 masquait un problème de fréquence de trading. Le modèle change de signal à chaque bougie (1h), générant 481 trades sur ~4 mois = un trade toutes les 8h. Les frais Binance spot (0.1% par trade) cumulés sur 481 trades absorbent 55% du capital. Le signal est juste mais le surtrading le rend inexploitable.

**La win_rate de 69% est révélatrice :** le modèle prédit correctement la direction sur 7 trades sur 10, mais est ruiné par les frais. C'est un signal utile qui nécessite un filtre de persistence, pas un signal inutile.

### Résultats RF avec filtre min_hold_bars=3

| Métrique trading | Sans filtre | Avec filtre (3 bars) | Delta |
|---|---|---|---|
| strategy_return | −71.9% | **−33.3%** | +38.6pp |
| excess_return | −53.2% | **−14.6%** | +38.6pp |
| max_drawdown | −72.1% | **−33.6%** | +38.5pp |
| sharpe_ratio | −1.59 | **−0.68** | +0.91 |
| win_rate | 69% | **75.7%** | +6.7pp |
| n_trades | 481 | **181** | −62% |
| fees_paid | 55.8% | **31.2%** | −24.6pp |

**Lecture :** Ne trader qu'après 3 bougies consécutives avec le même signal réduit les trades de 62% et améliore le Sharpe de −1.59 à −0.68. La stratégie reste perdante sur cette période mais pour des raisons de contexte marché (test period baissière, BTC −18.7%), pas uniquement de qualité de signal.

### Contexte marché du test set

Le test set couvre les 15% les plus récents du dataset (≈ 4 derniers mois). La période est baissière pour BTC (buy-and-hold = −18.7%). Notre modèle est **long-only** (`allow_short: false`) — il ne peut pas exploiter les signaux SELL en prenant des positions courtes. Dans un marché baissier, une stratégie long-only vs buy-and-hold est structurellement pénalisée parce que :

- Buy-and-hold : tient la position, bénéficie de tout rebond
- Long-only signal : sort lors des baisses (HOLD/SELL), rate certains rebonds à cause des frais de rentrée

**L'activation du short (`allow_short: true`) changerait significativement les résultats sur ce test period.**

---

## 3. Ce que le backtesting enseigne — confirmation du papier

Le papier "Cryptocurrency Price Prediction Algorithms" (John, Binnewies, Stantic, 2024) critique exactement ce pattern : beaucoup de modèles affichent de bonnes métriques ML mais n'évaluent pas la profitabilité réelle après frais.

**Notre cas est un exemple parfait :**

| Métrique ML | Valeur | Message trompeur |
|---|---|---|
| f1_macro | 0.42 | "Modèle correct à 42%" |
| accuracy | 0.45 | "45% de prédictions justes" |
| win_rate | 69% | "69% des trades profitables" |

| Métrique trading | Valeur | Message réel |
|---|---|---|
| strategy_return | −72% | Capital détruit |
| excess_return | −53% | Bien pire que ne rien faire |
| fees_paid | 55% | Frais seuls = destruction |

La divergence entre win_rate (69%) et strategy_return (−72%) est la signature classique d'un modèle qui sur-trade : chaque trade individuel est souvent correct, mais la friction de trading (frais + slippage) dépasse les profits cumulés.

---

## 4. Recommandations d'intégration du papier — roadmap

Analyse croisée entre les recommandations du survey et l'état du projet.

### P0 — Immédiat (corriger les gaps bloquants)

| Action | Statut | Impact |
|---|---|---|
| Backtest avec frais ✅ | Implémenté | Révèle le surtrading |
| Filtre min_hold_bars ✅ | Implémenté (=3) | −62% trades, +38pp return |
| Order flow features ✅ | Implémenté | HOLD recall +9%, BUY bias réduit |
| Exclure price_inverted ✅ | Implémenté | 0% importance supprimée |
| `order_flow_imbalance` (centré en 0) | À faire | Meilleure normalisation que buy_pressure_ratio |

### P1 — Prochaine itération (v2.1)

| Action | Justification |
|---|---|
| Walk-forward validation | TimeSeriesSplit actuel = approximation. Vrai walk-forward = un fold par trimestre |
| LightGBM/XGBoost | Souvent meilleur que RF sur features tabulaires + order flow |
| `allow_short: true` backtest | Quantifie la valeur des signaux SELL non exploités |
| Permutation importance sur test temporel | Valider que RF importance n'est pas biaisée par corrélations |

### P2 — Itération v2.2

| Action | Justification |
|---|---|
| Rolling features order flow | `buy_pressure_ratio_ma_3`, `ofi_sum_6`, etc. — avantage LSTM |
| Ablation study famille TA | Tester sans RSI/MACD/SMA — est-ce qu'on perd vraiment quelque chose ? |
| Métriques Sharpe/Sortino loggées par défaut | Déjà en place via bt_ prefix dans MLflow |
| BTCETH order flow semantics | Clarifier l'inversion avant d'utiliser order flow sur BTCETH |

### P3 — Post-MVP (research)

| Action | Justification |
|---|---|
| GRU / LSTM-GRU | Architectures hybrides légèrement meilleures |
| Reddit sentiment | API accessible, données r/CryptoCurrency |
| Blockchain features | hash rate, fees, active addresses |
| Transformer Encoder | Expérimental, coût élevé |

### Ce qu'on ne fait pas (et pourquoi)

| Exclusion | Raison |
|---|---|
| Optimisation de portefeuille | Hors scope DST MVP |
| Live trading | Risque financier, hors validation ML |
| Kafka / Airflow | Surdimensionné avant que le signal soit prouvé rentable |

---

## 5. Prochaine priorité absolue

Avant d'ajouter de nouveaux modèles : **quantifier l'impact de `allow_short: true`** sur le backtest avec min_hold_bars=3. Si les signaux SELL sont rentables en position courte sur le test period baissier, ça valide que le signal est utile même si la stratégie long-only ne peut pas l'exploiter pleinement.

```bash
# Test rapide en changeant config.yaml :
# backtesting.allow_short: true
make train-rf
# Comparer bt_strategy_return et bt_excess_return
```
