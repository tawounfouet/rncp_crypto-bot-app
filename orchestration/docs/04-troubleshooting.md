# 04 — Troubleshooting : Difficultés rencontrées

Statut: référence
Derniere revision: 2026-08-28

Historique des problèmes rencontrés lors de l'intégration d'Airflow dans le projet
`_dst-crypto-bot_v2`, avec causes racines et solutions appliquées.

---

## Problème 1 — Airflow 3.x installé à la place de 2.8.1

### Symptôme

```
airflow-init exiting with error
...
airflow: error: argument COMMAND: invalid choice: 'db' ...
```

Ou : le conteneur crashait silencieusement sans message clair.

### Cause

L'image de base `apache/airflow:2.8.1-python3.11` était bien épinglée,
**mais** la commande `pip install apache-airflow-providers-*` sans version d'Airflow
déclenchait une **mise à niveau automatique** vers Airflow 3.x (la dernière version disponible).

```
# ❌ Ce que pip faisait en réalité :
pip install apache-airflow-providers-postgres
# → résolvait les dépendances → installait apache-airflow>=3.0.0
# → écrasait le binaire airflow 2.8.1 de l'image de base
```

### Solution appliquée

Ré-épingler **explicitement** la version Airflow dans le `pip install` du Dockerfile :

```dockerfile
# ✅ Solution : épingler apache-airflow lui-même
RUN pip install --no-cache-dir \
    apache-airflow==2.8.1 \        ← ajouté ici
    apache-airflow-providers-postgres \
    ...
```

---

## Problème 2 — `NameError` dans le backend après restructuration

### Symptôme

```
NameError: name 'PaginationInfo' is not defined
```

Visible dans les logs du conteneur `crypto-bot-backend`.

### Cause

Lors de la restructuration du projet pour accueillir Airflow, le fichier
`backend/src/shared/schemas/common.py` avait une **référence croisée circulaire** :
la classe `PaginationInfo` était utilisée avant d'être définie dans le même fichier.

```python
# ❌ Avant (ordre incorrect)
class SomeResponse(BaseModel):
    pagination: PaginationInfo   # utilisée avant déclaration

class PaginationInfo(BaseModel): # déclarée après
    ...
```

### Solution appliquée

Déplacer la déclaration de `PaginationInfo` **au-dessus** de son premier usage :

```python
# ✅ Après (ordre correct)
class PaginationInfo(BaseModel):
    page: int
    per_page: int
    total: int

class SomeResponse(BaseModel):
    pagination: PaginationInfo   # déclarée avant, OK
```

---

## Problème 3 — `ModuleNotFoundError` après ajout de dépendances backend

### Symptôme

```
ModuleNotFoundError: No module named 'some_module'
```

Le backend démarrait mais crashait à l'import d'un module nouvellement ajouté.

### Cause

Docker avait mis en cache l'ancienne image du backend. Les nouveaux modules installés
dans `requirements.txt` n'étaient pas pris en compte car l'image n'avait pas été reconstruite.

```
docker compose up    ← utilise l'image cachée, n'installe PAS les nouvelles dépendances
```

### Solution appliquée

Forcer la reconstruction de l'image :

```bash
# ✅ Reconstruire sans cache
docker compose build --no-cache crypto-bot-backend

# Puis redémarrer
make dev-up
```

---

## Problème 4 — PostgreSQL refuse de créer la base `airflow`

### Symptôme

```
FATAL: database "airflow" does not exist
```

Airflow-init crashait car la base `airflow` n'existait pas dans PostgreSQL.

### Cause

Le conteneur PostgreSQL ne créait qu'une seule base par défaut (`crypto_bot_db`),
définie dans `docker-compose.yml` via `POSTGRES_DB`. Airflow avait besoin d'une base séparée.

### Solution appliquée

Créer `init-scripts/init-user-db.sh` et le monter dans `/docker-entrypoint-initdb.d/` :

```bash
# init-scripts/init-user-db.sh
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-EOSQL
    SELECT 'CREATE DATABASE airflow'
    WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'airflow')\gexec
EOSQL
```

```yaml
# docker-compose.yml
postgres:
  volumes:
    - ./init-scripts:/docker-entrypoint-initdb.d   # ← exécution automatique au 1er boot
```

> ⚠️ Ce script n'est exécuté **qu'au premier démarrage** (quand le volume `postgres_data`
> est vide). Si vous avez un volume existant, il faut le supprimer pour rejouer le script :
> `docker volume rm app_postgres_data`

---

## Problème 5 — `airflow-webserver` démarre avant `airflow-init`

### Symptôme

```
airflow-webserver | ERROR - No user found
airflow-webserver | connexion refused to airflow DB
```

### Cause

Docker Compose ne garantit pas l'ordre d'exécution entre services par défaut.
`airflow-webserver` démarrait avant qu'`airflow-init` ait eu le temps d'initialiser la base.

### Solution appliquée

Utiliser la condition `service_completed_successfully` dans `depends_on` :

```yaml
airflow-webserver:
  depends_on:
    postgres:
      condition: service_healthy            # attendre que PG soit prêt
    airflow-init:
      condition: service_completed_successfully   # attendre la fin de l'init
```

---

## Problème 6 — `error getting credentials` au `docker compose up`

### Symptôme

```
 ⠙ Image postgres:14   Pulling
error getting credentials - err: exit status 1, out: ``
make: *** [Makefile:32: dev-up] Error 1
```

Le build se termine bien, mais `make dev-up` échoue pendant le **pull des images de
base** (postgres, adminer…).

### Cause

`~/.docker/config.json` contient `"credsStore": "desktop.exe"` : Docker délègue la
récupération d'identifiants à `docker-credential-desktop.exe` (Docker Desktop). Quand
l'intégration WSL/Docker Desktop est momentanément instable, ce helper renvoie
`exit status 1`. Les pulls **parallèles** de `docker compose` traitent cette erreur
comme fatale — **même pour des images publiques** qui ne demandent aucune
authentification (un `docker pull` simple, lui, retombe en anonyme et passe).

### Solution

- **Automatique (en place)** : `make dev-up` réessaie le démarrage jusqu'à **5 fois avec
  backoff** (5s, 10s, 15s, 20s → ~50s de résilience). Ça absorbe les hoquets transitoires
  de Docker Desktop sans intervention. S'assurer quand même que Docker Desktop est démarré.
- **Si ça persiste après les 5 essais (par poste, non committable)** : le retry est une
  mitigation, pas une garantie — un hoquet DD très long peut le dépasser. Le fix
  **définitif** est de retirer le credential store (les images de `dev-up` sont
  **publiques**, aucun identifiant requis) : éditer `~/.docker/config.json` et supprimer la
  ligne `"credsStore": "desktop.exe"` (sauvegarde avant). Les pulls passent alors en
  anonyme, le helper n'est plus jamais appelé.

---

## Problème 7 — Airflow échoue « une fois sur deux » au déploiement à neuf

### Symptôme

Après suppression de tous les volumes puis `make dev-up`, Airflow ne démarre pas
(`database "airflow" does not exist` dans les logs `airflow-init`). Un **2ᵉ** `make
dev-up` fonctionne. Comportement non déterministe = **race condition**.

### Cause

Deux bugs combinés :

1. **Course au démarrage** : le healthcheck Postgres (`pg_isready`) passe via le socket
   **dès la phase d'init** (serveur temporaire qui exécute `init-user-db.sh`). Postgres
   était donc signalé `healthy` **avant** que la base `airflow` soit créée. `airflow-init`
   (`depends_on: service_healthy`) démarrait trop tôt → `airflow db init` sur une base
   inexistante.
2. **Échec silencieux** : l'entrypoint `airflow-init` n'avait pas `set -e` et finissait par
   `... || true`, donc il sortait en `exit 0` même en cas d'échec → webserver/scheduler
   démarraient sur une base cassée.

Au 2ᵉ `dev-up`, les bases existent déjà (volume non vide) → plus de course.

### Solution appliquée (déjà dans `docker-compose.yml`)

```yaml
# healthcheck postgres : ne devient healthy qu'une fois la base airflow créée
test: ["CMD-SHELL", "pg_isready -U ${POSTGRES_USER:-postgres} -q && psql -U ${POSTGRES_USER:-postgres} -d airflow -c 'SELECT 1' >/dev/null 2>&1"]
```
```yaml
# entrypoint airflow-init : échec bruyant
- |
  set -e
  airflow db init
  ...
```

### Procédure propre de « redeploy from 0 »

```bash
make dev-down-v   # arrête tout ET supprime les volumes du projet (postgres,
                  # minio, airflow_logs). À lancer via make : `docker compose down -v`
                  # seul échoue (variables versions.env non chargées).
make dev-build    # si le code / les deps ont changé
make dev-up
```

> Volume `postgres_data` vide ⇒ `init-user-db.sh` rejoue et crée `airflow` + `mlflow`.
> Avec le healthcheck corrigé, `airflow-init` attend que ce soit fait : plus de course.

---

## Problème 8 — DAG `ml_pipeline` : `train-rf` échouait (ModuleNotFoundError sklearn/torch)

### Statut : résolu

### Symptôme (historique)

Une fois Airflow déployé sur staging/prod (VM AWS, image construite depuis
`orchestration/Dockerfile`), les tâches `build_features_*` et `train_random_forest`
du DAG `ml_pipeline` échouaient avec `ModuleNotFoundError: No module named 'sklearn'`
(ou `torch`).

### Cause (historique)

`ml_pipeline.py` lançait l'entraînement via `BashOperator` (`cd {MODELS_DIR} && python
-m src.main train-rf`), exécuté **dans le conteneur Airflow lui-même**. Mais
`orchestration/requirements.txt` n'inclut que `jobs/requirements.txt` (dépendances
d'ingestion), pas `models/requirements.txt` (`pandas`, `scikit-learn`, `torch`,
`mlflow`...). `pandas` fonctionnait par hasard (dépendance transitive d'un provider
Airflow), pas les autres.

### Résolution retenue

La piste 2 envisagée a été retenue : `build_features_*` et `train_random_forest`
sont désormais déclenchées par un **appel HTTP** au conteneur `crypto-bot-ml-api`
(routes `POST /internal/pipeline/features`, `POST /internal/pipeline/train-rf`),
au lieu d'exécuter `python -m src.main` dans l'environnement Python d'Airflow.
Raison (cf. docstring de `orchestration/dags/ml_pipeline.py`) : `ml-api` a déjà
torch/mlflow/scikit-learn qui fonctionnent ; les installer en plus dans l'image
Airflow provoquait des conflits de versions (ex: `email-validator`/`pydantic`
requis par Flask-AppBuilder vs. celui tiré par une version récente de mlflow).
Airflow orchestre, il n'héberge plus la stack ML.

Le DAG `ingest_ohlcv` n'est pas concerné (dépendances légères, déjà dans
`jobs/requirements.txt`) et fonctionne normalement.

---

## Problème 9 — Staging : `InvalidAccessKeyId` sur l'upload MinIO (ingestion)

### Statut : résolu

### Symptôme

`ingest_ohlcv_binance_to_minio` / `ingest_ohlcv_kraken_to_minio` échouent sur la tâche
`collect_<exchange>_<symbol>_<interval>` avec un `RuntimeError: Échec de l'upload MinIO
pour raw/ohlcv/...` peu explicite dans le log de tâche Airflow (UI). La vraie erreur
n'apparaît **pas** dans ce log : `utils/connectors/minio.py` utilise le logger maison
`utils.logging.get_logger()` (`propagate = False`, handlers console + fichier propres),
contrairement au reste du pipeline d'ingestion (`logging.getLogger(__name__)` standard,
capté par Airflow). Sa ligne `logger.error("DataFrame upload failed ...")` part donc
ailleurs — dans les logs bruts du conteneur (`docker logs <airflow-scheduler>`) ou dans
`logs/cryptobot.log` à l'intérieur du conteneur, jamais dans le fichier que l'UI Airflow
affiche.

Une fois cette ligne retrouvée : `S3 operation failed; code: InvalidAccessKeyId, message:
The Access Key Id you provided does not exist in our records.`

### Cause

`docker-compose.staging.yml` initialise l'identité réelle de MinIO depuis
`MINIO_USER_ADMIN`/`MINIO_PWD_ADMIN`, alors que tous les services consommateurs
(Airflow, `ml-api`, backend) s'authentifient avec `MINIO_ROOT_USER`/`MINIO_ROOT_PASSWORD`
— deux paires de variables distinctes censées porter le même secret (même convention
sur `docker-compose.yml` et `docker-compose.prod.yml`). Le `.env` de la VM staging avait
les 4 variables présentes mais avec des valeurs différentes entre les deux paires : MinIO
avait donc une identité réelle différente de celle utilisée pour s'y connecter.

### Résolution retenue

Alignement de `MINIO_ROOT_USER`/`MINIO_ROOT_PASSWORD` sur les valeurs de
`MINIO_USER_ADMIN`/`MINIO_PWD_ADMIN` dans le `.env` de la VM (c'est cette 2e paire qui a
servi à initialiser le vrai compte root MinIO au moment de la création du volume — l'aligner
dans l'autre sens aurait nécessité de recréer le volume MinIO, donc de perdre les données
déjà stockées). Puis redémarrage des seuls services consommateurs (pas `minio`, pour ne
pas toucher son volume).

**Point de vigilance pour la suite** : rien ne garantit aujourd'hui que ces deux paires
restent synchronisées après un futur changement de l'une sans l'autre — à surveiller si
l'erreur revient après une rotation de secrets.

---

## Problème 10 — Staging : `ml-api` reste sur une image d'il y a 3 semaines malgré un déploiement CI "réussi"

### Statut : cause racine identifiée, pas corrigé (report décidé le 2026-08-28)

### Symptôme

Après le merge d'une MR sur `staging` et un pipeline CI vert (`build:docker` +
`deploy:staging` tous deux en succès, nouvelle image `ml-api` bien poussée sur le
registre avec un digest récent), le DAG `cryptobot_ml_pipeline` échoue sur les tâches
`train_random_forest_*`/`train_xgboost_*` avec `RuntimeError: Route d'entrainement
introuvable: .../internal/pipeline/train-xgboost` — une route pourtant bien présente
dans le code déployé. `docker inspect staging-ml-api --format '{{.Image}}'` puis
`docker image inspect ... --format '{{.Created}}'` confirment que le conteneur tourne
sur une image construite le **2026-08-02**, sans rapport avec le commit réellement
déployé.

### Cause

Le disque de la VM staging est plein. `docker pull` pour `ml-api` (une image ~980 Mo)
échoue en cours de téléchargement (`write ... no space left on device`) avant de pouvoir
remplacer l'image locale. Le job `deploy:staging` (`.gitlab-ci.yml`) fait ce pull avec
`docker compose ... pull --ignore-pull-failures` : ce flag masque silencieusement l'échec,
la suite du déploiement (`down` + `up -d`) continue et redémarre donc l'ancienne image déjà
en cache local, sans qu'aucune erreur ne remonte dans les logs du pipeline CI (qui affiche
"success"). Un `docker compose pull` lancé manuellement sans ce flag confirme l'erreur
disque explicitement.

Point annexe rencontré en diagnostiquant : un `docker compose` lancé à la main sur la VM
(hors `make`/script CI) échoue avec `service "postgres" has neither an image nor a build
context specified` si `versions.env` n'est pas d'abord chargé dans le shell — le Makefile
le fait via `include versions.env`, le script CI via `export $(grep ... versions.env)`,
mais rien ne le fait automatiquement pour une commande `docker compose` tapée directement.

### Résolution — reportée

Diagnostic terminé, correctif reporté (décision du 2026-08-28, fin de session). Actions à
prévoir pour une prochaine session :
- Libérer de l'espace disque sur la VM staging (`docker system prune`, ou identifier ce qui
  consomme l'espace avant de purger aveuglément — ne pas le faire sans vérifier d'abord ce
  qui serait supprimé).
- Retirer ou remplacer `--ignore-pull-failures` dans `deploy:staging` (`.gitlab-ci.yml`) par
  quelque chose qui fait échouer le pipeline si le pull échoue vraiment, plutôt que de
  déployer silencieusement une image obsolète.
- Envisager une alerte/vérification d'espace disque disponible avant déploiement.

---

## Checklist de diagnostic rapide

```
Airflow ne démarre pas ?
│
├─► Vérifier les logs init
│       docker compose logs airflow-init
│
├─► Vérifier que la base 'airflow' existe
│       docker compose exec postgres psql -U postgres -c "\l"
│
├─► Vérifier les variables d'environnement
│       docker compose config | grep AIRFLOW
│
├─► Forcer une reconstruction complète
│       docker compose down
│       docker volume rm $(docker volume ls -q | grep postgres)
│       docker compose build --no-cache
│       make dev-up
│
└─► Accéder directement au conteneur
        docker compose exec airflow-webserver bash
        airflow db check
```
