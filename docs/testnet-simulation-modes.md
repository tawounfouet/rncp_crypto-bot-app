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

## 4. Modélisation retenue (décidée le 2026-07-27) — double jeu de clés par exchange

Décision : **option "deux jeux de clés en parallèle"**, pas un jeu unique avec re-saisie à
chaque bascule. L'utilisateur configure une fois les clés réelles et/ou simulation par
exchange, puis bascule sans ressaisir.

### 4.1 Modèle de données — `UserSettings.api_keys`

Aujourd'hui (`backend/src/auth/models.py:202-253`) : `api_keys` est un JSON
`{exchange: {"api_key": <chiffré>, "api_secret": <chiffré>}}`, un seul jeu par exchange.

Nouvelle forme :
```json
{
  "binance": {
    "live":         {"api_key": "<chiffré>", "api_secret": "<chiffré>"},
    "sandbox":       {"api_key": "<chiffré>", "api_secret": "<chiffré>"},
    "active_mode":  "sandbox"
  },
  "kraken": {
    "live":         {"api_key": "<chiffré>", "api_secret": "<chiffré>"},
    "active_mode":  "sandbox"
  }
}
```

Asymétrie assumée (cohérente avec §2/§3) : Kraken n'a jamais de clé `"sandbox"` distincte (pas
de testnet Spot) — `active_mode` y bascule uniquement le comportement au moment de l'ordre
(`validate=true`), pas le jeu de clés utilisé. Binance/OKX/Bybit ont potentiellement les deux
clés, et `active_mode` sélectionne laquelle utiliser + active `set_sandbox_mode(True)`.

Méthodes à faire évoluer sur `UserSettings` (`models.py`) :
- `set_api_credentials(exchange, api_key, api_secret, mode)` — écrit dans `api_keys[exchange][mode]`
  au lieu d'écraser tout l'exchange.
- `get_api_key(exchange, mode=None)` / `get_api_secret(exchange, mode=None)` — lisent le mode
  demandé, ou `active_mode` si `mode` omis.
- Nouveau : `set_active_mode(exchange, mode)` — bascule sans toucher aux clés (condition : le
  mode ciblé doit déjà avoir des clés, sauf pour Kraken où `"sandbox"` n'a pas besoin de clés
  propres).
- Nouveau : `has_sandbox_credentials(exchange) -> bool` distinct de `has_live_credentials` —
  pour piloter l'affichage du formulaire (cf. 4.3).

### 4.2 Contrat API

- `PUT /users/me/settings` : accepte en plus `mode: "live" | "sandbox"`. Si `api_key`/`api_secret`
  fournis → écrit dans ce slot (et l'active). Si seul `mode` fourni (sans clés) → bascule
  `active_mode` sur un slot déjà configuré, sans re-saisie.
- `GET /users/me/settings` : `configured_exchanges` reste (exchange présent si au moins un mode a
  des clés), mais ajoute un détail par exchange, ex. :
  ```json
  "exchange_credentials": {
    "binance": {"live": true, "sandbox": true, "active_mode": "sandbox"},
    "kraken":  {"live": true, "sandbox": false, "active_mode": "sandbox"}
  }
  ```
- Nouveau champ sur `GET /market/exchanges` (déjà utilisé par la page Marché, réutilisable ici) :
  `supports_sandbox_credentials: bool` par exchange — dérivé de `ccxt.<id>().urls.get("test")
  is not None` (déjà vérifié le 2026-07-24 : vrai pour binance/okx/bybit, faux pour kraken).
  Pilote l'affichage du formulaire (4.3) sans dupliquer la logique côté frontend.

### 4.3 Câblage couche exécution (le "reste à faire" du plan initial, étape reportée depuis le
2026-07-24)

- `CcxtClient.__init__` : nouveau paramètre `sandbox: bool = False` → si vrai et supporté,
  `self._client.set_sandbox_mode(True)` juste après construction.
- `CcxtClient.place_order` : si le mode actif est `sandbox` **et** l'exchange ne supporte pas
  `set_sandbox_mode` (cas Kraken) → merger `params={"validate": True}` dans l'appel
  `create_order` de ccxt, plutôt que d'activer le sandbox mode (impossible).
- `registry.get_exchange_client(exchange, api_key, api_secret, sandbox=False)` : transmet le flag
  à `CcxtClient`.
- `factory.from_user_settings(settings, exchange)` : lit `active_mode`, résout le bon jeu de
  clés (`get_api_key(exchange, mode=active_mode)`), calcule `sandbox=(active_mode == "sandbox")`,
  transmet à `get_exchange_client`.

### 4.4 Frontend — page Gestion de compte

Formulaire actuel : un jeu de champs clé/secret par exchange sélectionné
(`ExchangeCredentialInput` dans `frontend/src/schemas/account.py:16-19` — à étendre avec `mode`).

Deux présentations selon `supports_sandbox_credentials` (récupéré via `/market/exchanges`) :
- **Vrai** (Binance/OKX/Bybit) : deux blocs de formulaire ("Clés réelles" / "Clés simulation"),
  chacun avec son propre bouton d'enregistrement, + un sélecteur "Mode actif" activable dès
  qu'au moins un des deux blocs a des clés enregistrées.
- **Faux** (Kraken) : un seul bloc de formulaire (clés réelles uniquement) + un texte explicite
  "Kraken n'a pas de testnet : en mode simulation, le solde affiché reste réel, seuls les ordres
  sont simulés (jamais exécutés)" + un sélecteur "Mode actif" à deux options malgré l'absence de
  second jeu de clés.

Le sélecteur de mode actif à afficher aussi sur la liste de portefeuilles déjà codée
(`03_Portefeuille_Spot.py`, `_render_portfolio_list`) — chaque carte devrait indiquer le mode
actif de l'exchange qu'elle représente, pas seulement son nom.

---

## 4.5 Backend implémenté et vérifié (2026-07-27)

Les 4 sous-parties de §4 sont codées et testées (113 tests backend, dont ceux dédiés à cette
fonctionnalité) :
- Modèle (`auth/models.py`) : double slot `live`/`sandbox` + `active_mode`, rétro-compatible
  avec l'ancien format à plat.
- Contrat API (`auth/schemas.py`, `auth/user_service.py`) : `mode` sur `PUT /users/me/settings`,
  `exchange_credentials` sur `GET /users/me/settings` + export, `supports_sandbox` sur
  `GET /market/exchanges`.
- Câblage (`market/clients/ccxt_client.py`, `registry.py`, `factory.py`) : `sandbox=True` active
  `set_sandbox_mode` si l'exchange a une vraie URL testnet, sinon `validate=true` à l'ordre.
  Kraken en mode sandbox retombe automatiquement sur les clés `live` (jamais de clés sandbox
  dédiées).

**Deux bugs réels trouvés en vérifiant avec le vrai ccxt (pas seulement les mocks)** :
1. **Persistance silencieuse cassée** : `UserSettings.api_keys` (colonne JSON simple, pas
   `MutableDict`) ne détectait pas les mutations en place sur un objet rechargé depuis la base
   — un deuxième exchange enregistré dans une session différente disparaissait silencieusement.
   Corrigé avec `flag_modified()`, reproduit et vérifié avec deux sessions SQLAlchemy séparées.
   **Existait avant ce chantier**, indépendant du mode simulé/réel.
2. **`"test" in urls` insuffisant** : `ccxt.kraken().urls` contient la clé `"test"` mais avec la
   valeur `None` — un test de présence de clé déclenchait `set_sandbox_mode()` qui plantait.
   Il faut `urls.get("test") is not None`. Trouvé uniquement parce qu'un test manuel contre le
   vrai ccxt a été fait en plus des tests mockés.

Reste à faire (frontend, pas commencé) : formulaire Gestion de compte (§4.4), affichage du mode
actif sur la liste de portefeuilles déjà codée.

---

## 5. Points encore ouverts

- Ajout d'OKX et/ou Bybit au `EXCHANGE_CATALOG` (`utils/constants.py`) et au mapping `CCXT_IDS` :
  toujours pas tranché (remplacer Kraken, ajouter en plus, ou garder Binance + Kraken tel quel).
- Migration des données existantes : au moins un utilisateur (l'utilisatrice) a déjà des clés au
  format actuel (`api_keys[exchange] = {api_key, api_secret}`, sans `mode`) — prévoir une
  migration ou une lecture rétro-compatible (`mode` absent → traiter comme `"live"`) plutôt que
  de perdre les clés déjà enregistrées.
- Séquencement de l'implémentation (4 couches : modèle chiffré, contrat API, `CcxtClient`,
  formulaire) — à décider avant de coder, pas fait dans ce document.
