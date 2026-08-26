# Liste Des Scenarios Mockes

Statut: référence
Derniere revision: 2026-07-28

## Scenarios globaux disponibles

Branches dans `mocks/factories.py` (pilotent reellement les donnees mockees affichees) :
- `utilisateur_normal`: base stable pour utilisateur standard.
- `exchange_non_configure`: statut exchange KO + message explicite (id reel : `exchange_non_configure`, pas `binance_non_configure`).
- `portefeuille_vide`: pas d'actifs, pas d'ordres, etats empty.
- `portefeuille_riche`: portefeuille diversifie avec exposition elevee.
- `performances_fortes`: equity curve haussiere, ROI positif.
- `performances_degradees`: equity degradee, drawdown plus marque.

Definis dans l'enum `MockScenario` mais **non branches** dans `mocks/factories.py` — les selectionner dans la sidebar n'a aucun effet visible sur les donnees affichees :
- `admin`: l'acces a la page Admin depend en pratique du role du compte connecte, pas de ce scenario.
- `bot_en_erreur`: aucun bot n'est force en statut `ERROR`.
- `bot_en_execution`: aucun bot n'est force en statut `RUNNING`.

## Comptes mockes
- `alice@cryptobot.dev / Passw0rd!` (role USER)
- `admin@cryptobot.dev / Admin123!` (role ADMIN)

## Simulations supportees
- Delais mockes par service (desactivables pour les tests).
- Erreurs forcees par cle service via `store.force_errors`.
- Reponses success/error coherentes pour toutes les actions UI.
