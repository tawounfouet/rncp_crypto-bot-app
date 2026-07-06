# Architecture cible - Bots IA de trading Binance Testnet

## Objectif du document

Ce document sert de source pour generer une presentation NotebookLM.

Le sujet est l'architecture cible d'une application de bots de trading crypto ou chaque utilisateur peut :

- creer un compte applicatif ;
- connecter ses propres API keys Binance Spot Testnet ;
- choisir un bot cle en main compose d'un modele IA, d'une strategie et d'une configuration complete ;
- laisser le backend executer les decisions du bot sur son compte Binance Testnet.

Le principe central est simple :

```text
1 utilisateur
-> ses propres cles Binance Testnet chiffrees
-> ses propres instances de bots
-> ses propres ordres et trades
```

L'application ne doit jamais utiliser une cle Binance globale pour trader au nom de tous les utilisateurs.

## Vision produit

L'application doit permettre a un utilisateur de selectionner un bot pret a l'emploi, puis de le faire fonctionner sur Binance Spot Testnet.

Un point produit est volontairement strict : l'utilisateur ne parametre pas le bot apres selection.
Il choisit le bot dans son entierete. La strategie, le modele IA, la paire, le timeframe, les signaux,
les limites de risque, les tailles d'ordre et les parametres d'execution sont deja definis dans le
bot template par l'equipe produit/quant.

Un bot n'est pas seulement une strategie. Dans l'architecture cible, un bot est compose de trois blocs :

```text
Bot = modele IA + strategie de trading + parametres d'execution
```

### Etat officiel V1 du moteur IA

La V1 de `crypto-bot-app` n'appelle pas `crypto-bot-ml-api` depuis le worker de trading.
Le worker backend utilise un modele deterministe local dans `backend/src/bots/ai.py` :

- `regime_classifier_v1` filtre les signaux RSI selon regime RSI et momentum ;
- `trend_classifier_v1` filtre les signaux de tendance selon l'ecart de moyennes mobiles.

La ML API reste disponible comme service de signaux et d'experimentation MLOps, mais elle n'est pas encore
le moteur de decision des bots live Testnet. Un raccordement futur devra remplacer explicitement cette
couche deterministe et journaliser la source `crypto-bot-ml-api` dans `model_output`.

Exemple :

```text
Bot IA RSI BTCUSDT
- modele IA : prediction du regime de marche
- strategie : RSI mean reversion
- paire : BTCUSDT
- time frame : 1h
- risk per trade : 1 %
- stop loss : 2 %
- take profit : 4 %
- auto trade : active
```

L'utilisateur ne peut pas transformer ce bot en ETHUSDT, modifier le RSI, changer le timeframe,
augmenter le risque ou remplacer le signal. Pour obtenir un autre comportement, il choisit un autre
bot template publie dans l'application.

## Notions importantes

### Utilisateur

L'utilisateur possede un compte dans l'application.

Il peut stocker ses cles Binance Testnet dans l'application. Ces cles sont chiffrees en base de donnees et ne sont jamais affichees apres leur enregistrement.

### Binance Testnet

Binance Spot Testnet permet de tester du trading Spot via API sans utiliser de vrais fonds.

Les endpoints utilises sont les endpoints `/api/*` du Spot Testnet. Les actions de trading, comme la creation d'un ordre, utilisent des endpoints signes avec l'API key et l'API secret de l'utilisateur.

### API key et API secret

L'API key et l'API secret Binance sont stockes chiffres, pas haches.

Raison :

- un mot de passe utilisateur doit etre hache, car on n'a jamais besoin de le retrouver ;
- un API secret Binance doit etre chiffre, car le backend doit pouvoir le dechiffrer en memoire pour signer les requetes Binance.

Le frontend ne doit jamais recevoir l'API secret.

### Bot template

Un bot template est un modele reutilisable.

Il decrit la logique generale du bot :

```text
bot_templates
- id
- name
- description
- model_type
- strategy_type
- symbol
- timeframe
- signal_source
- execution_params
- risk_limits
- order_policy
- status
```

Exemple :

```text
Bot template :
"AI RSI Mean Reversion"

Contenu :
- modele IA : classification regime de marche
- strategie : RSI mean reversion
- symbole fixe : BTCUSDT
- timeframe fixe : 1h
- signal_source : regime_model_v1 + rsi_reversal
- parametres fixes : RSI 14, oversold 30, overbought 70
- risk_limits fixes : max 1 % par trade, stop loss 2 %, take profit 4 %
```

### Bot instance

Une bot instance est le bot reel choisi par un utilisateur.

Elle relie :

- un utilisateur ;
- un bot template ;
- des cles Binance Testnet ;
- un etat d'execution.

```text
user_bot_instances
- id
- user_id
- bot_template_id
- exchange_credential_id
- mode
- status
- auto_trade_enabled
- config_snapshot
- created_at
- updated_at
```

Exemple :

```text
Instance utilisateur :
- user_id : utilisateur A
- bot_template_id : AI RSI Mean Reversion
- exchange_credential_id : cles Binance Testnet de l'utilisateur A
- config_snapshot : copie verrouillee du template choisi
- auto_trade_enabled : true
- status : active
```

`config_snapshot` est une copie technique de la configuration complete au moment de la creation.
Elle permet de conserver l'historique exact du bot choisi meme si le template est versionne plus tard.
Elle n'est pas modifiable par l'utilisateur.

## Architecture recommandee

L'architecture cible se compose de plusieurs couches.

```text
Frontend Streamlit
-> Backend FastAPI
-> PostgreSQL
-> Worker de trading
-> Binance Spot Testnet API
```

### Frontend

Le frontend permet a l'utilisateur de :

- creer un compte ;
- se connecter ;
- ajouter ses cles Binance Testnet ;
- choisir un bot ;
- activer ou mettre en pause un bot ;
- consulter les decisions, ordres, trades, erreurs et performances.

Le frontend ne doit pas :

- recevoir l'API secret ;
- signer des requetes Binance ;
- envoyer directement des ordres a Binance.

### Backend FastAPI

Le backend gere :

- l'authentification ;
- les utilisateurs ;
- le chiffrement et dechiffrement des cles Binance ;
- la creation des bot instances ;
- les validations de securite ;
- les endpoints pour demarrer, mettre en pause ou arreter un bot ;
- la lecture des resultats et historiques.

Le backend est la seule couche autorisee a dechiffrer temporairement l'API secret en memoire.

### PostgreSQL

PostgreSQL stocke :

- les utilisateurs ;
- les credentials exchange chiffres ;
- les bot templates ;
- les bot instances ;
- les executions ;
- les decisions IA ;
- les ordres ;
- les trades ;
- les positions ;
- les journaux d'erreur.

### Worker de trading

Le worker execute les bots actifs.

Il fonctionne en boucle :

```text
1. lire les bot instances actives
2. charger les parametres du bot
3. charger les credentials de l'utilisateur
4. dechiffrer temporairement l'API key et l'API secret
5. recuperer les donnees de marche
6. executer le modele IA
7. executer la strategie
8. appliquer le risk manager
9. envoyer ou non un ordre Binance Testnet
10. sauvegarder decision, ordre, trade et logs
```

## Tables recommandees

### users

Stocke les comptes utilisateurs de l'application.

```text
users
- id
- email
- username
- hashed_password
- is_active
- is_admin
- last_active_at
- created_at
- updated_at
```

Le mot de passe est hache avec Argon2.

### user_exchange_credentials

Table dediee aux cles exchange d'un utilisateur.

Cette table est recommandee pour la vraie architecture production, car elle est plus propre qu'un JSON dans `user_settings`.

```text
user_exchange_credentials
- id
- user_id
- exchange
- environment
- api_key_encrypted
- api_secret_encrypted
- label
- is_active
- permissions_checked
- last_verified_at
- created_at
- updated_at
```

Exemple :

```text
exchange : binance
environment : testnet
label : Binance Spot Testnet principal
```

L'API key et l'API secret sont chiffres avec AES-GCM via une cle serveur appelee `BINANCE_ENC_KEY`.

### bot_templates

Stocke les bots disponibles dans la marketplace interne de l'application.

```text
bot_templates
- id
- name
- description
- model_type
- strategy_type
- symbol
- timeframe
- signal_source
- execution_params
- risk_limits
- order_policy
- version
- status
- created_at
- updated_at
```

Un bot template ne contient aucune information utilisateur et ne contient pas de champs editables par
l'utilisateur final.

### user_bot_instances

Relie un utilisateur a un bot concret.

```text
user_bot_instances
- id
- user_id
- bot_template_id
- exchange_credential_id
- mode
- status
- auto_trade_enabled
- config_snapshot
- created_at
- updated_at
```

Cette table est centrale.

Elle repond a la question :

```text
Quel utilisateur utilise quel bot preconfigure, avec quelles cles, et dans quel etat d'execution ?
```

### bot_runs

Historique des executions d'une instance de bot.

```text
bot_runs
- id
- user_bot_instance_id
- started_at
- ended_at
- status
- error_message
- worker_id
```

### trading_decisions

Journal des decisions prises par l'IA et la strategie.

```text
trading_decisions
- id
- user_bot_instance_id
- run_id
- timestamp
- symbol
- timeframe
- market_snapshot
- model_output
- strategy_signal
- risk_decision
- final_action
- reason
```

Exemple de `final_action` :

```text
BUY
SELL
HOLD
SKIP_RISK_LIMIT
SKIP_NO_SIGNAL
```

### orders

Stocke les ordres envoyes a Binance Testnet.

```text
orders
- id
- user_id
- user_bot_instance_id
- exchange
- environment
- symbol
- side
- order_type
- quantity
- price
- status
- binance_order_id
- client_order_id
- raw_response
- created_at
- updated_at
```

### trades

Stocke les executions reelles des ordres.

```text
trades
- id
- user_id
- order_id
- user_bot_instance_id
- symbol
- side
- quantity
- price
- fee
- fee_asset
- trade_time
- raw_response
```

### positions

Vue ou table permettant de suivre l'exposition courante.

```text
positions
- id
- user_id
- user_bot_instance_id
- symbol
- quantity
- average_entry_price
- unrealized_pnl
- realized_pnl
- updated_at
```

## Flux utilisateur complet

### Etape 1 - Creation du compte

L'utilisateur cree un compte avec email, username et mot de passe.

Le mot de passe est hache avec Argon2.

### Etape 2 - Ajout des cles Binance Testnet

L'utilisateur ajoute :

- API key Binance Testnet ;
- API secret Binance Testnet ;
- confirmation du mot de passe applicatif.

Le backend :

```text
1. verifie le mot de passe
2. chiffre API key et API secret
3. stocke le resultat dans PostgreSQL
4. ne renvoie jamais l'API secret au frontend
```

### Etape 3 - Verification des permissions

Le backend peut tester les credentials avec Binance Testnet :

```text
GET /api/v3/account
```

Objectif :

- verifier que les cles sont valides ;
- verifier que l'utilisateur est bien sur Testnet ;
- verifier que les permissions sont suffisantes pour lire le compte et trader.

### Etape 4 - Choix du bot

L'utilisateur choisit un bot disponible.

Exemple :

```text
AI RSI Mean Reversion
```

Il consulte la configuration complete du bot :

- paire : BTCUSDT ;
- timeframe : 1h ;
- montant maximum par trade ;
- stop loss ;
- take profit ;
- signal IA et strategie ;
- mode d'execution.

Il ne peut pas modifier ces valeurs. Il peut seulement choisir ce bot, le demarrer, le mettre en pause
ou l'arreter.

### Etape 5 - Creation de l'instance

Le backend cree une ligne dans `user_bot_instances`.

Cette ligne relie :

```text
user_id
bot_template_id
exchange_credential_id
config_snapshot
```

### Etape 6 - Execution par worker

Le worker lit les instances actives.

Pour chaque instance :

```text
bot_instance = charger depuis PostgreSQL
credentials = charger et dechiffrer en memoire
market_data = recuperer depuis Binance ou base interne
prediction = executer modele IA
signal = executer strategie
risk = valider avec risk manager
order = envoyer a Binance Testnet si autorise
log = sauvegarder decision et resultat
```

### Etape 7 - Suivi utilisateur

L'utilisateur voit :

- statut du bot ;
- derniere decision ;
- dernier signal ;
- ordres ouverts ;
- trades executes ;
- PnL ;
- erreurs ;
- statut des credentials.

## Securite

### Regles essentielles

Le systeme doit respecter ces regles :

```text
1. Ne jamais stocker l'API secret en clair.
2. Ne jamais afficher l'API secret apres sauvegarde.
3. Ne jamais envoyer l'API secret au frontend.
4. Ne jamais logger l'API secret.
5. Dechiffrer uniquement en memoire et uniquement au moment d'appeler Binance.
6. Utiliser des permissions minimales sur les cles Binance.
7. Utiliser Binance Testnet pour les tests.
8. Utiliser une whitelist IP Binance quand possible.
```

### Chiffrement des cles

Les cles Binance sont chiffrees avec AES-GCM.

La cle racine `BINANCE_ENC_KEY` ne doit pas etre stockee dans PostgreSQL.

En developpement, elle peut etre dans `.env`.

En production, elle doit idealement etre injectee via :

- Docker Secret ;
- Kubernetes Secret ;
- HashiCorp Vault ;
- AWS Secrets Manager ;
- GCP Secret Manager ;
- Azure Key Vault.

### Difference hash et chiffrement

```text
Mot de passe utilisateur
-> hash Argon2
-> non reversible

API secret Binance
-> chiffrement AES-GCM
-> reversible par le backend
```

L'API secret doit etre reversible car Binance demande une signature HMAC pour les endpoints securises.

## Risk manager

Le risk manager est obligatoire avant tout ordre.

Il doit verifier :

- taille maximale d'un ordre ;
- exposition maximale par utilisateur ;
- exposition maximale par bot ;
- nombre maximum d'ordres ouverts ;
- perte maximale journaliere ;
- distance stop loss ;
- solde disponible ;
- statut de la paire ;
- mode Testnet ou Live.

Exemple :

```text
Signal strategie : BUY
Risk manager : refuse
Raison : exposition maximale deja atteinte
Action finale : SKIP_RISK_LIMIT
```

## Mode Testnet et mode Live

La premiere version doit rester en Binance Spot Testnet.

Le mode Live ne doit etre ajoute qu'apres :

- tests stables ;
- audit des logs ;
- validation risk manager ;
- permissions minimales ;
- UI de confirmation ;
- kill switch ;
- monitoring.

L'architecture doit donc separer :

```text
environment = testnet
environment = live
```

Un bot Testnet ne doit jamais utiliser des credentials Live.

Un bot Live ne doit jamais utiliser des credentials Testnet.

## Dashboard utilisateur

Le dashboard final doit montrer :

- liste des bots actifs ;
- statut de chaque bot ;
- paire tradee ;
- modele IA utilise ;
- strategie utilisee ;
- parametres verrouilles du template ;
- dernier signal ;
- derniere decision ;
- ordres ouverts ;
- trades executes ;
- PnL ;
- erreurs recentes ;
- bouton pause ;
- bouton stop ;
- bouton voir details.

## Exemple de sequence technique

```text
Utilisateur A lance le bot "AI RSI Mean Reversion" sur BTCUSDT.

1. POST /user-bots
2. Backend cree user_bot_instance
3. Worker detecte l'instance active
4. Worker recupere les credentials de l'utilisateur A
5. Worker dechiffre les credentials en memoire
6. Worker recupere les bougies BTCUSDT
7. Modele IA predit un regime favorable
8. Strategie RSI donne un signal BUY
9. Risk manager valide
10. Backend signe la requete Binance
11. Ordre envoye a Binance Spot Testnet
12. Reponse Binance sauvegardee dans orders
13. Decision sauvegardee dans trading_decisions
14. Dashboard utilisateur mis a jour
```

## Endpoints backend possibles

```text
POST /users/me/exchange-credentials
GET /users/me/exchange-credentials
POST /users/me/exchange-credentials/{id}/verify
DELETE /users/me/exchange-credentials/{id}

GET /bot-templates
GET /bot-templates/{id}

POST /user-bots
GET /user-bots
GET /user-bots/{id}
POST /user-bots/{id}/start
POST /user-bots/{id}/pause
POST /user-bots/{id}/stop

GET /user-bots/{id}/decisions
GET /user-bots/{id}/orders
GET /user-bots/{id}/trades
GET /user-bots/{id}/performance
```

## Roadmap technique proposee

### Phase 1 - Stabiliser l'authentification et credentials Testnet

- compte utilisateur reel ;
- login/logout ;
- stockage chiffre des credentials Binance Testnet ;
- verification des credentials ;
- page de test Binance Testnet.

### Phase 2 - Creer le modele de bot

- table `bot_templates` ;
- table `user_bot_instances` ;
- UI de selection d'un bot preconfigure ;
- affichage en lecture seule de la configuration complete du bot ;
- activation pause stop.

### Phase 3 - Worker d'execution

- worker qui lit les bots actifs ;
- execution strategie sans ordre reel ;
- journal des decisions ;
- mode paper trading interne.

### Phase 4 - Trading Testnet

- connexion Binance Spot Testnet ;
- passage d'ordres Testnet ;
- annulation d'ordres ;
- synchronisation des trades ;
- dashboard ordres et PnL.

### Phase 5 - Risk manager avance

- limites par utilisateur ;
- limites par bot ;
- limites par paire ;
- kill switch ;
- alertes.

### Phase 6 - Preparation production

- secrets manager ;
- monitoring ;
- audit trail ;
- rotation de cles ;
- separation stricte Testnet / Live ;
- tests de charge ;
- revue securite.

## Message cle pour la presentation

Le point central de l'architecture est la separation entre :

```text
bot template
-> logique generale reutilisable

user bot instance
-> configuration concrete d'un utilisateur

exchange credentials
-> cles Binance chiffrees appartenant a cet utilisateur
```

Cette separation permet de gerer plusieurs utilisateurs, plusieurs bots, plusieurs paires et plusieurs comptes exchange sans melanger les responsabilites.

## Sources utiles

- Binance Spot API documentation : https://developers.binance.com/docs/binance-spot-api-docs
- Binance Spot Testnet documentation : https://developers.binance.com/docs/binance-spot-api-docs/testnet
- Binance signed request security : https://developers.binance.com/docs/binance-spot-api-docs/testnet/rest-api/request-security
- Binance user data stream Testnet : https://developers.binance.com/docs/binance-spot-api-docs/testnet/user-data-stream
