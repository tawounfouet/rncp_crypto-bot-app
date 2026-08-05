# Contrats données et API

Statut: référence
Derniere revision: 2026-06-10

## Symboles supportés

| Nom canonique MVP | Variante Binance possible | Commentaire |
|---|---|---|
| `BTCUSDT` | `BTCUSDT` | paire BTC / USDT |
| `BTCETH` | `ETHBTC` avec inversion OHLC contrôlée | paire BTC / ETH demandée dans le cadrage |

Le symbole canonique reste `BTCETH` dans tout le projet. Binance Spot expose la paire inverse `ETHBTC`; le mapping est donc déclaré dans `config.yaml` via `data.symbol_mappings.BTCETH`.

Règles d'inversion :

- `open = 1 / source_open`
- `close = 1 / source_close`
- `high = 1 / source_low`
- `low = 1 / source_high`
- `volume` utilise le volume coté quand il est disponible, afin de représenter le volume dans l'actif de base canonique `BTC`
- `source_symbol` et `price_inverted` sont conservés dans le raw dataset pour auditabilité

## Donnée brute OHLCV

Formats attendus :

- primaire : `parquet`
- exports : `csv`, `jsonl`
- exemple contractuel : `json`

Schéma minimal :

```json
{
  "symbol": "BTCUSDT",
  "source_symbol": "BTCUSDT",
  "price_inverted": false,
  "interval": "1h",
  "open_time": "2026-05-01T00:00:00Z",
  "open": 60000.0,
  "high": 60500.0,
  "low": 59800.0,
  "close": 60200.0,
  "volume": 123.45,
  "close_time": "2026-05-01T00:59:59Z",
  "source": "binance"
}
```

Contraintes :

- `open_time` unique par `symbol` + `interval`
- timestamps en UTC
- prix et volume strictement positifs sauf cas documenté
- `high >= max(open, close)`
- `low <= min(open, close)`

## Sidecar de métadonnées dataset

Chaque fichier écrit dans `data/raw` et `data/processed` doit être accompagné d'un fichier `*.meta.json`.

Exemples :

- `data/raw/BTCUSDT/1h.csv.meta.json`
- `data/raw/BTCETH/1h.parquet.meta.json`
- `data/processed/BTCUSDT/1h_features.jsonl.meta.json`

Schéma minimal :

```json
{
  "layer": "raw",
  "dataset": "ohlcv",
  "source": "binance",
  "symbol": "BTCUSDT",
  "interval": "1h",
  "registered_at": "2026-06-01T19:00:00+00:00",
  "path": "data/raw/BTCUSDT/1h.csv",
  "file_name": "1h.csv",
  "file_size_bytes": 12345,
  "format": "csv",
  "content_type": "text/csv",
  "row_count": 1000,
  "column_count": 15,
  "columns": ["symbol", "interval", "open_time", "open", "high", "low", "close"],
  "dtypes": {
    "symbol": "object",
    "open": "float64"
  },
  "time_range": {
    "column": "open_time",
    "start": "2026-04-21 00:00:00+00:00",
    "end": "2026-06-01 15:00:00+00:00"
  }
}
```

Objectif :

- faciliter le debug sans ouvrir les gros fichiers
- tracer la provenance et la couche de transformation
- comparer rapidement deux exports d'un même dataset
- relier les datasets aux rapports qualité et label distribution

## Dataset traité

Formats attendus :

- primaire : `parquet`
- exports : `csv`, `jsonl`
- échantillons et rapports : `json`

Schéma minimal :

```json
{
  "symbol": "BTCUSDT",
  "interval": "1h",
  "timestamp": "2026-05-01T00:00:00Z",
  "close": 60200.0,
  "return_1": 0.0018,
  "volatility_20": 0.018,
  "sma_20": 59850.0,
  "sma_50": 59020.0,
  "rsi_14": 57.2,
  "macd": 113.4,
  "bb_width": 0.041,
  "target": "BUY"
}
```

## Mapping des labels

| Label | ID | Signal stratégie |
|---|---:|---:|
| `SELL` | 0 | -1 |
| `HOLD` | 1 | 0 |
| `BUY` | 2 | 1 |

Le mapping doit être stocké dans `label_mapping.json`.

## Contrat d'inférence interne

```json
{
  "symbol": "BTCUSDT",
  "interval": "1h",
  "model_name": "random_forest",
  "model_version": "2026-06-01T19-00-00Z",
  "signal": "BUY",
  "signal_value": 1,
  "confidence": 0.64,
  "probabilities": {
    "SELL": 0.12,
    "HOLD": 0.24,
    "BUY": 0.64
  },
  "data_timestamp": "2026-05-31T23:00:00Z",
  "generated_at": "2026-06-01T00:01:02Z",
  "latency_ms": 42.5,
  "warnings": []
}
```

Règles :

- `confidence` = probabilité de la classe prédite pour le MVP
- si la donnée est insuffisante, retourner `HOLD` avec warning
- si le modèle est absent, erreur API explicite
- ne pas appeler Binance dans le chemin critique de `/signals/latest`

## Endpoints API MVP

### `GET /health`

Réponse :

```json
{
  "status": "ok",
  "models_loaded": ["random_forest", "lstm"],
  "latest_data_timestamp": "2026-05-31T23:00:00Z",
  "data_freshness_seconds": 3660
}
```

### `GET /models`

Liste les artefacts disponibles.

```json
{
  "models": [
    {
      "name": "random_forest",
      "version": "2026-06-01T19-00-00Z",
      "symbols": ["BTCUSDT", "BTCETH"],
      "metrics": {
        "f1_macro": 0.41,
        "directional_accuracy": 0.56
      }
    }
  ]
}
```

### `GET /signals/latest`

Paramètres :

| Nom | Type | Défaut |
|---|---|---|
| `symbol` | string | `BTCUSDT` |
| `interval` | string | `1h` |
| `model` | string | `random_forest` |

Réponse : contrat d'inférence interne.

### `POST /predict`

Permet une prédiction ponctuelle à partir de features fournies ou d'un nombre de dernières bougies locales.

Pour le MVP, cet endpoint peut rester secondaire si `/signals/latest` couvre la démo.

## Codes d'erreur

| Code | Cas |
|---:|---|
| 400 | symbole ou intervalle non supporté |
| 404 | modèle demandé absent |
| 409 | artefact incomplet, scaler ou feature list absent |
| 422 | payload invalide |
| 503 | données indisponibles ou modèle non chargé |

## Compatibilité backend v2

Le signal peut être converti en format stratégie :

```json
{
  "strategy_name": "ml_mvp_signal",
  "symbol": "BTCUSDT",
  "signal": 1,
  "metadata": {
    "model": "random_forest",
    "confidence": 0.64
  }
}
```
