# Analyse critique — Crypto-Bot App

> Document d'**opinion** : évalue les choix de conception, pas seulement l'état des lieux. Les faits bruts et la liste exhaustive des bugs sont dans [`CODEBASE_ANALYSIS.md`](./CODEBASE_ANALYSIS.md) ; ici on répond à la question « ce code est-il bon, et pourquoi ? ».

---

## 1. Verdict global

| Dimension | Note /10 | Commentaire |
|---|---|---|
| Fonctionnel | 5/10 | Le socle ingère, entraîne et affiche, mais des features centrales sont cassées (B1 profil, B2/B3 achats, B4 historique backtests, B11 page Testnet) et d'autres renvoient du faux (B6, B8). |
| Sécurité | 3/10 | Cinq endpoints destructifs ou d'exécution sont accessibles anonymement (V1–V5) ; le contrôle d'accès n'est pas systématique. C'est le point le plus grave du dépôt. |
| Architecture | 7/10 | Découpage par domaine clair, pipeline data/ML cohérent, source de versions unique. Quelques décisions (routeur interne monté sans préfixe, auth dispersée) fragilisent l'ensemble. |
| Qualité de code | 6/10 | Code lisible et homogène, conventions respectées, mais beaucoup de `TODO` laissés en production et un chemin « simulé » jamais retiré. |
| Testabilité / DX | 6/10 | 515 tests locaux et bonne outillage pre-commit, mais **la CI n'exécute aucun test unitaire** et ignore `models/` et `orchestration/`. |
| Production-readiness | 4/10 | Le système prétend servir de vraies données et de vrais ordres tout en laissant des portes ouvertes et des horodatages figés. Non déployable en l'état sur un périmètre sensible. |

**En une phrase** : **un socle techniquement propre et bien découpé, miné par une confiance au client systématique — absence de garde sur les endpoints sensibles, données simulées présentées comme réelles — qui le rend inapte à la production tant que le contrôle d'accès n'est pas centralisé.**

---

## 2. Le problème n'est pas les bugs, c'est l'absence de frontière serveur

Les neuf bugs métier et les cinq failles critiques ne sont pas des accidents indépendants : ils partagent la même cause racine — **le serveur fait confiance à l'appelant, et les protections ne sont jamais posées comme invariant.**

- L'auth est ajoutée **endpoint par endpoint**, via `Depends(get_current_user)` recopié à la main. Cinq routes ont été oubliées (V1–V5) : `logout-all`, `purge-inactive`, `execute-active`, le routeur interne bots, l'API d'entraînement. Un `include_router(..., dependencies=[Depends(...)])` ou une dépendance de routeur aurait rendu l'oubli impossible.
- Quand un endpoint a été conçu « pour Airflow », l'auteur l'a **explicitement laissé sans auth** en s'appuyant sur un commentaire (« appele uniquement depuis le reseau docker »), puis l'a monté sous `/api/v1` et publié le port. La sécurité repose sur la documentation, pas sur le code.
- Le contrôle de propriété n'existe nulle part de façon générique : `logout_all_sessions(user_id)` accepte un identifiant client sans le confronter à `current_user` (V8).
- Le même réflexe s'applique aux **données** : `market/service.py` renvoie une marche aléatoire (« For testing ») sur des endpoints authentifiés documentés comme réels (B6) ; `check_health` renvoie `"connected"` sans rien tester (B9) ; `/health/detailed` retourne une constante `2025-07-29T03:15:00Z` (B10). **Le système simule la santé et les données qu'il devrait mesurer.**

Corriger la liste des bugs ne suffira pas : tant que la sécurité et la véracité des données ne deviennent pas des **invariants transverses**, la prochaine route oubliée ou le prochain mock laissé en place recréera exactement les mêmes symptômes. Le défaut est architectural, pas ponctuel.

---

## 3. Critiques d'architecture

### 3.1 L'authentification est un décor, pas une barrière
Recopier `Depends(get_current_user)` sur chaque route est simple à lire mais **sans rappel** : rien n'échoue au démarrage si une route l'oublie, aucun test ne vérifie systématiquement qu'une route sous `/users` est authentifiée. Résultat : cinq trous (V1–V5) et un test qui **défend** l'absence d'auth sur `execute-active` (`test_strategy_router.py:366`). Le choix « dépendance par endpoint » est défendable *si* complété par une dépendance de routeur et un test paramétré — ici ni l'un ni l'autre n'existe.

### 3.2 La séparation interne/public est purement déclarative
`internal_router` (bots) et `/internal/pipeline/*` (ml-api) reposent sur une convention de nommage, pas sur une frontière réseau réelle : tous les ports sont publiés et les routeurs internes sont montés. La confiance dans le commentaire a remplacé le contrôle (V4, V5). Une architecture multi-composants **doit** isoler les surfaces internes (réseau privé, auth de service) au lieu de compter sur le nom des routes.

### 3.3 Le frontend n'est pas une source de vérité, mais l'UI le croit
Le « mock-first » (`runtime_mode.py`) est un bon outil de démo, mais il laisse l'UI afficher un succès sur des endpoints qui échouent en silence : `list_backtests` renvoie `[]` en cas d'échec (`backtest_service.py:101-115`) et l'onglet historique affiche « Aucun backtest » au lieu de l'erreur (B4). Un échec de transport est ainsi déguisé en absence de données — l'utilisateur ne peut pas diagnostiquer. Le test `test_no_silent_mock_fallback.py` montre que l'équipe connaît le risque mais ne l'a pas généralisé.

### 3.4 Le flux de trading « au marché » n'a jamais été terminé
`market_buy`/`market_sell` et `_get_or_create_manual_deployment` sont des coquilles avec `TODO` (B2/B3), pourtant **documentées et exposées** (`backend/README.md:131-132`). Le module `trading` a été partiellement remplacé par `bots/`, mais ses endpoints cassés sont restés montés. C'est un symptôme de migration inachevée : deux chemins coexistent, l'un mort mais visible. Le même schéma touche le Testnet Lab : son routeur existe (13 routes) mais n'est **jamais monté** (B14), et sa page plante (B11) — la fonctionnalité est morte à ses deux extrémités, sans que rien ne l'indique.

### 3.5 La CI ne protège pas là où le risque est le plus grand
La décision « intégration backend seulement » laisse `models/` (entraînement, où une régression est silencieuse) **et** `orchestration/` (qui déclenche les pipelines) hors de tout filet. Les 226 tests frontend et 36 tests models existent mais ne sont jamais exécutés automatiquement. L'investissement de test est annulé par l'absence de porte de sortie.

---

## 4. Critique sécurité (au-delà de la liste des failles)

1. **Menace jamais envisagée : l'attaquant réseau anonyme.** Toute la conception postule des appelants coopératifs (Airflow, frontend). Or les composes publient les ports sur l'hôte : le scénario réaliste est un scan de ports → découverte de `/api/v1/users/purge-inactive` (destruction), `/api/v1/strategies/deployments/execute-active` (ordres réels) et `/internal/bot-templates/sync`. Aucun de ces appels n'exige de preuve d'identité.
2. **Primitive détournée : le JWT devient décoratif.** Le mécanisme d'auth est correct en soi, mais son application partielle le vide de sens : on peut agir sur des ressources d'autrui (`logout-all`, V1/V8) ou sur des ressources globales (`execute-active`) sans jeton.
3. **Confiance dans l'identifiant client.** `purge-inactive` accepte `days=1` (V2) et `logout-all` accepte n'importe quel `user_id` — deux paramètres de portée globale/étrangère pilotés par l'appelant. C'est un principe à interdire : un paramètre fourni par le client ne doit jamais élargir la portée d'une action.
4. **Secret de signature.** L'échec est *fail-safe* (clé obligatoire), mais l'exemple vide (V10) invite à une configuration incomplète ; à surveiller en staging/prod.
5. **Compromission réaliste en 5 minutes** : `curl`/enumération → purge ou exécution d'ordres, sans compte ni jeton, depuis n'importe quelle machine routant vers le port `8009`. Le manque de rate limiting (V7) rend en plus le brute-force du login trivial.

---

## 5. Critique du frontend / interface

- **Deux clients HTTP** (`api_client.py` public, `auth_api_client.py` authentifié) avec un chevauchement fonctionnel et des conventions de retour hétérogènes (`ApiResponse` vs tuples `(bool, msg)`) — surface d'incohérence.
- **Routage par nom de fichier** dans `pages/` avec numérotation dupliquée (`09_Backtesting.py` et `09_Binance_Testnet_Lab.py`) ; cette dernière n'est même pas déclarée dans `PAGES`, ce qui la rend buguée d'emblée (B11).
- **État de session global** (`st.session_state`) utilisé directement dans `setup_page` (`layouts/page_shell.py`) : la page testnet crashe lors de l'appel à `can_access` — le point d'entrée de chaque page est donc une source de crash si la clé n'est pas référencée.
- **Shim pydantic local** (`frontend/src/pydantic/`) qui masque le vrai paquet : choix assumé mais très fragile (un import pydantic réel inattendu change le comportement selon le `PYTHONPATH`).
- **Style** : un `@import` Google Fonts externe dans `theme/styles.py:15` couple le rendu à un réseau tiers (V11).

---

## 6. Critique du processus (DX, outillage, livrable)

- **Tests nombreux, CI partielle** : 515 tests au total, mais la CI ne joue que l'intégration backend. Le coût de cette absence est direct : les régressions `models/` et `frontend/` ne sont détectées qu'en local, donc « quand on y pense ».
- **`orchestration/` sans lint ni test** : les DAGs qui pilotent la production ne passent aucune vérification automatique ; un changement YAML faux ne sera vu qu'à l'exécution en Airflow.
- **Dépendances non épinglées à dur** : `skops` non pinné fait échouer deux tests ML ; `torch+cpu` n'est pas installable sur macOS, ce qui **décourage la reproduction locale** d'un composant clé.
- **`.dockerignore` racine absent** : chaque build envoie tout le dépôt au démon (lent, risque d'inclure `.env` si mal configuré).
- **README en retard** : l'architecture décrite omet `models/`, `jobs/`, `orchestration/`, `utils/` (voir mise à jour dans `README.md`). La prose diverge des sources exécutables, ce qui contredit la règle interne (AGENTS.md) qui donne priorité à `Makefile`/`versions.env`.
- **Documentation abondante mais non vérifiée** : les docs affirment des contrats (ports, absence d'auth « volontaire ») que le code contredit (V4, V5). Une doc qui « couvre » une faiblesse la rend plus dangereuse qu'aucune doc.

---

## 7. Ce qui mérite d'être sauvegardé

- **Le découpage par domaine** (`router`/`service`/`models`/`schemas`) : lisible, prévisible, propice à une correction ciblée — c'est la base sur laquelle centraliser l'auth est facile.
- **La gestion de versions unique** (`versions.env` + `scripts/check-infra.sh`) : pratique rare et saine.
- **Le socle de sécurité correct** : argon2id, chiffrement des identifiants d'exchange, JWT complet (`exp/iat/jti/type`), `TrustedHost`, Semgrep bloquant, hooks pre-commit.
- **Le pipeline data/ML** (ingest MinIO → transform Postgres → entraînement → ml-api) : cohérent et orchestré.
- **La couverture de tests existante** : 515 tests, dont une suite d'intégration backend sérieuse (214) — le travail est là, il « suffit » de le brancher en CI.
- **Le souci de traçabilité** : rapports de couverture suivis dans git, docs détaillées, commits conventionnels.

---

## 8. Réparer ou réécrire ?

| Option | Effort estimé | Verdict |
|---|---|---|
| **Réparer par patchs ciblés** (corriger les 14 bugs + 13 vulns) | 3–5 jours | Insuffisant seul : traite les symptômes sans empêcher la récidive (prochain endpoint oublié). À faire *après* la centralisation de l'auth. |
| **Centraliser l'auth + corriger les bugs** | 1–2 semaines | **Recommandé.** Un middleware/dépendance de routeur + revue systématique + tests de sécurité d'accès rendent les trous impossibles à réintroduire. Le socle est bon, il ne faut pas jeter le découpage. |
| **Réécrire le backend** | 1–2 mois | Non justifié : l'architecture est saine ; le problème est l'application incohérente d'un bon principe, pas le choix technologique. Le coût dépasse le bénéfice. |
| **Réécrire le frontend** | 2–3 semaines | Non prioritaire : Streamlit convient à un usage interne/démo. Le risque frontend est limité au diagnostic d'erreurs, pas à la sécurité. |

**Quel que soit le chemin, trois non-négociables :**
1. **Revalidation serveur obligatoire** : identité (`user_id` vient du jeton, jamais du client), portée des actions, et données sensibles (aucun mock servi comme réel).
2. **Auth centrale + tests d'accès paramétrés** avant tout nouveau correctif, sinon les patchs resteront contournables.
3. **Rotation/reconfiguration des secrets et fermeture des ports internes** (MinIO anonyme, ml-api, AuthFlow) avant toute exposition réseau.

---

## 9. Conclusion

Le dépôt présente un **socle technique au-dessus de la moyenne** — découpage clair, outillage soigné, pipeline data/ML complet, vraie suite de tests — mais il est **dangereusement confiant** : la sécurité et la véracité des données sont traitées comme des détails d'implémentation plutôt que comme des invariants. Les cinq endpoints anonymes destructifs et les données simulées servies comme réelles ne sont pas des scories isolées : ils expriment le même parti pris de faire confiance au client. C'est réparable sans réécriture, à condition de commencer par la frontière serveur et de brancher la CI sur les zones aujourd'hui non vérifiées (`models/`, `orchestration/`, tests unitaires).

> **Note finale : 4/10 en l'état — potentiel 8/10 atteignable en 2 semaines** si (et seulement si) l'authentification devient une dépendance de routeur centrale, les données simulées sont retirées des chemins de production, et la CI exécute enfin les tests déjà écrits.
