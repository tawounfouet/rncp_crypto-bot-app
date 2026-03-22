# Crypto-Bot Backend

Backend FastAPI pour le projet de trading automatise de cryptomonnaies.

## Architecture

Le code est organise en **domaines metier** (domain-driven), chaque domaine contenant ses propres models, schemas, services et routes.

```
backend/
├── src/
│   ├── main.py                  # Point d'entree FastAPI, lifespan, middleware
│   ├── auth/                    # Authentification & gestion utilisateurs
│   │   ├── router.py            #   /auth (register, login, refresh, logout)
│   │   ├── users_router.py      #   /users (profil, settings, admin CRUD)
│   │   ├── service.py           #   Logique JWT (creation/validation tokens)
│   │   ├── user_service.py      #   CRUD utilisateurs & settings
│   │   ├── models.py            #   User, UserSession, UserAccount, UserSettings
│   │   ├── schemas.py           #   UserCreate, TokenResponse, UserResponse...
│   │   └── dependencies.py      #   get_current_user, get_current_admin_user
│   ├── market/                  # Donnees de marche
│   │   ├── router.py            #   /market (prix, symboles, indicateurs, OHLCV)
│   │   ├── service.py           #   Generation de donnees simulees
│   │   ├── insert_service.py    #   Insertion donnees reelles Binance (UPSERT)
│   │   ├── models.py            #   MarketData (OHLCV)
│   │   ├── schemas.py           #   PriceInfo, TechnicalIndicators, MarketSummary
│   │   └── clients/             #   Clients externes
│   │       ├── binance.py       #     API Binance (klines, prix, symboles)
│   │       └── minio.py         #     Stockage MinIO (S3-compatible)
│   ├── trading/                 # Operations de trading
│   │   ├── router.py            #   /trading (ordres, transactions, portfolio)
│   │   ├── service.py           #   Logique ordres, portfolio, statistiques
│   │   ├── models.py            #   Order, OrderFill, Transaction
│   │   └── schemas.py           #   OrderCreate, PortfolioResponse, TradingStats
│   ├── strategy/                # Strategies de trading
│   │   ├── router.py            #   /strategies (CRUD, deploiement, validation)
│   │   ├── service.py           #   Gestion strategies & deploiements
│   │   ├── models.py            #   Strategy, StrategyDeployment, StrategyState...
│   │   ├── schemas.py           #   StrategyCreate, DeploymentResponse...
│   │   └── engine/              #   Moteur d'execution
│   │       ├── base_strategy.py #     Classe abstraite de base
│   │       ├── registry.py      #     Registre & factory des strategies
│   │       ├── indicators/      #     Indicateurs techniques (SMA, RSI, BB, MACD)
│   │       └── implementations/ #     Implementations concretes
│   ├── shared/                  # Infrastructure transversale
│   │   ├── config/
│   │   │   ├── settings.py      #   Settings Pydantic (env vars, auto-detection Docker)
│   │   │   ├── security.py      #   Configuration securite
│   │   │   └── constants.py     #   Enums (OrderType, StrategyType, TimeFrame...)
│   │   ├── database/
│   │   │   ├── connection.py    #   DatabaseManager (PostgreSQL → SQLite fallback)
│   │   │   ├── dependencies.py  #   get_db() pour injection FastAPI
│   │   │   ├── migrations/      #   Alembic
│   │   │   ├── seeds/           #   Donnees initiales
│   │   │   └── sql/             #   Scripts SQL (triggers, vues)
│   │   ├── models/
│   │   │   └── base.py          #   BaseModel (UUID + timestamps), mixins
│   │   ├── core/
│   │   │   └── exceptions.py    #   Hierarchie d'exceptions custom
│   │   └── schemas/
│   │       └── common.py        #   BaseResponse, PaginatedResponse
│   └── tests/
│       ├── unit/                #   Tests unitaires
│       ├── integration/         #   Tests API, DB, services externes
│       ├── fixtures/            #   Factories & fixtures
│       └── conftest.py
├── requirements.txt
├── requirements-dev.txt
├── Dockerfile
├── .gitlab-ci.yml
└── README.md
```

## Endpoints API

Prefix : `/api/v1`

### Auth (`/auth`)

| Methode | Route | Auth | Description |
|---------|-------|------|-------------|
| POST | `/auth/register` | Non | Inscription, retourne JWT |
| POST | `/auth/login` | Non | Login OAuth2 (form-data) |
| POST | `/auth/login/json` | Non | Login JSON |
| POST | `/auth/refresh` | Non | Renouveler l'access token |
| POST | `/auth/logout` | Non | Deconnexion (invalide le refresh token) |
| POST | `/auth/logout-all` | Non | Deconnexion de toutes les sessions |

### Users (`/users`)

| Methode | Route | Auth | Description |
|---------|-------|------|-------------|
| GET | `/users/me` | Oui | Profil utilisateur courant |
| PUT | `/users/me` | Oui | Modifier son profil |
| DELETE | `/users/me` | Oui | Supprimer son compte |
| GET | `/users/me/settings` | Oui | Preferences utilisateur |
| PUT | `/users/me/settings` | Oui | Modifier ses preferences |
| GET | `/users/` | Admin | Lister tous les utilisateurs |
| GET | `/users/{id}` | Admin | Detail d'un utilisateur |
| PUT | `/users/{id}` | Admin | Modifier un utilisateur |
| DELETE | `/users/{id}` | Admin | Supprimer un utilisateur |
| POST | `/users/{id}/activate` | Admin | Activer un compte |
| POST | `/users/{id}/deactivate` | Admin | Desactiver un compte |

### Market (`/market`)

| Methode | Route | Auth | Description |
|---------|-------|------|-------------|
| POST | `/market/data/insert` | Oui | Inserer des donnees Binance (UPSERT) |
| POST | `/market/data` | Oui | Recuperer des donnees OHLCV |
| GET | `/market/data/latest/{symbol}` | Oui | Dernieres donnees en base |
| GET | `/market/price/{symbol}` | Oui | Prix actuel + stats 24h |
| GET | `/market/prices` | Oui | Prix multiples (symboles separes par virgule) |
| GET | `/market/symbols` | Oui | Liste des paires disponibles |
| GET | `/market/symbols/{symbol}` | Oui | Detail d'une paire |
| GET | `/market/indicators/{symbol}` | Oui | Indicateurs techniques (SMA, RSI, BB, MACD) |
| GET | `/market/summary` | Oui | Resume marche (top gainers/losers) |

### Trading (`/trading`)

| Methode | Route | Auth | Description |
|---------|-------|------|-------------|
| POST | `/trading/orders` | Oui | Creer un ordre |
| GET | `/trading/orders` | Oui | Lister ses ordres (filtrable) |
| GET | `/trading/orders/{id}` | Oui | Detail d'un ordre |
| DELETE | `/trading/orders/{id}` | Oui | Annuler un ordre |
| GET | `/trading/orders/{id}/status` | Oui | Statut temps reel |
| POST | `/trading/orders/market/buy` | Oui | Achat rapide au marche |
| POST | `/trading/orders/market/sell` | Oui | Vente rapide au marche |
| POST | `/trading/transactions` | Oui | Creer une transaction |
| GET | `/trading/transactions` | Oui | Lister ses transactions |
| GET | `/trading/transactions/{id}` | Oui | Detail d'une transaction |
| GET | `/trading/portfolio` | Oui | Portfolio (balances, positions) |
| GET | `/trading/stats` | Oui | Statistiques de trading |
| GET | `/trading/positions` | Oui | Positions ouvertes |
| GET | `/trading/health` | Non | Health check du module |

### Strategies (`/strategies`)

| Methode | Route | Auth | Description |
|---------|-------|------|-------------|
| GET | `/strategies/available` | Non | Types de strategies disponibles |
| POST | `/strategies/` | Oui | Creer une strategie |
| GET | `/strategies/` | Oui | Lister ses strategies |
| GET | `/strategies/{id}` | Oui | Detail d'une strategie |
| PUT | `/strategies/{id}` | Oui | Modifier une strategie |
| DELETE | `/strategies/{id}` | Oui | Supprimer une strategie |
| POST | `/strategies/{id}/deploy` | Oui | Deployer une strategie |
| GET | `/strategies/deployments/` | Oui | Lister ses deploiements |
| POST | `/strategies/deployments/{id}/stop` | Oui | Arreter un deploiement |
| POST | `/strategies/validate` | Non | Valider des parametres |

### Infra

| Methode | Route | Description |
|---------|-------|-------------|
| GET | `/health` | Health check simple |
| GET | `/health/detailed` | Health check avec statut BDD |
| GET | `/api/v1` | Info API (version, endpoints) |

## Authentification

- **JWT** (HS256) : access token (30 min) + refresh token (7 jours)
- **Sessions** : refresh tokens stockes en base (table `user_sessions`)
- **Roles** : `is_admin` pour les endpoints d'administration

## Base de donnees

- **PostgreSQL** (primaire) avec fallback automatique vers **SQLite** en dev
- **UUID** comme cle primaire sur tous les modeles
- **Mixins** : timestamps (`created_at`, `updated_at`), soft delete, audit
- Connection pool : `pool_size=10`, `max_overflow=20`

## Installation locale

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements-dev.txt

cp src/.env.example .env
# Editer .env avec vos valeurs
```

## Lancement

```bash
# Mode developpement
uvicorn src.main:app --reload --port 8009

# Ou via Docker
docker build -t crypto-bot-backend .
docker run -p 8009:8009 crypto-bot-backend
```

## Tests

```bash
pytest src/tests -v
pytest src/tests -v --cov=src --cov-report=html
```

## Documentation interactive

- Swagger UI : http://localhost:8009/docs
- ReDoc : http://localhost:8009/redoc

## Variables d'environnement

| Variable | Description | Defaut |
|----------|-------------|--------|
| `SECRET_KEY` | Cle de signature JWT | - |
| `POSTGRES_HOST` | Host PostgreSQL | localhost |
| `POSTGRES_PORT` | Port PostgreSQL | 5432 |
| `POSTGRES_USER` | Utilisateur PostgreSQL | - |
| `POSTGRES_PWD` | Mot de passe PostgreSQL | - |
| `POSTGRES_DB` | Nom de la base | crypto_bot_db |
| `MONGODB_HOST` | Host MongoDB | localhost |
| `MONGODB_PORT` | Port MongoDB | 27017 |
| `MONGODB_USER` | Utilisateur MongoDB | - |
| `MONGODB_PWD` | Mot de passe MongoDB | - |
| `MINIO_ENDPOINT` | Endpoint MinIO | localhost:9000 |
| `MINIO_ACCESS_KEY` | Cle d'acces MinIO | - |
| `MINIO_SECRET_KEY` | Cle secrete MinIO | - |
| `BINANCE_API_KEY` | Cle API Binance (optionnel) | - |
| `BINANCE_API_SECRET` | Secret API Binance (optionnel) | - |

## CI/CD et workflow submodule

Ce repo dispose de son propre `.gitlab-ci.yml` qui execute les stages **lint** et **test** sur chaque MR et branche feature.

### Synchronisation automatique avec le repo parent

Lorsqu'une MR est mergee dans `staging`, un job `sync:parent` met a jour automatiquement le pointeur de submodule dans la branche `staging` du repo `crypto-bot`. Le repo parent detecte alors le changement et declenche sa propre CI pour construire les images Docker et deployer.

### Mecanisme anti-boucle

Les commits de synchronisation sont prefixes avec `ci(...)` dans leur message. Le job `sync:parent` est configure pour ne pas se declencher sur ces commits, ce qui evite une boucle infinie entre les deux pipelines.

### Variable CI requise

La variable `GROUP_PAT_TOKEN` (definie au niveau du groupe `dst_crypto`) est necessaire pour que le job `sync:parent` puisse pousser le commit de mise a jour du submodule dans le repo parent.
