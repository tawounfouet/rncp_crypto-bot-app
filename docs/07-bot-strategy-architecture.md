# Architecture bot — ce que l'utilisateur configure vs ce qui est fixé par le modèle

Statut: proposition (décision ouverte)
Derniere revision: 2026-07-27

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

## 4bis. Mise à jour 2026-07-29 — branchement ML fait pour Random Forest

Une partie du §5 (point 2) est résolue : `StrategyTypeEnum` a une valeur
`ML_RANDOM_FOREST`, `StrategyUpdate.strategy_type` permet de la persister, et
`execute_strategy` bascule dessus vers `backend/src/inference/live_features.py::
build_live_feature_frame` + `InferenceService` local (nouvelle route
`POST /inference/predict-live`). Le moteur de règles fixes (§3) n'est pas supprimé —
toujours utilisé pour les `strategy_type` autres que `ML_RANDOM_FOREST` — la question de
sa suppression (§5, point 1) reste ouverte. LSTM reste hors périmètre (cf.
`models/src/models/lstm.py`, jamais câblé, aucune inférence écrite).

## 4ter. Mise à jour 2026-07-30 — soumission ET annulation d'ordre réelles (Phase 3, élargie)

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

## 4quater. Mise à jour 2026-07-30 — déclenchement périodique (Phase 4)

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

## 5. Points ouverts à trancher avant de coder

- Supprimer ou geler `backend/src/strategy/engine/` (règles fixes) — vérifier les tests qui en
  dépendent avant de décider.
- ~~Où et comment brancher `inference/service.py` (ML) dans
  `strategy/service.py::execute_strategy`~~ — fait le 2026-07-29 pour Random Forest, cf.
  §4bis. Reste ouvert pour un futur modèle LSTM (branchement `ML_LSTM` séparé, prévu comme
  chantier futur).
- Modélisation exacte du "modèle ML disponible pour cet exchange" (dépend du registre
  scopé-par-exchange, point ouvert de `06-testnet-simulation-modes.md`).
- Portée réaliste vs calendrier (fin août) : ce document décrit la cible sans contrainte de
  délai, à la demande explicite de l'utilisatrice le 2026-07-24 — réduction de portée à faire
  séparément avant de lancer le code.
