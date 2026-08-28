# Architecture bot — ce que l'utilisateur configure vs ce qui est fixé par le modèle

Statut: décision actée, en cours d'implémentation
Derniere revision: 2026-08-28

> Réflexion menée le 2026-07-24, **avant tout codage**. Décide comment un "bot" combine
> plateforme, mode simulé/réel, modèle ML et paramètres de risque. Complète
> `06-testnet-simulation-modes.md` (qui traite exchange/mode simulé) sur le volet stratégie/ML.

---

## 1. Pourquoi le ML est obligatoire (pas juste une option)

`crypto-bot-infra/docs/GESTION_PROJET.md:39` liste un **"Composant IA / ML (C12)"** comme bloc
de compétence explicite du référentiel RNCP visé — donc évalué à la soutenance, pas optionnel.
**Décision** : le choix de stratégie exposé à l'utilisateur doit être un choix de **modèle ML
entraîné** (ex: `random_forest`, `lstm`), pas de règle technique fixe.

## 2. Séparation des responsabilités

Principe retenu : l'utilisateur ne règle **jamais** les paramètres internes d'un modèle
(fenêtre RSI, hyperparamètres d'entraînement...) — seulement des **paramètres de risque et
d'exécution**, dont l'effet est compréhensible et borné sans culture ML/finance.

| Réglé par l'utilisateur (par bot) | Fixé par l'équipe (par modèle, pas par bot) |
|---|---|
| Plateforme (exchange) | Fenêtre RSI, paramètres MACD/Bollinger (features) |
| Mode simulé / réel (cf. `06-testnet-simulation-modes.md`) | Hyperparamètres d'entraînement (`n_estimators`, `hidden_size`, ...) |
| Paire tradée | Quel modèle existe pour quel exchange (dépend des données dispo) |
| Stratégie = **quel modèle ML utiliser** (liste des modèles entraînés disponibles) | Le contenu même du modèle (poids/arbres appris) |
| Stop-loss, take-profit, budget, risque par trade, cooldown, max positions ouvertes | — |

**Pourquoi séparer ainsi** : un stop-loss mal réglé a un effet compréhensible (perte max
acceptée) même sans culture finance ; changer la fenêtre RSI d'un modèle déjà entraîné peut
casser silencieusement sa performance, sans que l'utilisateur puisse le mesurer.

## 3. Conséquence sur le code existant — duplication à résoudre

Deux implémentations séparées des mêmes indicateurs techniques (RSI, MACD, Bollinger) existent
aujourd'hui, pour deux usages différents :

- `backend/src/strategy/engine/implementations/` (`rsi_reversal.py`, `bollinger_bands.py`,
  `moving_average_crossover.py`, `multi_indicator.py`) — moteur de **règles fixes**, exposé
  comme "stratégie" sélectionnable dans `frontend/src/pages/06_Parametrage_Bot_Spot.py`
  aujourd'hui (avec des noms d'ailleurs déjà décorrélés du backend réel — cf. constat du
  2026-07-24).
- `models/src/features/build.py` (+ module `indicators`) — mêmes calculs, mais utilisés
  uniquement comme **features d'entrée** pour le ML (`models/`), jamais comme décision finale.

**Avec la décision "stratégie utilisateur = choix de modèle ML"**, le premier moteur
(`backend/src/strategy/engine/`) n'a plus de rôle produit : personne ne le sélectionnerait
puisqu'il n'est pas exposé. Point ouvert : le supprimer, ou le garder en dormant (tests
existants à vérifier avant suppression, cf. §5) ?

## 4. Parcours utilisateur cible (mis à jour, réflexion 2026-07-24)

1. **Ouvre l'appli** — existe (`app.py`, page de connexion).
2. **Sans clé configurée → voit les données de marché publiques** — à construire (le driver
   public existe côté backend, aucune page frontend ne l'affiche aujourd'hui hors connexion).
3. **Avec clé(s) → liste de ses portefeuilles, un seul actif à la fois** — partiellement
   existant (`configured_exchanges`, sélecteur d'exchange en session) ; manque : présentation
   "liste" au lieu de sélecteur simple, et le mode simulé/réel par plateforme (cf.
   `06-testnet-simulation-modes.md`).
4. **Configure un bot** : plateforme + mode simulé/réel + **modèle ML disponible pour cette
   plateforme** + paramètres de risque (stop-loss, take-profit, budget, risque par trade,
   cooldown). Existant partiellement : `StrategyDeployment` (exchange/paire/paramètres JSON),
   page `06_Parametrage_Bot_Spot.py` (champs de risque déjà présents). Manquant : le sélecteur
   de modèle ML lui-même (n'existe pas), et la liste de modèles doit être filtrée par
   plateforme (cf. gap "registre de modèles pas scopé par exchange", déjà documenté dans
   `06-testnet-simulation-modes.md` §4).
5. **Active le bot** — `backend/src/trading/service.py::create_order`/`cancel_order`
   soumettent et annulent maintenant réellement les ordres sur l'exchange (cf. mise à jour
   2026-07-30 ci-dessous) ; il reste des `TODO` non résolus sur le suivi de statut temps
   réel et le P&L. `strategy/service.py::execute_strategy` est branché sur un modèle ML
   (`ML_RANDOM_FOREST`, cf. mise à jour 2026-07-29) — le moteur de règles fixes (§3) reste
   utilisé pour les autres `strategy_type`.

## 4.1. Mise à jour 2026-07-29 — branchement ML fait pour Random Forest

Une partie du §5 (point 2) est résolue : `StrategyTypeEnum` a une valeur
`ML_RANDOM_FOREST`, `StrategyUpdate.strategy_type` permet de la persister, et
`execute_strategy` bascule dessus vers `backend/src/inference/live_features.py::
build_live_feature_frame` + `InferenceService` local (nouvelle route
`POST /inference/predict-live`). Le moteur de règles fixes (§3) n'est pas supprimé —
toujours utilisé pour les `strategy_type` autres que `ML_RANDOM_FOREST` — la question de
sa suppression (§5, point 1) reste ouverte. LSTM reste hors périmètre (cf.
`models/src/models/lstm.py`, jamais câblé, aucune inférence écrite).

## 4.2. Mise à jour 2026-07-30 — soumission ET annulation d'ordre réelles (Phase 3, élargie)

Le point d'arrêt mentionné ci-dessus est levé : `TradingService.create_order` appelle
maintenant `from_user_settings` + `client.place_order` (même pattern que
`get_user_portfolio`) après la création de la ligne `Order`, avec un adaptateur manuel
`OrderResult` → `Order` (pas de réutilisation de `update_from_exchange_response`, qui
attend un dict brut Binance, cf. §"Découvertes clés" du plan). En cas d'échec (clés
absentes/invalides, erreur exchange) : statut `"REJECTED"` persisté, pas de crash de
l'endpoint. Couvert par 4 tests unitaires (`test_trading_service_create_order.py`) qui
mockent `from_user_settings`/`client.place_order` — jamais d'appel réel dans les tests.

Phase 3 a été élargie en cours de route (décision du 2026-07-30) : avant de soumettre des
ordres réels, il fallait aussi pouvoir les annuler et en suivre le statut. Seule
l'annulation a été retenue pour cette phase — `cancel_order` appelle maintenant
`client.cancel_order(order.symbol, order.exchange_order_id)` (`order.exchange` sert
directement de cible, pas besoin de recharger le `StrategyDeployment`). Différence de
sémantique volontaire avec `create_order` : un échec (clés absentes/invalides, erreur
exchange) lève une `BusinessLogicError` plutôt que de marquer l'ordre `"REJECTED"` —
l'ordre reste ouvert sur l'exchange, l'appelant doit pouvoir réessayer, pas de faux statut
silencieux. Couvert par 4 tests unitaires (`test_trading_service_cancel_order.py`), même
principe de mocks. Le suivi de statut temps réel (`get_order_status_from_exchange`) reste
hors périmètre : `ExchangeClient` n'a aucune méthode pour interroger un ordre existant
côté exchange, ça demanderait d'étendre le contrat et ses 2 implémentations
(`binance_native.py`, `ccxt_client.py`) — chantier séparé, pas juste un branchement.

"Activer un bot" ML_RANDOM_FOREST va donc désormais jusqu'à la soumission et l'annulation
réelles d'un ordre testnet, mais rien ne déclenche encore ce cycle périodiquement
(Phase 4, Airflow) ni depuis le frontend (Phase 5).

## 4.3. Mise à jour 2026-07-30 — déclenchement périodique (Phase 4)

`StrategyService.execute_active_deployments()` boucle sur tous les `StrategyDeployment`
`status="active"` (tous utilisateurs confondus). Pour chacun : garde cooldown
(`strategy.parameters.get("cooldown_seconds", 300)` comparé à `state.last_signal_time`),
garde position (`state.position not in (None, "NEUTRAL")` — décision retenue : le
périmètre de `max_open_positions` est **par deployment**, pas par utilisateur, faute de
spec existante sur le sujet — non documenté, personne dans l'historique git n'a précisé
cette intention). Si aucune garde ne bloque : appelle `execute_strategy(deployment.id)`,
et si le signal n'est pas HOLD, calcule `quantity = deployment.amount / prix_courant`
(`deployment.amount` est en devise de cotation, `create_order` attend une quantité en
actif de base) puis appelle `TradingService.create_order`. Nouvel endpoint
`POST /strategies/deployments/execute-active`, **sans authentification** (même principe
que `/inference/predict-live` — appelé par Airflow, pas par un utilisateur). Nouveau DAG
`orchestration/dags/bot_execution.py`, planifié horaire (`0 * * * *`), même principe que
`ml_pipeline.py` (un appel HTTP, pas de logique métier côté Airflow).

Corrige au passage un bug préexistant (antérieur à ce chantier) dans `execute_strategy` :
`state.last_execution` n'était pas une colonne réelle de `StrategyState` (le vrai champ
est `last_signal_time`) — la mise à jour ne persistait donc jamais, ce qui aurait rendu la
garde cooldown de la Phase 4 inopérante. Corrige aussi un second bug lié : `state.last_signal`
(colonne `String(10)`) recevait le code numérique du signal (1/-1/0) au lieu du label
(`"BUY"/"SELL"/"HOLD"`) — extrait dans `utils/trading/signals.py`
(`SIGNAL_TO_VALUE`/`VALUE_TO_SIGNAL`), partagé avec `inference/service.py` et
`models/src/backtesting/engine.py` (qui avaient chacun leur propre mapping dupliqué,
dans des composants qui ne peuvent pas s'importer entre eux — `models/` n'est pas copié
dans l'image backend, même raison que le déplacement des indicateurs vers `utils/` en
Phase 0).

4 tests unitaires sur `execute_active_deployments` (gardes + soumission d'ordre, mocks
uniquement), 19 tests sur `strategy/router.py` (toutes les routes, dont `execute-active`
sans auth — jusque-là aucune route de ce fichier n'avait de test au niveau routeur).
Vérification manuelle du DAG (`airflow tasks test`) pas encore faite au moment de ce
commit — reportée, RAM insuffisante sur la machine de dev au moment d'écrire ce chantier
(cf. `project_k3s_vm_idea` en mémoire).

## 4.4. Mise à jour 2026-07-30 — route passthrough `available-models` (Phase 5, backend)

Nouvel endpoint `GET /strategies/available-models`, **authentifié** (contrairement à
`execute-active` : celui-ci est appelé par le frontend pour un utilisateur connecté, pas
par Airflow). `StrategyService.get_available_models()` relaie en HTTP synchrone
(`requests.get`, `ML_API_URL` en variable d'env, défaut `http://crypto-bot-ml-api:8010`,
timeout 30s) la route `GET /models` de ml-api, qui renvoie une liste fixe des deux modèles
connus (`random_forest`, `lstm`) avec `available` = existence du répertoire registry
correspondant. C'est le premier appel HTTP interne backend → ml-api (jusque-là, seul
Airflow appelait ml-api en HTTP ; le backend n'utilisait que l'inférence en process via
`InferenceService`). Nouveau schéma `ModelInfo` (`strategy/schemas.py`), miroir du schéma
ml-api du même nom.

Piège rencontré et corrigé : la route avait été déclarée après `GET /{strategy_id}` dans
`router.py` — FastAPI matche les routes dans l'ordre de déclaration, donc
`/available-models` était interceptée par la route à paramètre de chemin
(`strategy_id="available-models"`) et ne s'exécutait jamais en pratique. Remontée juste
après `/available`, qui avait déjà ce problème résolu pour la même raison.

Au passage : fixtures de test `strategy_service` (`_make_user`/`_make_ml_deployment`/
`_make_state`, dupliquées entre plusieurs fichiers de test) factorisées en fixtures
partagées (`make_user`/`make_deployment`/`make_state`) dans `backend/tests/conftest.py`,
réutilisées aussi par les tests `trading_service`. `test_strategy_service_execute.py` et
`test_strategy_service_execute_active.py` fusionnés en un seul `test_strategy_service.py`.
Corrige aussi, à cette occasion, un bug latent dans la garde cooldown de la Phase 4
(`execute_active_deployments`) : `state.last_signal_time` relu depuis SQLite perd son
`tzinfo` (colonne `DateTime` sans `timezone=True`), ce qui faisait planter la comparaison
avec `datetime.now(UTC)` (aware) dès qu'un test insérait un datetime timezone-aware — la
garde traite maintenant explicitement le cas `tzinfo is None` en le réinterprétant en UTC.

2 tests service (`get_available_models`, succès + erreur ml-api) + 2 tests routeur (200 +
502) + tests complets sur toutes les méthodes de `BackendApiClient` côté frontend
(26 tests, dont les 2 nouvelles : `get_available_models`, `deploy_strategy`).

## 4.5. Mise à jour 2026-07-30 — sélecteur de modèle + création de bot (Phase 5, frontend)

`06_Parametrage_Bot_Spot.py` : le sélecteur "Strategie" (jusque-là une liste en dur jamais
réellement envoyée au backend, cf. §4) est remplacé par un sélecteur peuplé via
`GET /strategies/available-models`, filtré sur `available=True`. `BotConfigService.save()`
envoie désormais `strategy_type` au niveau racine du payload d'update (auparavant absent :
modifier la "stratégie" dans ce formulaire n'avait jamais eu d'effet réel).

Ajout, dans un `st.expander` toujours visible (ouvert par défaut si aucun bot n'existe,
replié sinon) : un formulaire minimal de création de bot (nom + modèle), gap identifié
pendant cette session — aucune page frontend ne permettait de créer une `Strategy`
(= "bot" côté vocabulaire produit), ce qui bloquait totalement le test de cette page sans
passer par un appel API manuel.

**Décision d'architecture actée à cette occasion** (clarifiait une question restée ouverte
depuis le 2026-07-24, cf. [[project_bot_ml_architecture_reflection]] en mémoire) :
`strategy/engine/` (registre + implémentations de règles techniques —
`moving_average_crossover`/`rsi_reversal`/`bollinger_bands`/`multi_indicator`) est
**archivé, pas supprimé** : code backend conservé tel quel pour un usage futur éventuel,
mais plus aucun chemin produit ne doit pouvoir le solliciter — seuls les modèles ML
entraînés (`ml_random_forest`, futur `ml_lstm`) sont sélectionnables par l'utilisateur.
Raison non technique : le référentiel RNCP de la formation exige un bloc de compétence
ML (C12) évalué à la soutenance — exposer aussi des stratégies à règles diluerait le fait
que le choix de stratégie *est* un choix de modèle entraîné.

Bug découvert en conséquence directe de ce flou : `StrategyService.create_strategy()` et
`update_strategy()` validaient `strategy_type` contre `registry.list_strategies()` (le
registre technique, qui n'a jamais connu le ML) — `POST /strategies/` avec
`strategy_type="ml_random_forest"` échouait donc systématiquement en 400. Corrigé par un
bypass explicite (`if not strategy_type.startswith("ml_")`) dans les deux méthodes ; le
registre technique reste fonctionnel tel quel si jamais réactivé plus tard, mais n'est plus
consulté pour les types ML. `StrategyTypeEnum` garde ses valeurs techniques inchangées
(archivage, pas suppression) ; `GET /strategies/available` (liste ces stratégies
techniques) n'est déjà appelé par aucune page frontend.

Tests ajoutés : 5 tests `BotConfigService` (`get_available_models`, `create_bot`, propagation
de `strategy_type` dans `save()`) ; mock smoke-test (`frontend/tests/smoke/conftest.py`)
corrigé pour distinguer `/strategies/available-models` du catch-all `/strategies` (qui
renvoyait par erreur les strategies stub, sans clé `available`, faisant planter la page en
mode smoke-test).

## 4.6. Mise à jour 2026-07-30 — formulaire Start + nettoyage duplication frontend (Phase 5)

`05_Controle_Bot_Spot.py` + `BotControlService.deploy()` : le bouton "Start" (jusque-là un
placeholder renvoyant "utilisez l'API") ouvre désormais un formulaire inline (exchange via
`EXCHANGE_CATALOG`, symbole, timeframe fixé `1h` pour le MVP, montant) qui appelle
`deploy_strategy`. Bouton désactivé si le bot a déjà un deployment actif
(`bot.status != STOPPED`).

Bug découvert pendant la vérif manuelle : cliquer sur "Pause" (non supporté par le backend)
n'affichait aucun message d'erreur visible. Cause : le pattern `show_feedback(...)` suivi
d'un `st.rerun()` **inconditionnel** — le rerun relance le script avant que le message
rendu n'ait pu s'afficher côté navigateur. Corrigé dans les 3 endroits concernés de ce
fichier (Pause, confirmation Stop, confirmation Start) : le rerun ne se déclenche plus
qu'en cas de succès. Les autres pages (`06_Parametrage_Bot_Spot.py`, `07_Gestion_de_compte.py`,
`08_Admin.py`) suivaient déjà le bon pattern — bug isolé à ce fichier.

Deuxième bug de la même famille que celui de la Phase 4 (§4.3), trouvé en testant Start en
conditions réelles : `_heartbeat_label()` plantait sur `datetime.now(UTC) - heartbeat_at`
quand `heartbeat_at` (parsé depuis `updated_at` renvoyé par le backend) était naïf. En
creusant, cette fonction de parsing de date (`_parse_dt`) était **dupliquée à l'identique
dans 6 fichiers** (`bot_control_service.py`, `bot_config_service.py`, `admin_service.py`,
`market_service.py`, `portfolio_service.py`, `performance_service.py`) — toutes les 6
partageaient donc le même bug latent. Centralisées dans `frontend/src/utils/dates.py` :
`parse_dt(value) -> datetime | None` (normalise en UTC si `tzinfo is None`, préserve `None`
si absent/invalide) et `parse_dt_or_now(value) -> datetime` (fallback `datetime.now(UTC)`).
`admin_service.py` utilise `parse_dt` directement (a besoin de préserver `None` : un
utilisateur peut ne jamais s'être connecté) ; les 5 autres utilisent `parse_dt_or_now`.

En vérifiant l'étendue de cette duplication, deux autres helpers dans le même cas ont été
trouvés et centralisés à leur tour : `_float`/`_int` (conversion tolérante, dupliqués dans
4 fichiers) → `frontend/src/utils/numeric.py` (`to_float`, `to_int`) ; `_extract_error`
(lecture du message d'erreur d'une `ApiResponse`, dupliqué dans 3 fichiers) →
`frontend/src/utils/api_errors.py` (`extract_error`). La variante plus riche
`_extract_error_message` d'`auth_service.py` (gère aussi `message`/`details`, pas un doublon
strict) n'a pas été touchée.

Tests ajoutés : 2 `BotControlService.deploy` (succès, erreur backend). Vérification manuelle
complète du parcours Phase 5 : bot créé, configuré (modèle + paramètres de risque), démarré
(deployment actif créé), cycle Airflow `cryptobot_bot_execution` déclenché manuellement —
signal `HOLD` retourné par le modèle (aucun ordre soumis, comportement normal, pas un bug :
`execute_active_deployments` ne soumet un ordre que si le signal n'est pas HOLD).

## 4.7. Mise à jour 2026-08-26 — remplacement du flux `strategy/` par le module `bots/` (import `dev_ben` + adaptation multi-exchange)

Merge de `dev_ben` (module `backend/src/bots/` : catalogue de bots pré-configurés
verrouillés + panel admin de gestion des utilisateurs), avec adaptation du moteur
d'exécution des bots : la version d'origine était câblée de bout en bout sur un
"Binance Testnet lab" isolé (credentials dédiées, appels REST signés maison vers
`testnet.binance.vision`) — hors de l'architecture multi-exchange déjà en place
(`market/clients/`, issue #13). Adaptée pour router via cette couche existante :

- `market/clients/base.py`/`ccxt_client.py` : `place_order()` accepte maintenant un
  `quote_quantity` (achat MARKET par montant en devise de cotation, ex. "dépenser 100
  USDC de BTC" — ccxt `create_market_buy_order_with_cost`), en plus de `quantity` (actif
  de base). Nouveau `get_open_orders()`.
- `bots/execution.py` (nouveau) : passerelle `MultiExchangeBotGateway`, même interface
  que l'ancien service Testnet (klines/ticker/symbol_info/open_orders/balances/place_order)
  mais backée par `market.clients.factory.from_user_settings` (exécution réelle, respecte
  le mode actif live/sandbox de l'utilisateur) et `utils.connectors.exchanges.registry`
  (données de marché publiques). Le gate de credentials avant démarrage d'un bot utilise
  désormais le système multi-credential existant (`UserSettings.has_credentials_for_exchange`)
  au lieu d'un modèle `UserExchangeCredential` dédié au Testnet lab (abandonné à cette
  occasion, cf. non-scope ci-dessous). Le concept de credentials "vérifiées"
  (`permissions_checked`) n'existe plus : avoir des clés configurées suffit désormais,
  comme pour le reste de l'application.
- Réponse de `place_order()` reconstituée en un seul "fill" synthétique (`executedQty`/
  `cummulativeQuoteQty`) car `OrderResult` (contrat multi-exchange) ne porte pas le détail
  des fills/commission individuels que renvoyait l'API Binance brute — simplification
  assumée, pas encore vérifiée en conditions réelles (cf. §6 tests).

**Hors scope de cet import** (fichiers présents dans le code, mais non branchés dans
`main.py`/`navigation/rules.py`) : le "Binance Testnet lab" lui-même
(`market/binance_testnet_service.py`, `binance_testnet_router.py`,
`frontend/src/pages/09_Binance_Testnet_Lab.py`, service frontend associé) — feature
distincte de `dev_ben`, indépendante du catalogue de bots, jamais activée.

### Conséquence directe : deux systèmes d'exécution de bots coexistent maintenant

Ce document (§4.2 à §4.6) décrit un premier système, basé sur `StrategyDeployment` /
`StrategyService.execute_active_deployments()`, déclenché par le DAG Airflow
`orchestration/dags/bot_execution.py` (horaire). Il n'a **pas été supprimé** par ce merge
et est resté fonctionnel tel quel côté backend (`strategy/`), mais n'était plus atteignable
depuis le frontend : `06_Parametrage_Bot_Spot.py`/`05_Controle_Bot_Spot.py` et les
services associés (`bot_config_service.py`, `bot_control_service.py`) ont été
**entièrement remplacés** par le nouveau flux `bots/` (catalogue verrouillé, plus de
formulaire de paramétrage libre — cf. §2, la décision "l'utilisateur ne paramètre pas le
bot après sélection" est donc désormais appliquée strictement).

**Mise à jour 2026-08-28** : le point ouvert ci-dessous est tranché. `orchestration/dags/
bot_execution.py` est supprimé (plus aucune page ne crée de `StrategyDeployment` depuis le
26/08, ce DAG tournait dans le vide) — décommissionné à l'occasion d'un bug qui lui était
initialement attribué à tort (un 500 sur `POST /strategies/deployments/execute-active`,
en réalité sans rapport avec le module `bots/` alors en cours de travail). Le module backend
`strategy/` lui-même (`StrategyDeployment`, `execute_active_deployments`, l'endpoint) n'est
**pas supprimé** — même logique que l'archivage de `strategy/engine/` (§4.5) : gelé, pas
détruit, au cas où il servirait plus tard.

Le second système (`bots/worker.py`, tâche asyncio interne démarrée par `main.py` au
lancement de l'API si `ENABLE_BACKGROUND_TASKS`, toutes les `BOT_WORKER_INTERVAL_SECONDS`
= 60s par défaut) exécute les `UserBotInstance` actifs — mécanisme séparé, pas orchestré
par Airflow.

**Tranché le 2026-08-28** (cf. mise à jour ci-dessus) : le DAG Airflow est décommissionné
(fichier supprimé), le module backend `strategy/` reste en dormant.

### 6. Tests — trous critiques identifiés à cette occasion

- `bots/worker.py` : **0% de couverture** — c'est pourtant le code qui exécute réellement
  les bots en continu en production (boucle asyncio démarrée au boot de l'API).
- `bots/execution.py` (l'adaptation multi-exchange ci-dessus) : 47% — la gestion du
  `quote_quantity` et le repli synthétique des fills ne sont pas exercés par les tests
  d'intégration existants (`test_bot_service.py` utilise un fake gateway, pas le vrai
  `MultiExchangeBotGateway`).
- `bots/ml_client.py` : 38% — l'appel HTTP réel vers `crypto-bot-ml-api` peu couvert.
- Frontend : `05_Controle_Bot_Spot.py` (48%), `admin_service.py` (51%),
  `bot_config_service.py` (58%).

## 5. Points ouverts à trancher avant de coder

- Supprimer ou geler `backend/src/strategy/engine/` (règles fixes) — vérifier les tests qui en
  dépendent avant de décider.
- ~~Où et comment brancher `inference/service.py` (ML) dans
  `strategy/service.py::execute_strategy`~~ — fait le 2026-07-29 pour Random Forest, cf.
  §4.1. Reste ouvert pour un futur modèle LSTM (branchement `ML_LSTM` séparé, prévu comme
  chantier futur).
- Modélisation exacte du "modèle ML disponible pour cet exchange" (dépend du registre
  scopé-par-exchange, point ouvert de `06-testnet-simulation-modes.md`).
- Portée réaliste vs calendrier (fin août) : ce document décrit la cible sans contrainte de
  délai, à la demande explicite de l'utilisatrice le 2026-07-24 — réduction de portée à faire
  séparément avant de lancer le code.
