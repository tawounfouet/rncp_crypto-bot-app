# Architecture Data / ML — CryptoBot

Statut: référence
Derniere revision: 2026-06-12

> **Vision :** Les données brutes sont collectées une seule fois par les **jobs**,
> stockées dans **MinIO**, et chaque couche (ML, backend, frontend) les consomme
> depuis là où elles se trouvent — sans duplication ni appel direct aux APIs externes.

---

## 1. Flux data global

```
┌──────────────────────────────────────────────────────────────────┐
│                         EXTERNE                                  │
│  ┌──────────────────────────────────────────────────────────┐    │
│  │                   Binance API                             │    │
│  │              GET /api/v3/klines                           │    │
│  └────────────────────┬─────────────────────────────────────┘    │
│                       │ REST klines                              │
│                       ▼                                          │
│  ┌──────────────────────────────────────────────────────────┐    │
│  │  jobs/                                                     │    │
│  │  ┌────────────────────────────────────────────────────┐   │    │
│  │  │  collect_ohlcv.py                                   │   │    │
│  │  │  fetch klines → map_kline → DataFrame → Parquet     │   │    │
│  │  └────────────────────┬────────────────────────────────┘   │    │
│  └───────────────────────┼─────────────────────────────────────┘    │
│                          │ Parquet                                 │
│                          ▼                                         │
│  ┌──────────────────────────────────────────────────────────┐    │
│  │  MinIO (bucket: crypto-bot-data)                          │    │
│  │                                                           │    │
│  │  raw/ohlcv/{SYMBOL}/{interval}/{date}.parquet             │    │
│  │  models/{model_name}/best/{model,scaler}.joblib           │    │
│  └──────────────┬────────────────────────────────────────────┘    │
│                 │                                                  │
│                 ├────────────────────────────┐                     │
│                 │ read_raw_ohlcv_from_minio  │ deploy_model.py    │
│                 ▼                            ▼                    │
│  ┌────────────────────────────┐  ┌──────────────────────────────┐ │
│  │  models/ — ML layer        │  │  backend/ — FastAPI          │ │
│  │                            │  │                              │ │
│  │  features/build.py         │  │  inference/service.py        │ │
│  │  calcule RSI, MACD, ...    │  │  télécharge modèle au       │ │
│  │       ↓                    │  │  1er appel                  │ │
│  │  data/processed/*.parquet  │  │       ↓                     │ │
│  │       ↓                    │  │  predict() → scaler         │ │
│  │  train_random_forest.py    │  │    → model.predict_proba()  │ │
│  │       ↓                    │  │       ↓                     │ │
│  │  artifacts/registry/       │  │  POST /api/v1/inference/    │ │
│  │  random_forest/best/       │  │      predict                │ │
│  └────────────────────────────┘  └──────────────────────────────┘ │
└──────────────────────────────────────────────────────────────────┘
```

---

## 2. Les nouveaux dossiers

### `utils/` — Package transverse partagé

```
utils/
├── __init__.py                  # Export public
├── logging/
│   ├── __init__.py
│   ├── logger.py                # configure_logging(), get_logger(), LoggerMixin
│   └── formatters.py            # ColoredFormatter (console), JsonFormatter (fichier)
└── connectors/
    ├── __init__.py
    ├── minio.py                  # MinioClient — factorisé depuis 3 implémentations
    └── binance.py                # map_kline(), fetch_klines() — purs, sans SDK
```

**Ce que ça résout :**

| Problème avant | Solution |
|---|---|
| 5 `logging.basicConfig` dispersés + logger maison dans `models/` | Un `configure_logging()` unique, auto-détection TTY, rotation |
| 3 clients MinIO (backend + 2 jobs) avec noms d'env vars différents | Un `MinioClient` acceptant `MINIO_ACCESS_KEY` ET `MINIO_USER_ADMIN` |
| `map_kline` dupliqué entre `jobs/` et `models/` | `utils.connectors.binance.map_kline` — seule source de vérité |
| `fetch_klines` réimplémenté dans les jobs | Fonction portable sans dépendance `python-binance` |

### Import depuis n'importe où :

```python
from utils.connectors.minio import MinioClient
from utils.logging import configure_logging, get_logger

configure_logging(name="mon_service", level="DEBUG")
logger = get_logger(__name__)

client = MinioClient()
client.upload_dataframe(df, "mon/fichier.parquet")
```

---

## 3. Flux détaillé : Binance → MinIO → ML

### Étape 1 : Collecte (jobs)

```bash
python jobs/ingest/collect_ohlcv.py --symbol BTCUSDC --interval 1h
```

1. Appelle `GET /api/v3/klines` sur Binance (pas de clé API nécessaire)
2. Mappe les klines via `utils.connectors.binance.map_kline()`
3. Sérialise en Parquet → MinIO : `raw/ohlcv/BTCUSDC/1h/2026-06-12.parquet`

### Étape 2 : Feature engineering (models)

```bash
python -m src.main features --symbols BTCUSDC BTCETH --interval 1h
```

```
models/src/features/build.py
└── build_symbol_features()
    ├── read_raw_ohlcv_from_minio("BTCUSDC", "1h")     ← MinIO
    │   └── liste tous les fichiers raw/ohlcv/BTCUSDC/1h/*.parquet
    │   └── télécharge + concatène → DataFrame
    ├── apply_symbol_mapping() si invert_price = true    ← pour BTCETH
    ├── build_features()                                  ← calcule RSI, MACD, etc.
    └── write_dataset() → data/processed/BTCUSDC/1h_features.parquet
```

### Étape 3 : Entraînement (models)

```bash
python -m src.main train-rf --dataset data/processed/BTCUSDC/1h_features.parquet
```

```
models/src/training/train_random_forest.py
├── read_dataset(path) → DataFrame
├── train_random_forest()
│   ├── scaler = StandardScaler().fit_transform(features)
│   ├── model = RandomForestClassifier().fit(X_train, y_train)
│   └── retourne {model, scaler, feature_columns, metrics, ...}
├── save_random_forest_artifacts() → artifacts/random_forest/<run_id>/
├── write_model_card()
├── MLflow tracking
└── register_best_model() → artifacts/registry/random_forest/best/
```

---

## 4. Flux de déploiement : Modèle → Backend

```
  ┌──────────────────────────────────┐
  │  artifacts/registry/             │
  │  random_forest/best/             │
  │  ├── model.joblib                │
  │  ├── scaler.joblib               │
  │  └── feature_columns.json        │
  └────────────┬─────────────────────┘
               │ python jobs/deploy_model.py
               ▼
  ┌──────────────────────────────────┐
  │  MinIO                           │
  │  models/random_forest/best/      │
  │  ├── model.joblib                │
  │  ├── scaler.joblib               │
  │  └── feature_columns.json        │
  └────────────┬─────────────────────┘
               │ téléchargement au 1er appel
               ▼
  ┌──────────────────────────────────┐
  │  Cache local                     │
  │  /tmp/cryptobot_models/          │
  │  random_forest/best/             │
  │  ├── model.joblib                │
  │  ├── scaler.joblib               │
  │  └── feature_columns.json        │
  └────────────┬─────────────────────┘
               │ joblib.load()
               ▼
  ┌──────────────────────────────────┐
  │  POST /api/v1/inference/predict  │
  │  scaler.transform()              │
  │  → model.predict_proba()         │
  │  → signal + confidence           │
  └──────────────────────────────────┘
```

### Job de déploiement

```bash
# Depuis la racine du projet (après entraînement)
python jobs/deploy_model.py

# Déployer un modèle spécifique
python jobs/deploy_model.py --model random_forest
```

Ce qu'il copie vers MinIO :

| Fichier | Rôle |
|---|---|
| `model.joblib` | RandomForestClassifier entraîné |
| `scaler.joblib` | StandardScaler fit sur les features |
| `feature_columns.json` | Ordre exact des colonnes attendues |

### Service d'inférence (backend)

```python
from inference.service import InferenceService

svc = InferenceService(model_name="random_forest")
result = svc.predict({
    "rsi_14": 45.2,
    "sma_20": 67100.0,
    "macd": 120.5,
    # ... toutes les feature_columns
})
# → {"signal": "BUY", "confidence": 0.87, ...}
```

**Fonctionnement :**
1. Au premier appel, télécharge les artefacts depuis MinIO vers `/tmp/cryptobot_models/random_forest/best/`
2. Charge `model.joblib` + `scaler.joblib` avec `joblib.load()`
3. `predict(features)` → `scaler.transform()` → `model.predict_proba()` → retourne signal

---

## 5. Endpoints API

### `POST /api/v1/inference/predict`

**Request :**
```json
{
    "symbol": "BTCUSDC",
    "interval": "1h",
    "features": {
        "rsi_14": 42.15,
        "sma_20": 67320.0,
        "sma_50": 65100.0,
        "ema_12": 67200.0,
        "ema_26": 65800.0,
        "macd": 140.0,
        "macd_signal": 135.0,
        "macd_hist": 5.0,
        "bb_upper": 69000.0,
        "bb_middle": 67320.0,
        "bb_lower": 65640.0,
        "bb_width": 0.05,
        "volatility_20": 0.02,
        "volume_sma_20": 12500.0,
        "return_1": 0.001,
        "return_3": 0.003,
        "return_6": -0.002,
        "buy_pressure_ratio": 0.52,
        "volume_delta": 150.0,
        "trade_size_avg": 0.5
    }
}
```

**Response :**
```json
{
    "success": true,
    "symbol": "BTCUSDC",
    "interval": "1h",
    "model_name": "random_forest",
    "model_version": "minio",
    "signal": "SELL",
    "signal_value": -1,
    "confidence": 0.72,
    "probabilities": {
        "0": 0.72,
        "1": 0.18,
        "2": 0.10
    },
    "latency_ms": 12.34,
    "generated_at": "2026-06-12T08:30:00+00:00",
    "warnings": []
}
```

### `GET /api/v1/inference/model`

Retourne la liste des colonnes attendues (utile pour construire le payload).

```json
{
    "success": true,
    "model_name": "random_forest",
    "model_version": "minio",
    "feature_columns": ["rsi_14", "sma_20", "sma_50", ...],
    "artifact_path": "/tmp/cryptobot_models/random_forest/best",
    "loaded": true
}
```

---

## 6. Commandes utiles (Makefile / CLI)

### Workflow complet — du data au déploiement

```bash
# 1. Ingester les données depuis Binance
python jobs/ingest/collect_ohlcv.py --symbol BTCUSDC --interval 1h

# 2. Construire les features (lit depuis MinIO)
cd models && python -m src.main features --symbols BTCUSDC --interval 1h

# 3. Entraîner le modèle
cd models && python -m src.main train-rf \
    --dataset data/processed/BTCUSDC/1h_features.parquet

# 4. Déployer le meilleur modèle vers MinIO
python jobs/deploy_model.py

# 5. Lancer l'API backend
cd backend && uvicorn src.main:app --reload

# 6. Tester l'inférence
curl -X POST http://localhost:8000/api/v1/inference/predict \
  -H "Content-Type: application/json" \
  -d '{
    "symbol": "BTCUSDC",
    "features": {
      "rsi_14": 42.0, "sma_20": 67000.0, "sma_50": 65000.0,
      "ema_12": 67100.0, "ema_26": 65500.0, "macd": 160.0,
      "macd_signal": 150.0, "macd_hist": 10.0, "bb_upper": 69000.0,
      "bb_middle": 67000.0, "bb_lower": 65000.0, "bb_width": 0.06,
      "volatility_20": 0.02, "volume_sma_20": 13000.0,
      "return_1": 0.001, "return_3": -0.001, "return_6": 0.005,
      "buy_pressure_ratio": 0.55, "volume_delta": 200.0,
      "trade_size_avg": 0.45
    }
  }'
```

---

## 7. Règles à retenir

| Règle | Pourquoi |
|-------|----------|
| **Les jobs collectent, les couches lisent** | Un seul point d'entrée pour les données brutes → pas de duplication |
| **Les données brutes ne sont jamais modifiées dans MinIO** | Immuabilité → reproductibilité |
| **Les features sont calculées à la demande** | `read_raw_ohlcv_from_minio()` concatène tous les fichiers disponibles |
| **Le modèle est déployé via MinIO, pas copié à la main** | Traçabilité : on sait quelle version est en production |
| **Le backend ne dépend pas du dossier `models/`** | Isolation : chaque couche peut vivre dans son conteneur |
| **`utils/` ne dépend d'aucune couche applicative** | Pas de dépendance circulaire, utilisable partout |
