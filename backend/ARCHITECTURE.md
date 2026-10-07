# Architecture — backend/

> Document de référence de la couche **API FastAPI**. Vue système globale dans [`../ARCHITECTURE.md`](../ARCHITECTURE.md) ; constats et bugs dans [`../CODEBASE_ANALYSIS.md`](../CODEBASE_ANALYSIS.md).

---

## 1. Vue d'ensemble

Le backend est l'API REST centrale (`/api/v1`) qui expose l'authentification, le catalogue de bots, le trading, les stratégies, les données de marché et l'inférence. Il est découpé **par domaine métier**, chaque domaine suivant le même triptyque `router → service → models/schemas`.

```
backend/
├── src/
│   ├── main.py                 # entrée uvicorn : app, middlewares, handlers, montage routeurs
│   ├── auth/                   # users, sessions, credentials exchange, settings
│   ├── bots/                   # templates verrouillés, instances, décision/ordre/trade/position
│   ├── market/                 # données de marché, insertion, clients exchange, testnet (non monté)
│   ├── trading/                # ordres, fills, transactions, stats
│   ├── strategy/               # stratégies + moteur de règles (module gelé)
│   ├── inference/              # inférence ML en process (modèle + features live)
│   └── shared/                 # config, database, exceptions, schemas, clients transverses
├── requirements.txt(.template) # générés depuis ../versions.env
├── Dockerfile                  # contexte de build = racine du repo
├── README.md                   # table des endpoints
├── tests/{unit,integration}    # 214 tests
└── ci/parse_test_report.py     # parseur JUnit/Cobertura inclus dans l'image de test
```

Métriques : **24 134 lignes / 119 fichiers** Python.

---

## 2. Point d'entrée et cycle de vie

`src/main.py` crée l'application `FastAPI` (`main.py:116`) avec `lifespan` (`main.py:33`).

**Démarrage (`lifespan`, `main.py:43-94`) :**
1. `init_database()` (`main.py:48`) — création des tables + correctifs de compatibilité de schéma (`shared/database/connection.py`).
2. `BotService().sync_builtin_templates(...)` (`main.py:67`) — synchronise le catalogue de templates (migration des instances si `BOT_TEMPLATE_AUTO_MIGRATE`).
3. Si `ENABLE_BACKGROUND_TASKS` : lance `BotWorker(...).run_forever(...)` via `asyncio.create_task` (`main.py:74-81`) — **sur la boucle de l'API** (cf. B12).

**Arrêt (`main.py:98-109`) :** signale l'événement d'arrêt du worker, attend 5 s puis annule.

**Configuration d'exécution :** `HOST=0.0.0.0`, `PORT=8000` par défaut (`settings.py:42-43`), mais le conteneur expose et sert le port **8009** (`backend/Dockerfile` : `EXPOSE 8009`, `CMD uvicorn src.main:app --host 0.0.0.0 --port 8009`).

---

## 3. Middlewares et gestion d'erreurs

Chaîne appliquée dans `main.py` :

| Ordre | Élément | Référence |
|---|---|---|
| 1 | `TrustedHostMiddleware` (`ALLOWED_HOSTS`) | `main.py:138` |
| 2 | `CORSMiddleware` (`CORS_ORIGINS`, credentials, méthodes GET/POST/PUT/DELETE/OPTIONS) | `main.py:141-147` |
| 3 | Handler `RequestValidationError` → 422 structuré | `main.py:151-162` |
| 4 | Handler `SQLAlchemyError` → 500 | `main.py:165-175` |
| 5 | Handler `Exception` → 500 | `main.py:178-188` |

Health : `/health` (`main.py:192`) et `/health/detailed` (`main.py:203`, contient un horodatage figé — B10).

---

## 4. Montage des routeurs

`main.py:280-306` : import des routeurs puis inclusion sous `settings.API_PREFIX` (`= /api/{API_VERSION}`, `settings.py:29`).

| Routeur | Variable montée | Préfixe |
|---|---|---|
| `auth.router` | `auth_router` | `/api/v1` |
| `auth.users_router` | `users_router` | `/api/v1` |
| `bots.router` | `bots_router` | `/api/v1` |
| `bots.router` (interne) | `bots_internal_router` | **aucun** (`main.py:294`) |
| `strategy.router` | `strategies_router` | `/api/v1` |
| `trading.router` | `trading_router` | `/api/v1` |
| `market.router` | `market_router` | `/api/v1` |
| `inference.router` | `inference_router` | `/api/v1` |

> ⚠️ Le routeur `market/binance_testnet_router.py` (13 routes) **n'est jamais importé ni monté** (B14). Vérifié via OpenAPI : **77 chemins / 91 opérations** montés.

---

## 5. Découpage par domaine

| Domaine | Rôle | Fichiers clés |
|---|---|---|
| `auth/` | Users, sessions, credentials exchange chiffrés, settings | `router.py`, `users_router.py`, `service.py`, `user_service.py`, `dependencies.py`, `models.py`, `schemas.py` |
| `bots/` | Catalogue de templates verrouillés + décision signal→risque→ordre | `service.py` (1 800+ l.), `ai.py`, `execution.py`, `ml_client.py`, `worker.py`, `router.py`, `models.py` |
| `market/` | Données OHLCV, insertion historique, clients exchange | `router.py`, `service.py`, `insert_service.py`, `clients/`, `binance_testnet_*` |
| `trading/` | Ordres, fills, transactions, statistiques | `router.py`, `service.py`, `models.py`, `schemas.py` |
| `strategy/` | Stratégies + moteur de règles (gelé, remplacé par `bots/`) | `router.py`, `service.py`, `engine/` |
| `inference/` | Inférence ML en process | `router.py`, `service.py`, `live_features.py` |

### 5.1 `bots/` — cœur métier

`BotService.execute_active_once()` (`bots/service.py:828`) orchestre le cycle d'un bot :
signal (modèle MLflow ou règles — `_compute_*_signal`, `_compute_template_signal`) → risque (`_evaluate_risk`, `_daily_loss_status`) → ordre/trade/position (`_record_order`, `_record_trades_and_position`, `_update_position`).
Dépendances injectables : `ai.py` (régime/tendance), `execution.py` (`MultiExchangeBotGateway`), `ml_client.py` (`BotMlClient`, HTTP vers ml-api), `worker.py` (`BotWorker.run_once`, synchrone — B12).

### 5.2 `auth/` — authentification

- `dependencies.py` : `HTTPBearer` → `get_current_user`, `get_current_active_user`, `get_current_admin_user`, `get_current_user_optional`. **L'auth est injectée route par route** (pas de garde de routeur → V1–V5).
- `service.py` : création/validation JWT HS256 (`exp/iat/jti/type`, `service.py:84-121`), argon2id avec repli PBKDF2 (`service.py:37`), logout/logout-all (`service.py:335`).
- `user_service.py` : CRUD utilisateur. **`update_user` perd silencieusement les modifications** (B1).

### 5.3 `market/clients/` — abstraction exchange

`base.py` définit l'ABC `ExchangeClient` (Balance, Ticker, OrderResult) ; implémentations `binance.py`, `binance_native.py`, `ccxt_client.py` ; `registry.py` + `factory.py:from_user_settings(...)` résolvent le client ; `minio.py` et `quotes.py` complètent. Les clients de **données de marché** (drivers) vivent dans `utils/connectors/exchanges` (voir [`../utils/ARCHITECTURE.md`](../utils/ARCHITECTURE.md)).

### 5.4 `strategy/engine/`

Moteur de règles historiques : `base_strategy.py`, `implementations/`, `indicators/`, `registry.py` (enregistre `rsi_reversal`, `moving_average_crossover`, `bollinger_bands`, `multi_indicator`).

---

## 6. `shared/` — socle transverse

| Sous-dossier | Contenu |
|---|---|
| `config/` | `settings.py` (`Settings(BaseSettings)`), `security.py` (chiffrement `EXCHANGE_ENC_KEY`), `constants.py` (`ErrorCode`, `API_VERSION`), `asgi.py`/`wsgi.py` |
| `database/` | `connection.py` (`DatabaseManager` : Postgres, repli SQLite, `sessionmaker(autoflush=False)`), `dependencies.py` (`get_db`), `migrations/`, `seeds/`, `sql/`, `init_database.sql` |
| `core/` | `exceptions.py` : hiérarchie `CryptoBotException` → `ValidationError`, `NotFoundError`, `BusinessLogicError`, `AuthenticationError`, `ExternalServiceError`, `StrategyExecutionError`, `DataError` |
| `schemas/` | Schémas Pydantic partagés (`BaseResponse`, `PaginatedResponse`) |
| `clients/` | `airflow_client.py` (déclenchement de DAGs) |
| `models/` | `Base` SQLAlchemy + `register_model` |

**Base de données** : `DatabaseManager.get_database_url()` (`connection.py:96`) tente PostgreSQL puis bascule sur SQLite (`USE_SQLITE_FALLBACK=true`) ; `get_session()` (`connection.py:229`) **commit à la sortie** du contexte.

Modèles persistés (21 tables, définis dans les `models.py` de domaine) : `users`, `user_sessions`, `user_accounts`, `user_exchange_credentials`, `user_settings`, `orders`, `order_fills`, `transactions`, `market_data`, `strategies`, `strategy_deployments`, `strategy_states`, `trading_sessions`, `backtest_results`, `bot_templates`, `user_bot_instances`, `bot_runs`, `trading_decisions`, `bot_orders`, `bot_trades`, `bot_positions`.

---

## 7. Tests & qualité

- `tests/unit` (15 fichiers) · `tests/integration` (5) · `tests/integration/test_api` (2) = **214 tests**.
- Lancement : `make test-backend` ou `PYTHONPATH=backend/src:. .venv/bin/python -m pytest backend/tests -q`.
- Docker de test : `backend/Dockerfile` cible `test` (`CMD pytest tests -v`), contexte racine requis pour `COPY utils/`.
- Couverture : `pytest-cov` + `ci/parse_test_report.py`.

---

## 8. Limites structurelles (renvoi)

1. Auth non centralisée (V1–V5).
2. Routeur interne bots monté sans préfixe ni auth (V4).
3. Routeur Testnet défini mais non monté (B14).
4. Données simulées servies par `MarketDataService` (B6).
5. Worker synchrone sur la boucle de l'API (B12).

Argumentation détaillée : [`../ANALYSE_CRITIQUE.md`](../ANALYSE_CRITIQUE.md) et [`../RECOMMANDATIONS.md`](../RECOMMANDATIONS.md).
