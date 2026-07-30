# Feature importance Random Forest — analyse

**Date :** 2026-06-01
**Run :** `20260601-210403`
**Dataset :** `data/processed/BTCUSDT/1h_features.parquet` — 25 950 lignes

---

## 1. Classement complet

| Rang | Feature | Importance | Famille | Cumulé |
|---|---|---|---|---|
| 1 | `quote_asset_volume` | 14.1% | Volume microstructure | 14.1% |
| 2 | `taker_buy_quote_volume` | 11.5% | Order flow | 25.6% |
| 3 | `number_of_trades` | 9.3% | Market activity | 34.9% |
| 4 | `bb_width` | 7.1% | Volatilité | 42.0% |
| 5 | `volatility_20` | 6.2% | Volatilité | 48.2% |
| 6 | `volume` | 6.2% | Volume brut | 54.4% |
| 7 | `taker_buy_base_volume` | 5.6% | Order flow | 60.0% |
| 8 | `return_1` | 4.2% | Rendement prix | 64.2% |
| 9 | `return_3` | 3.8% | Rendement prix | 68.0% |
| 10 | `return_6` | 3.3% | Rendement prix | 71.3% |
| 11 | `volume_sma_20` | 3.0% | Volume moyen | 74.3% |
| 12 | `macd_hist` | 2.3% | TA oscillateur | 76.6% |
| 13 | `macd` | 2.3% | TA oscillateur | 78.9% |
| 14 | `rsi_14` | 2.3% | TA oscillateur | 81.2% |
| 15 | `macd_signal` | 2.2% | TA oscillateur | 83.4% |
| 16 | `open` | 1.8% | Prix brut | 85.2% |
| 17 | `close` | 1.7% | Prix brut | 86.9% |
| 18 | `bb_upper` | 1.7% | Bollinger | 88.6% |
| 19 | `low` | 1.6% | Prix brut | 90.2% |
| 20 | `high` | 1.5% | Prix brut | 91.7% |
| 21 | `ema_12` | 1.5% | Moyenne mobile | 93.2% |
| 22 | `sma_50` | 1.4% | Moyenne mobile | 94.6% |
| 23 | `ema_26` | 1.4% | Moyenne mobile | 96.0% |
| 24 | `sma_20` | 1.4% | Moyenne mobile | 97.4% |
| 25 | `bb_middle` | 1.3% | Bollinger | 98.7% |
| 26 | `bb_lower` | 1.3% | Bollinger | 100.0% |
| 27 | `price_inverted` | **0.0%** | Flag audit | — |

---

## 2. Observations

### Le vrai signal est l'order flow, pas le TA classique

Les 3 premières features (`quote_asset_volume`, `taker_buy_quote_volume`, `number_of_trades`) font **34.9% de l'importance** à elles seules. Ce sont des features de **microstructure de marché** — elles capturent la pression acheteuse réelle (takers) et l'activité du carnet d'ordres.

Le RF a découvert que "qui achète et combien" prédit mieux BUY/SELL/HOLD que les indicateurs techniques classiques. Ce résultat est cohérent avec la littérature de market microstructure : l'order flow imbalance (OFI) est l'un des prédicteurs à court terme les plus robustes en finance.

### RSI, MACD, SMA, EMA sont quasi-inutiles

| Indicateur | Importance | Interprétation |
|---|---|---|
| RSI 14 | 2.3% | Bruit de fond |
| MACD (ligne) | 2.3% | Bruit de fond |
| MACD hist | 2.3% | Bruit de fond |
| MACD signal | 2.2% | Bruit de fond |
| SMA 20 | 1.4% | Redondant |
| SMA 50 | 1.4% | Redondant |
| EMA 12 | 1.5% | Redondant |
| EMA 26 | 1.4% | Redondant |

Ces 8 features représentent ~14% de l'importance au total mais **aucune individuellement** ne dépasse le seuil de signal utile. Leurs valeurs sont très corrélées entre elles et avec les features de rendement et de prix brut.

### `price_inverted` = 0.0% — feature parasite

Ce flag (toujours `False` pour BTCUSDT, toujours `True` pour BTCETH) n'apporte aucun signal dans un dataset mono-symbole. À supprimer des features d'entraînement.

### `bb_width` et `volatility_20` sont utiles (7% + 6%)

La largeur de Bollinger et la volatilité rolling identifient les régimes de marché : quand la volatilité est haute, les signaux BUY/SELL sont plus forts (les mouvements dépassent plus souvent le seuil de labellisation). Ces deux features méritent d'être conservées.

---

## 3. Feature synthétique à ajouter

La feature manquante la plus évidente est le **ratio de pression acheteur** :

```python
buy_pressure_ratio = taker_buy_quote_volume / quote_asset_volume
```

Cette valeur oscille entre 0 (toutes les transactions initiées par les vendeurs) et 1 (toutes initiées par les acheteurs). Un ratio > 0.6 sur plusieurs bougies consécutives est un signal d'accumulation. C'est exactement le type d'information temporelle qu'un LSTM peut exploiter mieux qu'un RF.

Autres features synthétiques potentielles :
- `trade_size_avg = quote_asset_volume / number_of_trades` — taille moyenne des ordres (gros ordres = signal institutionnel)
- `volume_delta = taker_buy_base_volume - (volume - taker_buy_base_volume)` — delta volume (acheteurs - vendeurs en BTC)

---

## 4. Conséquences pour l'itération suivante

| Décision | Justification |
|---|---|
| Supprimer `price_inverted` des features | Importance 0, pollue le modèle |
| Ajouter `buy_pressure_ratio` | Feature synthétique haute valeur, non redondante |
| Conserver `bb_width` et `volatility_20` | Signal réel sur les régimes de marché |
| SMA/EMA/RSI/MACD : conserver pour l'instant | Retrait à tester empiriquement — faible mais non nul |
| LSTM sur order flow temporel | Séquences de `buy_pressure_ratio` = avantage structurel LSTM vs RF |

Voir [06-plan-iteration-v2.md](../implementation/06-plan-iteration-v2.md) pour le plan d'implémentation.
