# Mode simulation vs réel par plateforme — comparatif et design retenu

> Contexte : préparation de la preuve fonctionnelle "portefeuille réel Binance + Kraken"
> (cf. plan `testnet-portfolio-verification.md`). Réflexion menée le 2026-07-24, **avant tout
> codage** — ce document fige les constats et le design ; l'implémentation suit dans une étape
> séparée.

---

## 1. Pourquoi ce document

Le plan initial supposait "un testnet par plateforme, comme Binance". En creusant, deux constats
changent la donne :

1. **Kraken n'a pas de testnet Spot self-service.** Un compte Kraken classique (inscription
   normale) n'est **pas** un testnet — l'API testing environment Spot existe côté Kraken mais
   nécessite une qualification via contact direct avec leur équipe API, sans délai garanti.
   Seul Kraken **Futures** a un testnet public (`demo-futures.kraken.com`), hors périmètre (on
   vise le Spot).
2. **Binance n'a plus l'agrément pour servir des clients en France depuis le 30/06/2026**
   (fin de la période transitoire PSAN, cf. issue [#13](https://gitlab.com/dst_crypto/Crypto-bot-app/-/issues/13)
   déjà référencée dans `multi-exchange-layer.md`). Le testnet Binance reste techniquement
   utilisable (bac à sable de développement, pas un service à des clients réels), mais Binance
   n'est plus un choix pertinent comme référence produit long terme pour un public français.

---

## 2. Comparatif par plateforme (vérifié le 2026-07-24)

| Plateforme | Agréé MiCA / utilisable en France | Testnet Spot self-service | Ce que couvre le mode simulé |
|---|---|---|---|
| **Binance** | ❌ Perdu au 30/06/2026 | ✅ (`testnet.binance.vision`) | Faux solde **et** faux ordres, compte séparé du réel |
| **Kraken** | ✅ (PSAN historique, statut agrément à reconfirmer si on l'utilise en prod) | ❌ Pas de testnet Spot self-service | Ordres simulés uniquement (`validate=true` sur `AddOrder`) — **le solde affiché reste le vrai solde du compte réel**, il n'existe pas de faux portefeuille Kraken |
| **OKX** | ✅ CASP via Malte (MFSA), depuis janvier 2025 | ✅ Demo Trading (`okx.com/demo-trading`), fonds virtuels réapprovisionnés automatiquement | Faux solde et faux ordres, compte séparé ; carnet d'ordres non simulé fidèlement (limite mineure, sans impact démo) |
| **Bybit** | ✅ via Bybit EU | ✅ `testnet.bybit.com`, 10 000 USDT + 1 BTC virtuels sur demande | Faux solde et faux ordres, infrastructure testnet séparée (liquidité/prix peuvent différer du marché réel) |

Rappel technique important, vérifié dans le code (`utils/connectors/exchanges/ccxt_driver.py`) :
les **données de marché historiques** (bougies, utilisées pour les modèles) passent par des
endpoints publics non authentifiés, indépendants du mode simulé/réel — cette limite ne touche
que la couche exécution (`backend/src/market/clients/`), pas l'entraînement des modèles.

Vérification technique ccxt 4.5.63 (installé dans le projet) : `fetchBalance`, `fetchOHLCV`,
`fetchTickers`, `createOrder`, `cancelOrder` sont supportés nativement sur les quatre
plateformes ; seul `set_sandbox_mode` diffère (absent pour Kraken).

---

## 3. Design retenu — mode simulation/réel choisi par l'utilisateur

Plutôt qu'un flag global côté serveur (dev-only), le choix simulation/réel devient une **option
par utilisateur et par exchange**, cohérente avec le modèle multi-exchange déjà en place
(`configured_exchanges`, clés par exchange dans `UserSettings.api_keys`).

Deux mécanismes différents selon ce que la plateforme permet réellement — invisibles pour
l'utilisateur, qui ne voit qu'un choix "simulé / réel" :

- **Binance / OKX / Bybit** : deux jeux de clés API par exchange (clés testnet/demo, clés
  réelles). Le mode choisi détermine quel jeu de clés est utilisé et active
  `set_sandbox_mode(True)` côté ccxt.
- **Kraken** : un seul jeu de clés réelles. Le mode "simulé" active `validate=true` au moment de
  l'appel `create_order` — aucun ordre n'est exécuté, mais **le solde affiché reste réel**.

### Point d'attention UX (à ne pas cacher à l'utilisateur)

Le mode "simulé" n'est **pas symétrique** entre plateformes : sur Binance/OKX/Bybit, tout est
faux (solde + ordres) ; sur Kraken, seul l'ordre est faux, le solde est réel. L'interface doit
l'expliciter (ex. un texte contextuel "Kraken : solde réel, ordres simulés" à côté du sélecteur
de mode pour cet exchange), plutôt que de laisser croire à un comportement identique partout.

---

## 4. Impacts pressentis sur le modèle de données (à affiner à l'implémentation)

- `UserSettings.api_keys` devra porter, par exchange, soit deux jeux de clés (réel/testnet) soit
  un jeu de clés + un mode par défaut — modélisation exacte à trancher à l'étape de code, pas
  ici.
- `from_user_settings()` (`backend/src/market/clients/factory.py`) devra recevoir le mode choisi
  et le répercuter : sélection du jeu de clés pour Binance/OKX/Bybit, ou `params={"validate":
  True}` pour Kraken.
- Le sélecteur de mode côté frontend (page Gestion de compte) est un ajout au flux existant
  décrit dans `multi-exchange-layer.md` section 3, pas une refonte.

---

## 5. Points encore ouverts

- Ajout d'OKX et/ou Bybit au `EXCHANGE_CATALOG` (`utils/constants.py`) et au mapping `CCXT_IDS` :
  pas encore décidé si on remplace Kraken, on l'ajoute en plus, ou on garde Binance + Kraken tel
  quel pour la démo (le compte Kraken déjà créé par l'utilisatrice reste utilisable en mode
  "clés réelles + validate", aucune perte).
- Modélisation exacte du double jeu de clés par exchange dans `UserSettings` — à faire à
  l'étape de code, avec tests.
- Le doc `multi-exchange-layer.md` §4 liste encore la persistance de l'exchange sélectionné côté
  backend comme "reste à faire" — le mode simulé/réel devra probablement suivre le même
  mécanisme de persistance quand celui-ci sera fait.
