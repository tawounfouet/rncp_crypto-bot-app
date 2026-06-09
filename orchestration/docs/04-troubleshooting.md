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
