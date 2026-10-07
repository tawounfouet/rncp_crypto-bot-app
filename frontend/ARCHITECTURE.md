# Architecture — frontend/

> Document de référence de la couche **UI Streamlit**. Vue système globale dans [`../ARCHITECTURE.md`](../ARCHITECTURE.md) ; constats dans [`../CODEBASE_ANALYSIS.md`](../CODEBASE_ANALYSIS.md).

---

## 1. Vue d'ensemble

Application **Streamlit multipage, « mock-first »** : elle peut fonctionner sans backend (données de démonstration locales) ou en mode réel (REST `/api/v1` + JWT). Un seul client HTTP authentifié et un client public, une couche de services métier, un état porté par `st.session_state`.

```
frontend/
├── src/
│   ├── app.py                 # page Connexion (entrée)
│   ├── pages/                 # 12 pages (Streamlit découvre par nom de fichier)
│   ├── layouts/page_shell.py  # setup_page() : shell commun à toutes les pages
│   ├── navigation/rules.py    # PAGES + can_access() + sidebar_entries()
│   ├── services/              # clients HTTP + services métier
│   ├── state/session.py       # session_state + tokens
│   ├── components/            # briques UI (alerts, cards, tables, navigation, …)
│   ├── theme/                 # tokens, manager, styles, plotly
│   ├── schemas/               # modèles Pydantic (auth, bot, market, …)
│   ├── mocks/                 # MockStore, factories, scenarios
│   ├── prerequisites/         # pré-requis exchange par page
│   ├── utils/                 # formatters, validators, dates, …
│   └── pydantic/              # SHIM local masquant le vrai paquet pydantic
├── pyproject.toml             # ruff line-length=100, pytest pythonpath=["src"]
├── Dockerfile
├── requirements.txt(.template)
├── tests/{unit,integration,smoke}   # 226 tests
└── README.md
```

Métriques : **13 220 lignes / 104 fichiers** Python ; **12 pages**.

---

## 2. Navigation et shell de page

- **Entrée** : `app.py` = page de connexion. `main()` (`app.py:73`) appelle `setup_page(..., page_key="login")` puis affiche le formulaire (`AuthService.login`).
- **Shell commun** : chaque page commence par `setup_page(title, icon, page_key)` (`layouts/page_shell.py:14`) qui :
  1. `st.set_page_config` + `apply_global_styles(get_theme_mode())` (`page_shell.py:19-20`) ;
  2. `get_store()` + `AuthService.ensure_authenticated_user()` (`page_shell.py:22-24`) ;
  3. `can_access(page_key, user)` (`page_shell.py:28,49`) — lève une `KeyError` si la clé n'existe pas dans `PAGES`.
- **Règles d'accès** : `navigation/rules.py` définit `PAGES` (12 entrées : `dashboard`, `market`, `login`, `signup`, `portfolio`, `performance`, `bot_control`, `bot_config`, `account`, `backtesting`, `admin`, `privacy`) et `can_access` (`rules.py:140`) qui s'appuie sur `get_page` (`rules.py:109`).
- **Barres latérales** : `components/navigation.py` (`render_public_sidebar`, `render_private_sidebar`) alimentées par `sidebar_entries(user)` (`rules.py`).

> ⚠️ `pages/09_Binance_Testnet_Lab.py` appelle `setup_page(..., page_key="binance_testnet_lab")`, clé absente de `PAGES` → `KeyError` au chargement (B11).

---

## 3. Couche services

| Fichier | Rôle |
|---|---|
| `services/api_client.py` | Client **public/authentifié** (`BackendApiClient`) : user, market, trading, stratégies, backtests… |
| `services/auth_api_client.py` | Client **compte/testnet** (`AuthApiClient`) : `/users/me`, `/binance-testnet/*`, credentials exchange |
| `services/base.py` | `ServiceError` (exception commune) |
| `services/runtime_mode.py` | `allow_mock_fallback()` (mock autorisé par défaut, désactivable via `DISABLE_MOCK_FALLBACK`), `backend_required_message()` |
| `services/auth_service.py` | `AuthService` : login/register/logout, `ensure_authenticated_user` (`auth_service.py:99`), refresh de jeton (`_refresh_access_token`) |
| `services/*_service.py` | Services métier : `account`, `admin`, `backtest`, `bot_config`, `bot_control`, `dashboard`, `market`, `performance`, `portfolio`, `binance_testnet_lab` |

**Deux conventions de retour** coexistent : `ApiResponse` (dataclass du client) et tuples `(bool, message)` dans certains services métier.

---

## 4. État de session

`state/session.py` centralise l'accès à `st.session_state` (pas de store externe). Clés principales :

| Clé | Rôle |
|---|---|
| `app_store` | `MockStore` (données locales) |
| `access_token` / `refresh_token` | jetons JWT |
| `user_data` / `authenticated` | profil courant / drapeau |
| `exchange_configured` / `exchange_synced` | état de config exchange |
| `selected_exchange` | exchange courant |
| `user_synced_at` / `user_synced_token` | cadence de resynchronisation (~60 s) |

Fonctions notables : `get_store`, `reset_store`, `clear_auth_session` (nettoyage des jetons/flags), `set_selected_exchange`.

---

## 5. Thème, composants, schémas, mocks

- **Thème** : `theme/tokens.py` (design tokens, `get_theme_tokens`), `theme/manager.py` (`ThemeMode` dark/light, persistance dans le store), `theme/styles.py` (CSS global, `@import` Google Fonts — V11), `theme/plotly.py` (thème des graphes).
- **Composants** : `components/` — `alerts.py` (`show_feedback`), `cards.py`, `tables.py`, `badges.py`, `headers.py`, `navigation.py`, `prerequisites.py`.
- **Schémas** : `schemas/` — modèles Pydantic (`auth`, `account`, `admin`, `bot`, `common`, `dashboard`, `market`, `performance`, `portfolio`).
- **Mocks** : `mocks/db.py` (`MockStore`, `create_mock_store` — `mocks/db.py:163`), `factories.py`, `scenarios.py` (`MockScenario`). Le mode mock est piloté par `runtime_mode.py`.
- **Pré-requis** : `prerequisites/exchange.py` — `page_requires_exchange`, `is_exchange_configured`, `evaluate_exchange_prerequisite`.

> ⚠️ `src/pydantic/` est un **shim** : dès que `src/` est sur le `PYTHONPATH` (tests + conteneur), il **masque** le vrai paquet `pydantic`. Ne pas le remplacer sans vérifier.

---

## 6. Tests & qualité

- `tests/unit` · `tests/integration` · `tests/smoke` = **226 tests**.
- Lancement **depuis `frontend/`** (le `pyproject.toml` porte `pythonpath=["src"]` et `testpaths=["tests"]`) : `cd frontend && ../.venv/bin/python -m pytest tests -q`.
- Convention imposée par un test : **aucun fallback mock silencieux** quand le backend est injoignable (`tests/unit/test_no_silent_mock_fallback.py`).
- Ruff : config locale `line-length=100` (`frontend/pyproject.toml`).

---

## 7. Limites structurelles (renvoi)

1. Page Testnet Lab dont la clé de navigation est inconnue (B11).
2. Endpoints Testnet appelés alors que le routeur backend n'est pas monté (B14).
3. Échecs d'API déguisés en absence de données (B4 via `backtest_service`).
4. `@import` Google Fonts externe (V11) et `API_URL` par défaut `localhost` (V12).

Argumentation : [`../ANALYSE_CRITIQUE.md`](../ANALYSE_CRITIQUE.md).
