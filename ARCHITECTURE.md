# Architecture — Crypto-Bot App

> Document de référence technique : comment le système est construit et comment les données circulent. Les jugements de valeur sont dans [`ANALYSE_CRITIQUE.md`](./ANALYSE_CRITIQUE.md) ; les faits d'exécution dans [`CODEBASE_ANALYSIS.md`](./CODEBASE_ANALYSIS.md).

**Architecture détaillée par couche :** [`backend/ARCHITECTURE.md`](./backend/ARCHITECTURE.md) · [`frontend/ARCHITECTURE.md`](./frontend/ARCHITECTURE.md) · [`models/ARCHITECTURE.md`](./models/ARCHITECTURE.md) · [`jobs/ARCHITECTURE.md`](./jobs/ARCHITECTURE.md) · [`orchestration/ARCHITECTURE.md`](./orchestration/ARCHITECTURE.md) · [`utils/ARCHITECTURE.md`](./utils/ARCHITECTURE.md) · [`ci/ARCHITECTURE.md`](./ci/ARCHITECTURE.md).

---

## 1. Vue système

```
                    ┌───────────────────────────────────────────┐
                    │        Frontend Streamlit  :8501          │
                    │  app.py → pages/ (12) → services/*        │
                    │  api_client.py (public) · auth_api_client │
                    └──────────────────┬────────────────────────┘
                                       │ REST /api/v1 · JWT Bearer HS256
                                       ▼
   ┌──────────────────────────────────────────────────────────────────────┐
   │                     Backend FastAPI  :8009                            │
   │  main.py : TrustedHost → CORS → routers                               │
   │  auth · users · bots(+internal) · strategy · trading · market · infer │
   └──┬──────────┬───────────┬──────────────┬──────────────┬───────────────┘
      │          │           │              │              │
      │ HTTP     │ SQLAlchemy│ HTTP live    │ HTTP         │ process-local
      ▼          ▼           ▼              ▼              ▼
 ┌─────────┐ ┌──────────┐ ┌───────────┐ ┌──────────┐ ┌───────────────┐
 │ ml-api  │ │PostgreSQL│ │ Exchanges │ │ MLflow   │ │ inference/    │
 │ :8010   │ │ :5432    │ │ public API│ │ :5001    │ │ service.py    │
 │/internal│ │ 21 tables│ │ binance…  │ │ registre │ │ (artefacts)   │
 └────┬────┘ └────▲─────┘ └───────────┘ └────┬─────┘ └───────────────┘
      │           │                          │
      │           │ transform (jobs)         │ deploy artifacts
      │      ┌────┴──────┐                   │
      │      │ MinIO     │◄── ingest ────────┴── Binance REST
      │      │ :9000     │
      │      │ bucket    │
      │      │crypto-bot-data
      │      └───────────┘
      ▼
 ┌──────────────────────────────────────────────────────────────┐
 │ Airflow 2.8  :8080 — DAGs orchestration/dags/                 │
 │   ingest_ohlcv · backfill_ohlcv · ml_pipeline · purge_inactive│
 │   (+ example_cryptobot)                                       │
 └──────────────────────────────────────────────────────────────┘
```

**Topologie de déploiement réelle :**

| Composant | Hébergement | Particularité |
|---|---|---|
| backend, frontend, ml-api, MinIO, PostgreSQL, Airflow, MLflow | Cluster K8s Talos (3 nœuds) via ArgoCD, repo `dst_crypto/Crypto-bot-infra` | Environnement principal ; `dev`/`staging`/`production` en namespaces |
| Mêmes services | VM AWS « Liora » (fallback) | Déployés en parallèle par la CI (`/opt/crypto-bot-{staging,prod}`) |
| Dev local | `docker-compose.yml` | Tous les ports publiés sur l'hôte |

Images taguées via `versions.env` ; la CI GitLab construit et pousse par environnement (`:dev`, `:staging`, `:vX.X`).

---

## 2. Backend (package principal)

### 2.1 Organisation

Architecture **en couches par domaine**. Chaque dossier de `backend/src/` (`auth`, `market`, `trading`, `strategy`, `bots`, `inference`) suit le même triptyque, et un `shared/` transverse :

```
backend/src/
├── main.py              # entrée uvicorn : middlewares, handlers, montage des routeurs
├── auth/     router.py · users_router.py · service.py · user_service.py · models.py · schemas.py · dependencies.py
├── market/   router.py · service.py · insert_service.py · clients/ (drivers exchange) · models.py · schemas.py
├── trading/  router.py · service.py · models.py · schemas.py
├── strategy/ router.py · service.py · models.py · schemas.py
├── bots/     router.py · service.py · worker.py · models.py · schemas.py
├── inference/ router.py · service.py · live_features.py
└── shared/   config/ · database/ · models/ · schemas/ · core/exceptions.py
```

Conventions non standard à connaître :
- Le routeur **interne** des bots est défini dans `bots/router.py` (`internal_router`) et **monté sans `API_PREFIX`** (`main.py:294`) — contrairement à tous les autres routeurs qui passent par `settings.API_PREFIX` (`= /api/{API_VERSION}`, `settings.py:29`).
- Les modèles SQLAlchemy héritent d'une `BaseModel` et sont enregistrés par un décorateur `@register_model` (ex. `bots/models.py:38`) ; `create_tables()` importe tous les modèles au démarrage.
- Les identifiants sont des UUID stockés en `String`.

### 2.2 Cycle de vie d'une requête

```
Requête HTTP
  │
  ├─► TrustedHostMiddleware        (main.py:138)  — hôte dans ALLOWED_HOSTS sinon 400
  ├─► CORSMiddleware               (main.py:141)  — origines CORS_ORIGINS, credentials autorisés
  ├─► Routage Starlette            — routes évaluées dans l'ORDRE D'ENREGISTREMENT (main.py:291-306)
  │      └─► (routeur) Dépendances : HTTPBearer → auth/dependencies.get_current_user
  │                                        └─ auth/service.verify_token (JWT HS256, exp/type)
  │      └─► Handler du routeur
  │              └─► service.* (métier) ──► models (SQLAlchemy) / clients (exchange) / inference
  │
  └─► Réponse | handlers globaux d'exception :
         RequestValidationError → 422 structuré      (main.py:151)
         SQLAlchemyError        → 500                (main.py:165)
         Exception              → 500                (main.py:178)
```

L'authentification est une **dépendance injectée route par route** (`Depends(get_current_user)`), pas un middleware : seules les routes qui la déclarent sont protégées. `get_current_user` (`auth/dependencies.py`) extrait le Bearer, appelle `auth_service.get_current_user(token)` et lève 401 sinon ; `get_current_admin_user` ajoute le contrôle `is_admin`.

### 2.3 Flux métier clés

**Flux A — Authentification / session**

```
Frontend                Backend /auth                     PostgreSQL
   │ POST /auth/login ─────►│                                 │
   │                        │ verify password (argon2id) ────►│ users
   │                        │ create JWT (exp/iat/jti/type)   │
   │◄──── access + refresh ─┤ store UserSession ─────────────►│ user_sessions
   │ GET /users/me ────────►│ get_current_user (Bearer) ─────►│
   │◄──── profil ───────────┤                                 │
```

**Flux B — Décision de bot (le cœur produit)**

```
Airflow / worker API
   │ bots/service.execute_active_once(worker_id, limit)
   │      │ 1. liste les UserBotInstance actives (templates verrouillés)
   │      │ 2. compute signal : modèle MLflow (registre) OU règles → HOLD/BUY/SELL
   │      │ 3. applique risk_limits (risk_per_trade_pct, max_daily_loss_pct)
   │      │ 4. si signal ≠ HOLD → crée BotOrder / TradingDecision
   │      ▼
   │   bot_runs · trading_decisions · bot_orders · bot_trades · bot_positions
   ▼
Backend  GET /user-bots/{id}/decisions|orders|trades|position|performance
Frontend 05_Controle_Bot_Spot.py · 04_Performances_Spot.py
```

⚠️ Le worker est lancé sur la boucle de l'API (`main.py:74-80`, `asyncio.create_task`) alors que `run_once` est synchrone (`worker.py:21`) — voir B12 dans [`CODEBASE_ANALYSIS.md`](./CODEBASE_ANALYSIS.md#5-bugs-confirmés-reproductibles-par-lecture-du-code).

**Flux C — Ingestion de données de marché**

```
Airflow ingest_ohlcv
   │ jobs/ingest/collect_ohlcv.run_ingestion
   │     Binance REST (klines) → DataFrame
   │     upload Parquet → MinIO  raw/ohlcv/{exchange}/{SYMBOL}/{interval}/{YYYY-MM-DD}.parquet
   ▼
Airflow (transform)
   │ jobs/transform/load_ohlcv  MinIO → PostgreSQL (table market_data)
   ▼
Backend  GET /market/data/latest/{symbol} (lit Postgres)
         GET /market/public/prices      (appel direct driver exchange, non authentifié)
```

⚠️ Les endpoints `/market/price/{symbol}`, `/prices`, `/indicators`, `/summary`, `POST /market/data` n'utilisent **pas** ces données : `MarketDataService.get_historical_data` renvoie des données simulées (B6).

**Flux D — Entraînement ML**

```
Airflow ml_pipeline
   │ POST :8010/internal/pipeline/features|train-random_forest|train-mlp|train-xgboost
   ▼
ml-api → entraîne → dépose artefacts (registry) → MLflow :5001 (backend store Postgres)
   │
   │ POST :8009/internal/bot-templates/sync  (resynchronise le catalogue de bots)
   ▼
Backend  GET /bot-templates  (nouveaux modèles visibles)
```

---

## 3. Modèle de données

21 tables SQLAlchemy, organisées par domaine, reliées à `users` par `cascade="all, delete-orphan"` :

```
                              ┌──────────┐
                              │  users   │──── UserSettings (uselist=False)
                              └────┬─────┘──── UserAccount, UserExchangeCredential
                                   │
     ┌───────────────┬─────────────┼──────────────┬──────────────────┐
     ▼               ▼             ▼              ▼                  ▼
 user_sessions   orders        strategies    bot_templates      (market_data
                 ├─ order_fills ├─ strategy_deployments           indépendant)
                 └─ transactions├─ strategy_states
                                ├─ trading_sessions
                                └─ backtest_results

 user_bot_instances ──► bot_runs ──► trading_decisions
        │                             └─► bot_orders ──► bot_trades
        └─► bot_positions
```

Points clés :
- **Identifiants** : UUID en `String` (pas d'entier auto-incrémenté).
- **Champs sensibles** : `users.hashed_password` (argon2id) ; `user_exchange_credentials` stocke `api_key`/`api_secret` **chiffrés** (`EXCHANGE_ENC_KEY`, cf. `shared/config/security.py`) ; jamais renvoyés en clair (schémas dédiés).
- **Snapshots JSON** : `bot_templates.execution_params/risk_limits/order_policy` et `bot_templates.signal_source` sont dénormalisés en JSON — les instances référencent un template, mais les paramètres peuvent être migrés via `sync_builtin_templates(migrate_instances=...)`.
- **`market_data`** : table large (OHLCV + volumes taker), `UPSERT` sur la clé `(symbol, exchange, interval_timeframe, open_time)`.
- **`strategy_*`** : module historique conservé (gelé) après remplacement par `bots/` ; `BacktestResult` persisté par utilisateur.

---

## 4. Frontend (Streamlit)

```
frontend/src/
├── app.py            # entrée : login/dashboard public
├── pages/            # 12 pages (Streamlit les découvre par nom de fichier)
│    00_Tableau_de_bord  01_Marche  02_Inscription  03_Portefeuille_Spot
│    04_Performances_Spot  05_Controle_Bot_Spot  06_Parametrage_Bot_Spot
│    07_Gestion_de_compte  08_Admin  09_Backtesting
│    09_Binance_Testnet_Lab  10_Politique_de_confidentialite
├── layouts/page_shell.py   # setup_page() : point d'entrée commun de chaque page
├── navigation/rules.py     # PAGES (clé → métadonnées) + can_access()
├── services/               # clients HTTP + services métier (api_client, auth_api_client, …)
├── state/session.py        # gestion du session_state Streamlit + tokens
├── components/ · theme/ · schemas/ · mocks/ · pydantic/ (shim)
```

- **Point central de navigation** : chaque page appelle `setup_page(title, icon, page_key)` (`layouts/page_shell.py:14`) qui charge `get_store()`, authentifie, puis appelle `can_access(page_key, user)` → `get_page` consulté dans `PAGES` (`navigation/rules.py`). Une clé absente (`binance_testnet_lab`) provoque une `KeyError` (B11).
- **State management** : pas de Redux-like ; tout passe par `st.session_state` via `state/session.py`. Clés principales :

| Clé `session_state` | Rôle |
|---|---|
| `STORE_KEY` | `MockStore` (données locales de démo) |
| `ACCESS_TOKEN_KEY` / `REFRESH_TOKEN_KEY` | jetons JWT |
| `USER_DATA_KEY` / `AUTHENTICATED_KEY` | profil courant / drapeau de session |
| `EXCHANGE_CONFIGURED_KEY` / `EXCHANGE_SYNCED_KEY` | état de la config exchange |
| `SELECTED_EXCHANGE_KEY` | exchange courant |
| `USER_SYNCED_TOKEN_KEY` / `USER_SYNCED_AT_KEY` | cadence du refresh (≈ 60 s) |

- **Deux clients HTTP** : `services/api_client.py` (routes publiques et authentifiées via `access_token` explicite) et `services/auth_api_client.py` (routes compte/testnet, avec `API_URL` par défaut `http://localhost:8009`, `auth_api_client.py:32`).
- **Systèmes de style** : `theme/styles.py` (CSS global + `@import` Google Fonts, `theme/styles.py:15`) et `apply_global_styles(...)` appelé par `setup_page`.
- **Piège** : `frontend/src/pydantic/` est un shim qui **masque** le paquet réel dès que `src/` est dans le `PYTHONPATH`.

---

## 5. Conventions transverses à connaître

| Sujet | Convention |
|---|---|
| Montage des routeurs | Préfixe global `/api/v1` sauf le routeur interne bots (`main.py:294`) |
| Auth | Dépendance par route (`Depends(get_current_user)`), pas de garde de routeur |
| Identifiants | UUID `String` ; `user_id` doit venir du jeton, jamais du client (à corriger là où ce n'est pas le cas) |
| Dates | Mélange naïf/aware : beaucoup de `datetime.now(UTC)` (aware) mais des champs de schéma sans fuseau (`market/schemas.py:60`) — piège de comparaison (B7) |
| Erreurs | Handlers globaux 422/500 dans `main.py` ; certaines routes reconvertissent `Exception` en 500 générique |
| Prix/données | Driver exchange `GET /market/public/*` (réel) vs `MarketDataService` (simulé, B6) |
| Chiffrement | `EXCHANGE_ENC_KEY` pour identifiants exchange ; `JWT_SIGNING_KEY` pour les jetons (distincts) |
| Tests | Un test par domaine ; frontend via `frontend/pyproject.toml` (`pythonpath=["src"]`) |
| `utils/` | Package partagé racine (backend/jobs/models) — distinct de `frontend/src/utils/`, ne jamais les mélanger sur le `PYTHONPATH` |
| requirements | Fichiers **générés** depuis `versions.env` + `*.requirements.txt.template` — ne pas éditer à la main |

---

## 6. Limites structurelles (résumé)

Ces choix sont détaillés et argumentés dans [`ANALYSE_CRITIQUE.md`](./ANALYSE_CRITIQUE.md) :

1. **Auth non centralisée** : la protection est recopiée par route, ce qui laisse des endpoints ouverts (V1–V5).
2. **Frontière interne/public déclarative** : routeurs et ports « internes » sont en réalité exposés (V4, V5, V6).
3. **Données simulées sur chemins de production** : `MarketDataService` renvoie du hasard sur des routes documentées comme réelles (B6).
4. **Migration `strategy → bots` inachevée** : endpoints `trading` morts mais montés et documentés (B2/B3) ; routeur Testnet défini mais non monté (B14).
5. **Worker synchrone sur la boucle de l'API** : les passes de bots bloquent le serveur HTTP (B12).
6. **CI partielle** : aucun test unitaire ni `models/`/`orchestration/` vérifiés automatiquement.
