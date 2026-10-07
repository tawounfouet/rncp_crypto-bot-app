# INDEX — Documentation du projet

Point d'entrée de toute la documentation. Ce dépôt contient **8 documents Markdown** à la racine : cette page sert de sommaire et de guide de navigation.

---

## 1. Les documents

| Document | Rôle | Contenu en une ligne | À lire quand… |
|---|---|---|---|
| [`README.md`](./README.md) | Point d'entrée | Présentation, architecture du monorepo, démarrage rapide, déploiement, avertissement sécurité | On découvre le projet |
| [`CODEBASE_ANALYSIS.md`](./CODEBASE_ANALYSIS.md) | Faits | Métriques, architecture, inventaire des endpoints, 14 bugs `B1…B14`, 13 vulnérabilités `V1…V13`, dette | On veut l'état factuel et exhaustif |
| [`ANALYSE_CRITIQUE.md`](./ANALYSE_CRITIQUE.md) | Jugement | Verdict /10 par dimension, thèse centrale, critiques d'architecture/sécurité/frontend/processus, réparer vs réécrire | On veut un avis tranché et priorisé |
| [`RECOMMANDATIONS.md`](./RECOMMANDATIONS.md) | Action | Plan de remédiation en 6 phases (0→5), correctifs prêts à l'emploi, suite de tests minimale | On passe à la correction |
| [`ARCHITECTURE.md`](./ARCHITECTURE.md) | Référence technique | Vue système, cycle de requête, flux métier (auth, bots, ingestion, ML), modèle de données, conventions | On modifie le code ou on déploie |
| [`DEMO_SOUTENANCE.md`](./DEMO_SOUTENANCE.md) | Démo soutenance | Mise en place (`make demo-up`), seed, comptes, parcours, seedé vs live, dépannage | On prépare/présente la soutenance |
| [`AGENTS.md`](./AGENTS.md) | Instructions agents | Règles OpenCode, pièges vérifiés, commandes (fichier gitignoré) | On outille un agent IA sur ce repo |
| [`INDEX.md`](./INDEX.md) | Sommaire | Cette page | On cherche où aller |

**Ordre de lecture suggéré** : `README.md` → `CODEBASE_ANALYSIS.md` → `ANALYSE_CRITIQUE.md` → `RECOMMANDATIONS.md`, puis `ARCHITECTURE.md` en référence. `AGENTS.md` au besoin.

---

## 2. Navigation par tâche

| Je veux… | Aller à |
|---|---|
| Lancer le projet en local | [`README.md`](./README.md#demarrage-rapide) puis `docs/01-setup.md` |
| Préparer/présenter la démo de soutenance | [`DEMO_SOUTENANCE.md`](./DEMO_SOUTENANCE.md) |
| Configurer les variables d'environnement | `docs/01-setup.md` · `.env.example` · [`CODEBASE_ANALYSIS.md`](./CODEBASE_ANALYSIS.md#63-configuration-bloquante) |
| Comprendre un flux métier (bots, marché, ML) | [`ARCHITECTURE.md`](./ARCHITECTURE.md#23-flux-métier-clés) |
| Connaître les failles de sécurité | [`CODEBASE_ANALYSIS.md`](./CODEBASE_ANALYSIS.md#4-sécurité--vulnérabilités) §4 |
| Retrouver un bug précis | [`CODEBASE_ANALYSIS.md`](./CODEBASE_ANALYSIS.md#5-bugs-confirmés-reproductibles-par-lecture-du-code) §5 (IDs `B1…B14` explicites) |
| Comprendre la décision « réparer ou réécrire » | [`ANALYSE_CRITIQUE.md`](./ANALYSE_CRITIQUE.md#8-réparer-ou-réécrire) §8 |
| Commencer à corriger | [`RECOMMANDATIONS.md`](./RECOMMANDATIONS.md#phase-1--sécurité-bloquante) Phase 1, puis Phases 2-3 |
| Écrire les tests manquants | [`RECOMMANDATIONS.md`](./RECOMMANDATIONS.md#filet-de-sécurité--suite-de-tests-minimale-à-faire-en-premier-de-la-phase-1) |
| Configurer la CI / l'outillage | `AGENTS.md` · `.gitlab-ci.yml` · [`RECOMMANDATIONS.md`](./RECOMMANDATIONS.md#phase-4--robustesse--qualité) |
| Déployer (K8s / VM AWS) | [`README.md`](./README.md#infrastructure-kubernetes-talos--argocd) · `docs/01-setup.md` |
| Moderniser / réduire la dette | [`RECOMMANDATIONS.md`](./RECOMMANDATIONS.md#phase-5--modernisation-opportun-après-stabilisation) |

---

## 3. Carte rapide du code source

| Package | Point d'entrée | Cœur du système | Architecture détaillée |
|---|---|---|---|
| `backend/` | `backend/src/main.py` (FastAPI `:8009`) | `*/router.py` → `*/service.py` → `*/models.py` | [`backend/ARCHITECTURE.md`](./backend/ARCHITECTURE.md) |
| `frontend/` | `frontend/src/app.py` (Streamlit `:8501`) | `frontend/src/pages/*` + `frontend/src/services/*` | [`frontend/ARCHITECTURE.md`](./frontend/ARCHITECTURE.md) |
| `models/` | `models/src/main.py` (ml-api `:8010`) | `models/src/api/main.py` · `models/src/training/` | [`models/ARCHITECTURE.md`](./models/ARCHITECTURE.md) |
| `jobs/` | `jobs/ingest/collect_ohlcv.py` · `jobs/transform/load_ohlcv.py` | `utils/connectors/` (MinIO, exchanges) | [`jobs/ARCHITECTURE.md`](./jobs/ARCHITECTURE.md) |
| `orchestration/` | `orchestration/dags/*` (Airflow `:8080`) | `ingest_ohlcv`, `ml_pipeline`, `purge_inactive_users`, `backfill_ohlcv` | [`orchestration/ARCHITECTURE.md`](./orchestration/ARCHITECTURE.md) |
| `utils/` | `utils/__init__.py` (package partagé) | `utils/connectors/` · `utils/trading/signals.py` · `utils/features/` | [`utils/ARCHITECTURE.md`](./utils/ARCHITECTURE.md) |
| `ci/` | `ci/docker-compose.test.yml` | tests d'intégration Docker + Postgres | [`ci/ARCHITECTURE.md`](./ci/ARCHITECTURE.md) |

Fichiers à connaître absolument avant toute modification :

- `backend/src/main.py` — montage des routeurs (dont le routeur interne bots **sans préfixe**) et middlewares.
- `backend/src/shared/config/settings.py` — toutes les variables d'environnement (`CORS_ORIGINS`, `ALLOWED_HOSTS`, `JWT_SIGNING_KEY`, `EXCHANGE_ENC_KEY`…).
- `backend/src/shared/database/connection.py` — `get_db_session()` (commit à la sortie) et `sessionmaker(autoflush=False)` : détermine les pièges de persistance (B1).
- `backend/src/market/service.py` — contient le chemin de **données simulées** (B6).
- `frontend/src/navigation/rules.py` — `PAGES` et `can_access` : toute nouvelle page doit y être déclarée (B11).
- `versions.env` + `*.requirements.txt.template` — source unique des versions ; les `requirements*.txt` sont **générés**.

---

## 4. Repères chiffrés

- **6 packages** : `backend`, `frontend`, `models`, `jobs`, `orchestration`, `utils` (+ `ci`).
- **LOC Python** : 45 827 lignes / 327 fichiers — backend 24 134, frontend 13 220, models 5 403, utils 1 257, orchestration 823, jobs 791.
- **436 fichiers suivis dans Git** ; branche `staging`.
- **Endpoints backend** : **77 chemins / 91 opérations** montés (schéma OpenAPI) ; **10** dans `ml-api` ; **13** routes définies mais non montées (`/binance-testnet`, B14).
- **Modèles de données** : 21 tables SQLAlchemy.
- **Pages frontend** : 12.
- **Tests** : 214 backend · 226 frontend · 39 utils+jobs · 36 models = **515 tests locaux** ; en CI, seuls les tests d'intégration backend (~214) tournent.
- **Bugs confirmés** : **14** (`B1…B14`).
- **Vulnérabilités** : **6** 🔴 critiques · **4** 🟠 élevées · **3** 🟡 moyennes = **13** (`V1…V13`).
- **Dette** : pas de `.dockerignore` racine ; CI sans tests unitaires ni `models/`/`orchestration/` ; `skops` non épinglé ; README initial incomplet.

---

*Dernière mise à jour : 2026-07-28 — documents générés lors d'un audit complet de la codebase.*
