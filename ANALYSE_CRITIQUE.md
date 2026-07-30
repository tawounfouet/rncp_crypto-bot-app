# Analyse critique de la codebase — CryptoBot App

> **Disclaimer :** Cette analyse critique est constructive et vise à identifier les axes de priorisation technique. Elle ne remet pas en cause la qualité globale du projet, qui démontre une architecture bien pensée et une CI/CD industrialisée.

---

## 1. Failles de sécurité critiques

### 1.1 Secrets par défaut en dur

**Fichier :** `backend/src/shared/config/settings.py:34`
```python
SECRET_KEY: SecretStr = "your-secret-key-change-this-in-production"
```

La clé secrète JWT a une valeur par défaut triviale. Si un déploiement oublie de surcharger `.env`, **n'importe qui peut signer des JWT valides**. Même constat pour `MINIO_SECRET_KEY` (ligne 77).

**Risque :** Élevé — compromet toute l'authentification.

---

### 1.2 CORS et Allowed Hosts en wildcard

**Fichier :** `backend/src/shared/config/settings.py:45-51`
```python
CORS_ORIGINS: list[str] = ["*"]
ALLOWED_HOSTS: list[str] = ["*"]
```

En production, `CORS_ORIGINS: ["*"]` autorise n'importe quel site à faire des requêtes跨域 vers l'API. Combiné avec `ALLOWED_HOSTS: ["*"]`, le `TrustedHostMiddleware` est neutralisé.

**Risque :** Élevé — attaques CSRF potentielles, pas de protection Host header.

---

### 1.3 Mots de passe en clair dans les mocks

**Fichier :** `frontend/src/mocks/db.py:33-58`
```python
MockUser(password="Passw0rd!"),
MockUser(password="Admin123!"),
```

Les mots de passe des utilisateurs de démonstration sont stockés **en clair** dans la base mockée. Bien que ce soit une base mock, cela normalise un mauvais pattern et pourrait fuiter via les logs ou une page debug.

**Risque :** Moyen — exposition via logs/erreurs.

---

### 1.4 Timestamp en dur dans le health check

**Fichier :** `backend/src/main.py:169`
```python
"timestamp": "2025-07-29T03:15:00Z",
```

Une date littérale figée en juillet 2025 dans un endpoint de health check. C'est un **cauchemar de débogage** : qui va penser à mettre à jour cette date ?

---

## 2. Problèmes d'architecture et de conception

### 2.1 Duplication de systèmes de configuration

Deux systèmes de settings Pydantic coexistent :
- `backend/src/shared/config/settings.py` (~350 lignes, backend complet)
- `models/src/config/settings.py` (~? lignes, ML)

Ils ne partagent rien. Si un paramètre commun change (ex: `BINANCE_API_URL`), il faut le modifier aux deux endroits. Le module `jobs/` gère sa config via **variables d'environnement brutes** (sans Pydantic).

---

### 2.2 Routers backend complets mais services vides

Le backend a **3 routers** volumineux avec une belle gestion d'erreurs :
- `trading/router.py` : 721 lignes, 13 endpoints
- `market/router.py` : 636 lignes, 10 endpoints
- `strategy/router.py` : 370 lignes, 10 endpoints

Mais les services sous-jacents (`TradingService`, `StrategyService`) sont des stubs ou inexistants. Les imports fonctionnent mais les appels `await service.create_order(...)` échoueront à l'exécution.

**Problème :** illusion de complétude. Le code est écrit mais pas testable car les services ne sont pas implémentés.

---

### 2.3 Duplication de code entre `jobs/` et `backend/`

Les jobs `collect_ohlcv.py` et `load_ohlcv.py` réimplémentent :
- Le client MinIO (identique à celui du backend)
- Le mapping klines Binance (identique à `market/clients/`)
- La logique de connexion DB

Alors que le backend a déjà toute cette infrastructure via `shared/`. Les jobs auraient dû réutiliser le package `shared/` du backend.

---

### 2.4 Script SQL MySQL pour une base PostgreSQL

**Fichier :** `backend/src/shared/database/init_database.sql` (517 lignes)

Ce fichier est écrit en **syntaxe MySQL** :
```sql
CREATE DATABASE crypto_trading_bot;
USE crypto_trading_bot;           -- MySQL, en PostgreSQL : \c
id VARCHAR(36) PRIMARY KEY DEFAULT (UUID()),  -- MySQL, PG: gen_random_uuid()
updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,  -- MySQL pur
```

Tout le projet utilise PostgreSQL. Ce fichier est donc **inutilisable** et potentiellement dangereux si quelqu'un l'exécute sur la base de production.

---

### 2.5 `from_orm()` déprécié dans Pydantic V2

**Fichier :** `backend/src/strategy/router.py:115`
```python
strategy_response = StrategyResponse.from_orm(strategy)
```

`from_orm()` est supprimé dans Pydantic V2. Remplacer par `model_validate(strategy)`. Le projet utilise `pydantic==2.12.5` donc cette ligne lèvera une `AttributeError` à l'exécution.

---

## 3. Qualité du code et dette technique

### 3.1 Prolifération des outils de formattage

| Fichier | line-length | target-version |
|---------|-------------|----------------|
| `pyproject.toml` (racine) | 120 | py314 |
| `frontend/pyproject.toml` | 100 | py310 |
| `models/pyproject.toml` | ? | ? |

Trois fichiers `pyproject.toml` avec des règles Ruff différentes. Le fichier racine cible Python 3.14 pendant que le frontend cible 3.10. Incohérence garantie.

---

### 3.2 Pas de type checking dans la CI

La CI exécute Ruff (lint + format) mais pas **mypy** ou **pyright**. Pour un projet de cette taille avec des appels asynchrones complexes et des relations SQLAlchemy, l'absence de type checking statique est une source de bugs silencieux.

---

### 3.3 Base SQLite commitée

**Fichier :** `backend/src/shared/database/db.sqlite3`

Un fichier SQLite de 0-2 Ko est commité dans le dépôt. C'est un résidu de développement local qui n'aurait jamais dû être versionné. `.gitignore` ne l'exclut pas.

---

### 3.4 Migrations Alembic absentes

**Dossier :** `backend/src/shared/database/migrations/{versions}/` — vide

Le dossier est préparé mais aucune migration n'a été générée. La création des tables se fait via `Base.metadata.create_all(bind=engine)` au démarrage — un pattern déconseillé en production car il ne permet pas les migrations incrémentales.

---

### 3.5 Rate limiting déclaré mais pas implémenté

Settings :
```python
RATE_LIMIT_ENABLED: bool = True
RATE_LIMIT_REQUESTS: int = 100
```

Mais aucun middleware FastAPI de rate limiting n'est présent dans `main.py`. C'est un **dead code** qui donne une fausse impression de sécurité.

---

### 3.6 `requirements.txt.template` en double emploi

Les fichiers `requirements.txt.template` (backend, jobs, orchestration) sont compilés en `requirements.txt` via `generate-requirements.py`. Mais les `requirements.txt` finaux sont **aussi commités dans le dépôt**, créant une redondance et un risque de désynchronisation si on modifie l'un sans régénérer l'autre.

---

## 4. Problèmes opérationnels

### 4.1 Pas de monitoring / alerting

Aucun des éléments suivants n'est présent :
- Prometheus metrics (`/metrics`)
- Structured logging (JSON)
- Sentry ou équivalent pour le crash reporting
- Health check réel de dépendances (PostgreSQL, MinIO, Binance)

Le health check `/health/detailed` retourne des infos mais n'est pas utilisé par un système de monitoring externe.

---

### 4.2 Dockerfile backend copie les tests en production

**Fichier :** `backend/Dockerfile:84`
```dockerfile
COPY --chown=app:app . .
```

Cette instruction copie tout le dossier backend, y compris les tests, les fixtures, et les fichiers de configuration de test dans l'image de production. Cela augmente la surface d'attaque et la taille de l'image.

---

### 4.3 Airflow en LocalExecutor seulement

Airflow est configuré en `LocalExecutor`, ce qui signifie que toutes les tâches s'exécutent dans le processus du scheduler. En production, ça ne passera pas à l'échelle :
- Impossible de paralléliser les tâches
- Une tâche qui consomme trop de mémoire peut tuer le scheduler
- Pas de résilience worker-by-worker

Le passage à `CeleryExecutor` (avec Redis) ou `KubernetesExecutor` est indispensable pour la prod.

---

### 4.4 Gestion des batches dans `load_ohlcv.py`

```python
records = df.to_dict(orient="records")
with engine.begin() as conn:
    conn.execute(upsert_stmt)
```

Si le DataFrame fait 1000 lignes, il envoie une seule requête avec 1000 lignes. C'est inefficace et peut causer des timeouts PostgreSQL. Aucun batching/chunking n'est implémenté.

---

## 5. Problèmes frontend

### 5.1 Dépendance directe à `plotly.express` avec fallback silencieux

```python
try:
    import plotly.express as px
except ModuleNotFoundError:
    px = None
```

Si Plotly n'est pas installé (environnement minimal), les graphiques sont simplement masqués sans erreur visible. L'utilisateur voit une page vide sans comprendre pourquoi. Un check au démarrage serait préférable.

---

### 5.2 Mock-first sans timeline de migration réelle

La stratégie mock-first est pragmatique, mais il n'y a **aucun plan de migration** visible vers une vraie API backend. Les services mockés (`PortfolioService`, `AccountService`, etc.) ont des interfaces complètes mais appellent `MockStore` et non le backend. Sans roadmap claire, le risque est de stagner indéfiniment en mode "démo".

---

### 5.3 `st.page_link` enveloppé dans try/except partout

```python
try:
    st.page_link("pages/03_Portefeuille_Spot.py", label="...")
except Exception:
    st.caption("...")
```

Ce pattern try/except silencieux est répété dans quasiment toutes les pages. Il cache les vraies erreurs et rend le débogage difficile. Si une page est manquante, l'utilisateur voit juste un texte moins cliquable sans comprendre pourquoi.

---

## 6. Tests et qualité

### 6.1 Tests backend quasi absents

> **✅ Résolu (2026-07-27)** — Constat périmé : ce n'est plus le cas. Le dossier
> `backend/tests/` contient désormais 113 tests réels (auth, chiffrement des clés API,
> exécution multi-exchange, endpoints publics...), en plus de 171 côté frontend, 32 côté
> `utils/` et 3 côté `jobs/` (319 au total). Constat original conservé ci-dessous pour
> mémoire, ne reflète plus l'état du code.

Le dossier `backend/tests/` existe avec une belle structure :
```
tests/
├── conftest.py
├── fixtures/
├── integration/
└── unit/
```

Mais les fichiers sont vides ou squelettiques. Pour un backend avec ~2000 lignes de code métier (auth, database, settings, error handling), c'est un **vide critique**. Aucune garantie que le login, le refresh token, ou le fallback SQLite fonctionnent.

### 6.2 Pre-commit hook exécute les tests à chaque commit

> **✅ Partiellement résolu (2026-07-27)** — `scripts/run-tests-if-needed.sh` ne lance plus
> systématiquement toute la suite : il cible désormais les suites concernées par les zones
> modifiées (`backend/`, `frontend/`, `utils/`, `jobs/`), avec prise en compte des
> dépendances (`utils/` relance aussi `backend`/`jobs`, qui en dépendent). Le déclenchement
> du hook lui-même reste sur tout fichier `.py` modifié (pas de granularité par fichier de
> test précis) — la remarque garde donc une part de validité, mais l'attente "toute la
> suite à chaque commit" décrite ci-dessous n'est plus exacte.

**Fichier :** `.pre-commit-config.yaml:53-58`
```yaml
- id: run-tests
  name: "Run lint + tests for changed code"
  entry: scripts/run-tests-if-needed.sh
  files: '^(backend|frontend)/src/.*\.py$'
```

Ce hook s'exécute sur **n'importe quel** fichier `.py` modifié dans backend/frontend, pas seulement ceux impactés par le changement. Pour un commit d'une seule ligne, l'utilisateur attend que toute la suite de tests s'exécute.

---

## 7. Sécurité des dépendances

### 7.1 Dépendances non utilisées

**Fichier :** `backend/requirements.txt`
```
pyarrow==23.0.1      # Non utilisé dans le backend (utile dans jobs)
fastparquet==2026.3.0  # Idem — non utilisé dans le backend
```

Ces dépendances alourdissent l'image Docker backend inutilement.

---

## 8. Synthèse et priorités

| Priorité | Problème | Impact | Effort |
|----------|----------|--------|--------|
| **P0** | `SECRET_KEY` par défaut | 🔴 Critique | 5 min |
| **P0** | CORS/ALLOWED_HOSTS en wildcard | 🔴 Critique | 5 min |
| **P0** | `from_orm()` cassé en Pydantic V2 | 🔴 Critique (runtime error) | 2 min |
| **P1** | Script SQL en syntaxe MySQL | 🟠 Élevé | 30 min |
| **P1** | Timestamp en dur dans health check | 🟠 Élevé (debugging) | 1 min |
| **P1** | Migrations DB absentes | 🟠 Élevé (prod) | 2h |
| **P1** | Mots de passe en clair dans mocks | 🟠 Élevé | 10 min |
| **P2** | Pas de type checking dans CI | 🟡 Moyen | 30 min |
| **P2** | Rate limiting non implémenté | 🟡 Moyen | 2h |
| **P2** | Tests backend absents | 🟡 Moyen | 8h+ |
| **P2** | Duplication jobs vs backend | 🟡 Moyen | 4h |
| **P3** | Deux configs Ruff divergentes | 🔵 Faible | 15 min |
| **P3** | SQLite commité dans le dépôt | 🔵 Faible | 1 min |
| **P3** | Plotly import silencieux | 🔵 Faible | 10 min |

### Résumé

**3 problèmes bloquants P0** qui causeront un runtime error ou une faille de sécurité en production. Le plus urgent est le `from_orm()` déprécié qui fait planter tous les endpoints `/strategies`.

La force du projet réside dans son **architecture** et sa **CI/CD**. La faiblesse est dans le **décalage entre le volume de code écrit et ce qui est réellement testé/fonctionnel**. Les routers backend font illusion (2000+ lignes d'endpoints) mais les services sous-jacents sont des stubs.
