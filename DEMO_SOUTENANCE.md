# Démonstration de soutenance — Crypto-Bot App

> Guide complet de la **mise en place** et du **déroulé** de la démonstration : un jeu de données déterministe, un environnement dédié (worker de bots désactivé) et un parcours utilisateur de bout en bout sur Streamlit.
>
> Documents liés : [`README.md`](./README.md) · [`INDEX.md`](./INDEX.md) · [`ARCHITECTURE.md`](./ARCHITECTURE.md) · [`CODEBASE_ANALYSIS.md`](./CODEBASE_ANALYSIS.md).

---

## 1. Objectif

Pouvoir présenter, en quelques minutes et sans dépendance à un exchange réel, **l'intégralité du parcours utilisateur** de l'application :

- connexion / inscription, tableau de bord, marché ;
- portefeuille Spot, performances ;
- catalogue et contrôle des bots (start/pause/stop), décisions/ordres/trades ;
- backtesting (historique + import de données) ;
- gestion de compte, administration, politique de confidentialité.

La démonstration repose sur deux briques :

1. **`backend/scripts/seed_demo.py`** — un seed **idempotent** qui peuple la base (PostgreSQL, ou SQLite en repli) avec un utilisateur, un admin, un exchange configuré, des bots et leur activité, des données de marché, des backtests et un portefeuille.
2. **`docker-compose.demo.yml`** — une **surcharge** de `docker-compose.yml` qui **désactive le worker de bots** (`ENABLE_BACKGROUND_TASKS=0`) : aucune décision/ordre n'est exécuté en direct, tout provient du seed → rendu **déterministe**.

---

## 2. Prérequis

- Docker + Docker Compose.
- Avoir cloné le dépôt et créé le fichier d'environnement :

```bash
cp .env.example .env
# éditer .env : renseigner au minimum JWT_SIGNING_KEY et EXCHANGE_ENC_KEY
#   JWT_SIGNING_KEY   : clé de signature des JWT (backend)
#   EXCHANGE_ENC_KEY  : clé AES-GCM (base64) pour chiffrer les identifiants d'exchange
```

Générer une `EXCHANGE_ENC_KEY` valide :

```bash
python3 -c "import os,base64; print(base64.b64encode(os.urandom(32)).decode())"
```

> Ne **jamais** appeler `docker compose` directement : seul le `Makefile` charge `versions.env` (+ `.env`). Taper `make` pour la liste des cibles. Détails : [`docs/01-setup.md`](docs/01-setup.md).

---

## 3. Démarrage en une commande

```bash
make demo-up
```

Cette cible :

1. démarre la stack en surchargeant `docker-compose.yml` par `docker-compose.demo.yml` (worker de bots **off**) ;
2. attend que le backend soit *healthy* (`GET /health`) ;
3. exécute le seed (`python /app/scripts/seed_demo.py --reset`) dans le conteneur backend.

À la fin, l'URL est affichée : **http://localhost:8501**.

### Cibles Makefile

| Cible | Effet |
|---|---|
| `make demo-up` | Démarre la stack démo + attend le backend + seed |
| `make demo-seed` | (Re)peuple uniquement le jeu de données (stack déjà démarrée) |
| `make demo-reset` | Stop + suppression des volumes + redémarrage + seed (reset « from 0 ») |
| `make demo-down` | Arrête l'environnement de démonstration |

### Lancement manuel (équivalent)

```bash
docker compose -f docker-compose.yml -f docker-compose.demo.yml up -d
docker compose -f docker-compose.yml -f docker-compose.demo.yml exec -T crypto-bot-backend \
    python /app/scripts/seed_demo.py --reset
```

---

## 4. Comptes de démonstration

| Rôle | Email | Mot de passe |
|---|---|---|
| Utilisateur démo | `demo@cryptobot.dev` | `Demo12345!` |
| Administrateur | `admin@cryptobot.dev` | `Admin12345!` |

> Ces identifiants sont **fictifs** et destinés à la démo. Le seed est idempotent : `--reset` supprime puis recrée ces comptes et leurs données (état identique à chaque exécution).

---

## 5. Ce que le seed crée

`backend/scripts/seed_demo.py` (exécuté dans le conteneur backend, `/app/scripts/seed_demo.py`) :

| Domaine | Contenu |
|---|---|
| Utilisateurs | 1 utilisateur démo + 1 administrateur (`UserService.create_user`, mot de passe haché argon2id) |
| Exchange | Binance configuré en **mode sandbox** (`UserSettings.set_api_credentials`, clés chiffrées AES-GCM) → les pages à pré-requis exchange ne sont pas bloquées |
| Bots | 3 templates **publiés** (créés par le seed, autonomes vis-à-vis du ml-api) et 3 instances verrouillées : `ACTIVE` (14 trades), `PAUSED` (9), `STOPPED` (6) |
| Journal | Par bot : `BotRun`, `TradingDecision`, `BotOrder`, `BotTrade` et une `BotPosition` (PnL réalisé/non réalisé) |
| Marché | ~2 882 bougies **1h** sur 60 jours pour `BTCUSDC` et `ETHUSDC` (table `market_data`) |
| Backtests | 3 `BacktestResult` (RSI BTCUSDC 1h, MA Cross ETHUSDC 4h, Multi-indicateurs BTCUSDC 1h) |
| Portefeuille | 1 `Strategy`, 1 `StrategyDeployment`, 1 `TradingSession`, 6 `Order` + `OrderFill`, 7 `Transaction` |

Le catalogue de bots intégré étant `disabled` et les templates ML dépendant du ml-api, le seed **crée ses propres templates publiés** (`demo-rsi-btcusdc-1h-v1`, `demo-trend-ethusdc-4h-v1`, `demo-multi-btcusdc-1h-v1`) pour être totalement autonome.

### Réinitialisation

```bash
make demo-seed      # relance le seed avec --reset
make demo-reset     # vide les volumes (base + MinIO) puis recrée tout
```

---

## 6. Périmètre : seedé vs live

| Écran (page) | Source des données | Fonctionne hors-ligne ? |
|---|---|---|
| Connexion / Inscription (`app.py`, `02`) | Backend (auth) | Oui |
| Tableau de bord (`00`) | Seed (bots + performances) | Oui |
| Marché (`01`) | **Exchange réel** (prix/klines publics) | Non (réseau requis) |
| Portefeuille Spot (`03`) | **Exchange réel** (soldes) + BDD | Partiel (soldes live) |
| Performances Spot (`04`) | Seed (agrégats backend) | Oui |
| Contrôle Bot (`05`) | Seed (bots + journal) | Oui |
| Paramétrage / Catalogue Bots (`06`) | Seed (templates + bots) | Oui |
| Gestion de compte (`07`) | Seed (profil + settings) | Oui |
| Admin (`08`) | Seed (utilisateurs) | Oui |
| Backtesting (`09`) | Seed (backtests + marché) ; import = live | Oui (consultation) |
| Binance Testnet Lab (`09`) | **Exchange Binance Testnet** (clés requises) | Non |
| Confidentialité (`10`) | Statique | Oui |

> Les pages **Marché**, **Portefeuille** (soldes) et **Testnet Lab** dépendent d'un appel exchange réel. Pour une démo 100 % hors-ligne, limiter le parcours à la colonne « Oui » ci-dessus.

---

## 7. Parcours de démonstration conseillé

1. **Connexion** — `demo@cryptobot.dev` / `Demo12345!` (page `app.py`).
2. **Tableau de bord** (`00`) — vue agrégée des 3 bots, PnL, statuts.
3. **Catalogue Bots Spot** (`06`) — templates verrouillés et paramétrage (montant par ordre, circuit breaker).
4. **Contrôle Bot Spot** (`05`) — sélectionner un bot, jouer **start / pause / stop**, consulter décisions, ordres, trades et position.
5. **Performances Spot** (`04`) — KPI, courbe d'equity, journal des trades, contribution par bot.
6. **Backtesting** (`09`) — onglet *Historique* (3 backtests seedés), onglet *Import* (démonstration de l'import OHLCV), onglets de configuration.
7. **Portefeuille Spot** (`03`) — portefeuille / ordres / transactions (partie live : montrer l'état de connexion exchange).
8. **Gestion de compte** (`07`) — profil (édition persistée), settings, credentials exchange (mode sandbox/live).
9. **Admin** (`08`) — se reconnecter avec `admin@cryptobot.dev` / `Admin12345!` : liste/gestion des utilisateurs.
10. **Politique de confidentialité** (`10`) — clôture.

---

## 8. Architecture du mode démo

```
docker-compose.yml  ──┐
                      ├──►  stack complète (backend, frontend, Postgres, MinIO,
docker-compose.demo.yml┘     ml-api, MLflow, Airflow)
                           + ENABLE_BACKGROUND_TASKS=0  (worker de bots OFF)
                             │
                             ▼
   backend/scripts/seed_demo.py  ──►  PostgreSQL (utilisateurs, bots, journal,
                                      marché, backtests, portefeuille)
```

- **Surcharge Compose** : `docker-compose.demo.yml` ne remplace pas `docker-compose.yml`, il le complète (fusion par clé).
- **Worker désactivé** : `BotWorker` n'est pas lancé (`main.py`, `lifespan`) → pas d'exécution automatique, pas d'appel exchange déclenché par les bots.
- **Frontend** : en dev, `DISABLE_MOCK_FALLBACK=1` et `API_URL=http://crypto-bot-backend:8009` → l'UI consomme la **vraie** API et donc les données seedées.

---

## 9. Correctifs appliqués pour la démonstration

Quatre bugs de l'audit `CODEBASE_ANALYSIS.md` bloquaient le parcours et ont été corrigés :

| # | Fichier | Correction |
|---|---|---|
| **B1** | `backend/src/auth/user_service.py` | `session.flush()` **avant** `session.refresh()` → la mise à jour de profil (`PUT /users/me`) est désormais persistée (reproduit/vérifié). |
| **B4** | `backend/src/strategy/router.py` | Route `GET /strategies/backtests` déclarée **avant** `GET /{strategy_id}` → l'historique des backtests répond (au lieu d'un 404). |
| **B11** | `frontend/src/navigation/rules.py` | Clé `binance_testnet_lab` ajoutée à `PAGES` → la page ne plante plus (`KeyError`). |
| **B14** | `backend/src/main.py` | Routeur `/binance-testnet` monté sous `/api/v1` (routes protégées par `get_current_user`). |
| **B15** | `frontend/src/pages/03_Portefeuille_Spot.py` | La page affichait « *{exchange}* n'est pas configuré. Ajoutez vos clés… » **et `return`** dès que `exchange_ok` était faux → message trompeur (les clés *sont* configurées) et données masquées. Affiche désormais le **message réel du backend** (« Impossible de contacter binance… ») et **poursuit le rendu** : ordres/trades issus de la base (seed) restent visibles. |
| **B16** | `frontend/src/services/portfolio_service.py` | Le backend renvoie ses listes sous enveloppe `{"success":true,"data":[…]}` ; le frontend ne cherchait que `[…]` ou `{"transactions":[…]}` → **« Derniers trades » / « Ordres ouverts » toujours vides** malgré des données en base. Ajout d'un décodeur `_unwrap_list` (liste brute ou `data`/`items`/`results`/clé nommée). Vérifié : 7 transactions seedées remontent. |

---

## 10. Ports et URL (dev/démo)

| Service | URL |
|---|---|
| Frontend Streamlit | http://localhost:8501 |
| Backend FastAPI (docs) | http://localhost:8009/api/v1/docs |
| MLflow UI | http://localhost:5001 |
| Airflow UI | http://localhost:8080 (admin / admin) |
| MinIO Console | http://localhost:9001 |

Détail complet par environnement : [`docs/01-setup.md`](docs/01-setup.md).

---

## 11. Lancement du seed hors conteneur (développement)

Le seed peut aussi tourner localement (repli SQLite) en fournissant l'environnement minimal :

```bash
KEY=$(python3 -c "import os,base64; print(base64.b64encode(os.urandom(32)).decode())")
JWT_SIGNING_KEY=test-key-not-prod ALLOWED_HOSTS=localhost CORS_ORIGINS=http://localhost:8501 \
USE_SQLITE_FALLBACK=true EXCHANGE_ENC_KEY="$KEY" \
PYTHONPATH=backend/src:. .venv/bin/python backend/scripts/seed_demo.py --reset
```

`--reset` supprime puis recrée les comptes et données de démo. Sans `--reset`, les comptes existants sont conservés.

---

## 12. Dépannage

| Symptôme | Cause probable | Solution |
|---|---|---|
| Le seed dit « exchange NON configuré » | `EXCHANGE_ENC_KEY` absente | la renseigner dans `.env` puis `make demo-seed` |
| Pages *Tableau de bord / Portefeuille / Performances* bloquées | Pré-requis exchange non détecté | vérifier `EXCHANGE_ENC_KEY`, relancer `make demo-seed`, se reconnecter |
| Aucun bot dans le catalogue | Seed non exécuté / reset partiel | `make demo-seed` |
| *Marché* vide | Pas d'accès réseau (prix live) | normal hors-ligne ; présenter les autres écrans |
| Portefeuille « exchange non connecté » | Clés sandbox factices (pas de compte réel) | attendu ; illustre l'état de connexion |
| Frontend ne voit pas les données | Backend pas *healthy* | attendre `make health` = OK, puis rafraîchir |
| Volumes/schéma incohérents | Base partiellement initialisée | `make demo-reset` |

Voir aussi [`docs/01-setup.md`](docs/01-setup.md) § dépannage.

---

## 13. Fichiers concernés

| Fichier | Rôle |
|---|---|
| `backend/scripts/seed_demo.py` | Seed du jeu de données de démonstration |
| `docker-compose.demo.yml` | Surcharge Compose (worker de bots désactivé) |
| `Makefile` | Cibles `demo-up`, `demo-seed`, `demo-reset`, `demo-down` |
| `README.md` | Section « Mode démonstration (soutenance) » |
| `backend/src/auth/user_service.py` | Correctif B1 |
| `backend/src/strategy/router.py` | Correctif B4 |
| `frontend/src/navigation/rules.py` | Correctif B11 |
| `backend/src/main.py` | Correctif B14 |

---

*Dernière mise à jour : 2026-07-28 — mise en place du mode démonstration pour la soutenance RNCP.*
