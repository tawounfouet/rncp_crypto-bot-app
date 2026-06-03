# Liste Des Scenarios Mockes

## Scenarios globaux disponibles
- `utilisateur_normal`: base stable pour utilisateur standard.
- `admin`: contexte admin (a coupler avec login admin pour acces page Admin).
- `binance_non_configure`: statut Binance KO + message explicite.
- `portefeuille_vide`: pas d'actifs, pas d'ordres, etats empty.
- `portefeuille_riche`: portefeuille diversifie avec exposition elevee.
- `bot_en_erreur`: au moins un bot passe en statut `ERROR`.
- `bot_en_execution`: bots forces en statut `RUNNING` (hors cas erreur).
- `performances_fortes`: equity curve haussiere, ROI positif.
- `performances_degradees`: equity degradee, drawdown plus marque.

## Comptes mockes
- `alice@cryptobot.dev / Passw0rd!` (role USER)
- `admin@cryptobot.dev / Admin123!` (role ADMIN)

## Simulations supportees
- Delais mockes par service (desactivables pour les tests).
- Erreurs forcees par cle service via `store.force_errors`.
- Reponses success/error coherentes pour toutes les actions UI.
