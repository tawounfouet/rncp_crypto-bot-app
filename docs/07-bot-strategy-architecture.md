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
5. **Active le bot** — **le plus gros trou identifié** : `backend/src/trading/service.py`
   contient des `TODO` non résolus sur l'essentiel (soumission d'ordre réelle, annulation,
   P&L, suivi de position) et `strategy/service.py::execute_strategy` n'est branché à aucun
   modèle ML aujourd'hui (seulement au moteur de règles fixes, cf. §3).

## 5. Points ouverts à trancher avant de coder

- Supprimer ou geler `backend/src/strategy/engine/` (règles fixes) — vérifier les tests qui en
  dépendent avant de décider.
- Où et comment brancher `inference/service.py` (ML) dans `strategy/service.py::execute_strategy`
  pour que "activer un bot" utilise réellement un modèle ML, pas une règle fixe.
- Modélisation exacte du "modèle ML disponible pour cet exchange" (dépend du registre
  scopé-par-exchange, point ouvert de `06-testnet-simulation-modes.md`).
- Portée réaliste vs calendrier (fin août) : ce document décrit la cible sans contrainte de
  délai, à la demande explicite de l'utilisatrice le 2026-07-24 — réduction de portée à faire
  séparément avant de lancer le code.
