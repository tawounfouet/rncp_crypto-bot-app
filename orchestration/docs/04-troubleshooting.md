# 04 — Troubleshooting : Difficultés rencontrées

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
    apache-airflow-providers-mongo \
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
 ⠙ Image mongo:4.4     Pulling
error getting credentials - err: exit status 1, out: ``
make: *** [Makefile:32: dev-up] Error 1
```

Le build se termine bien, mais `make dev-up` échoue pendant le **pull des images de
base** (postgres, mongo, adminer…).

### Cause

`~/.docker/config.json` contient `"credsStore": "desktop.exe"` : Docker délègue la
récupération d'identifiants à `docker-credential-desktop.exe` (Docker Desktop). Quand
l'intégration WSL/Docker Desktop est momentanément instable, ce helper renvoie
`exit status 1`. Les pulls **parallèles** de `docker compose` traitent cette erreur
comme fatale — **même pour des images publiques** qui ne demandent aucune
authentification (un `docker pull` simple, lui, retombe en anonyme et passe).

### Solution

- **Immédiat** : relancer `make dev-up` (l'erreur est intermittente, le 2ᵉ essai passe
  généralement). S'assurer que Docker Desktop est bien démarré.
- **Permanent (par poste, non committable)** : comme `dev-up` ne tire que des images
  **publiques**, on peut retirer le credential store. Éditer `~/.docker/config.json` et
  supprimer la ligne `"credsStore": "desktop.exe"` (faire une sauvegarde avant). Les
  pulls passent alors en anonyme, sans dépendre de Docker Desktop.

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
make dev-down
# /!\ docker compose down -v lancé seul échoue (variables versions.env non chargées).
#     Supprimer les volumes explicitement :
docker volume rm crypto-bot-app_postgres_data crypto-bot-app_mongo_data \
                 crypto-bot-app_minio_data crypto-bot-app_airflow_logs
make dev-build   # si le code/les deps ont changé
make dev-up
```

> Volume `postgres_data` vide ⇒ `init-user-db.sh` rejoue et crée `airflow` + `mlflow`.
> Avec le healthcheck corrigé, `airflow-init` attend que ce soit fait : plus de course.

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
