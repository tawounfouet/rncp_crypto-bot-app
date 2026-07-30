# 05 — Architecture Decision Records (ADR)

Statut: référence
Derniere revision: 2026-06-09

Les ADR documentent les **décisions d'architecture importantes**, leurs contextes, et les alternatives écartées.
Chaque décision est immutable — si elle évolue, un nouvel ADR est créé.

---

## Format utilisé

```
ADR-NNN — Titre court
Status   : [Proposé | Accepté | Abandonné | Remplacé par ADR-XXX]
Date     : YYYY-MM-DD
Décideurs : [noms ou équipe]
```

---

## ADR-001 — Utiliser Apache Airflow comme orchestrateur

**Status :** Accepté  
**Date :** 2026-06-09  

### Contexte

Le projet Cryptobot nécessite d'orchestrer plusieurs tâches récurrentes :
- Collecte de prix via l'API Binance
- Calcul de signaux de trading
- Entraînement périodique des modèles ML

Ces tâches étaient initialement gérées par des scripts Python lancés manuellement ou via cron.
Aucune visibilité sur les échecs, pas de retry automatique, pas d'historique d'exécution.

### Décision

Adopter **Apache Airflow 2.8.1** comme orchestrateur.

### Alternatives considérées

| Option | Avantages | Inconvénients | Décision |
|--------|-----------|---------------|----------|
| **Cron + scripts** | Simple, natif | Pas de UI, pas de retry, pas d'historique | ❌ Écarté |
| **Prefect** | Moderne, Pythonique | Nouveau pour l'équipe, moins répandu | ❌ Écarté |
| **Dagster** | Assets-centric | Courbe d'apprentissage steep | ❌ Écarté |
| **Apache Airflow** | Standard industrie, UI riche, providers officiels | Verbose, overhead infra | ✅ Retenu |

### Conséquences

- Ajout de 3 services Docker (`airflow-webserver`, `airflow-scheduler`, `airflow-init`)
- Besoin d'une base de données dédiée (`airflow` dans PostgreSQL)
- Les pipelines sont désormais versionnés comme du code Python dans `orchestration/dags/`

---

## ADR-002 — Utiliser LocalExecutor (pas CeleryExecutor)

**Status :** Accepté  
**Date :** 2026-06-09  

### Contexte

Airflow supporte plusieurs executors pour exécuter les tâches des DAGs.
Le choix impacte directement la complexité de l'infrastructure.

### Comparaison des executors

```
SequentialExecutor     1 tâche à la fois, SQLite           → dev minimal
LocalExecutor     ──►  Parallélisme local, PostgreSQL       → dev sérieux ✅
CeleryExecutor         Multi-workers, Redis requis          → prod scale-out
KubernetesExecutor     Pod par tâche, K8s requis            → prod cloud-native
```

### Décision

Utiliser **LocalExecutor** pour l'environnement de développement local.

### Raisonnement

- `LocalExecutor` permet l'exécution **parallèle** de tâches sur une seule machine
- Compatible avec **PostgreSQL** (déjà présent dans le projet)
- **Aucune dépendance supplémentaire** (pas de Redis, pas de K8s)
- Suffisant pour les volumes de données en phase de développement
- Migration vers `CeleryExecutor` ou `KubernetesExecutor` possible en prod sans changer les DAGs

### Variable d'environnement

```yaml
AIRFLOW__CORE__EXECUTOR=LocalExecutor
```

---

## ADR-003 — Épingler la version Airflow dans le Dockerfile

**Status :** Accepté  
**Date :** 2026-06-09  
**Contexte :** Problème rencontré → voir [04-troubleshooting.md § Problème 1](./04-troubleshooting.md)

### Contexte

L'image de base `apache/airflow:2.8.1-python3.11` contient Airflow 2.8.1.
Lors du `pip install apache-airflow-providers-*`, pip résolvait les dépendances
et **mettait à niveau Airflow vers 3.x**, cassant tous les binaires de l'image.

### Décision

Ré-épingler **explicitement** `apache-airflow==2.8.1` dans la commande `pip install`
du `Dockerfile`, même si c'est redondant avec l'image de base.

```dockerfile
# orchestration/Dockerfile
RUN pip install --no-cache-dir \
    apache-airflow==2.8.1 \    ← ligne ajoutée explicitement
    apache-airflow-providers-postgres \
    ...
```

### Alternative écartée

Utiliser `--constraint` avec le fichier officiel Airflow :
```bash
pip install apache-airflow-providers-postgres \
    --constraint "https://raw.githubusercontent.com/apache/airflow/constraints-2.8.1/constraints-3.11.txt"
```
Plus propre en théorie, mais plus fragile (dépend d'une URL externe au build time).

### Conséquences

- Légère redondance dans le Dockerfile (acceptable)
- **Garantie de version figée** quelle que soit l'évolution des providers
- À mettre à jour manuellement lors d'une montée de version d'Airflow

---

## ADR-004 — Dédier le dossier `orchestration/` à Airflow

**Status :** Accepté  
**Date :** 2026-06-09  

### Contexte

Le projet dispose déjà de deux couches de services (`backend/`, `frontend/`),
chacune avec son propre `Dockerfile`. Il fallait décider où placer les artefacts Airflow.

### Options considérées

```
Option A : scripts/airflow/          → mélange avec les scripts DevOps
Option B : airflow/                  → nouveau dossier racine
Option C : orchestration/       ✅   → dossier déjà existant, sémantique claire
```

### Décision

Utiliser le dossier **`orchestration/`** déjà présent dans le projet (vide).

### Raisonnement

- Cohérence avec la convention existante (chaque service = 1 dossier)
- `orchestration/` était prévu pour cet usage (vide mais présent dans le dépôt)
- Séparation nette entre :
  - `scripts/` → outils DevOps (lint, tests, deploy)
  - `init-scripts/` → bootstrap PostgreSQL (convention image officielle)
  - `orchestration/` → code métier d'orchestration (DAGs, plugins)

### Structure résultante

```
backend/
├── Dockerfile
└── src/

frontend/
├── Dockerfile
└── src/

orchestration/            ← même niveau, même convention
├── Dockerfile
├── dags/
├── logs/
└── plugins/
```

---

## ADR-005 — Créer la base `airflow` via `init-scripts/` et non via migration Airflow

**Status :** Accepté  
**Date :** 2026-06-09  

### Contexte

Airflow nécessite sa propre base de données PostgreSQL (`airflow`).
Le projet utilisait déjà `crypto_bot_db` comme base principale.

### Options pour créer la base `airflow`

| Option | Mécanisme | Risque |
|--------|-----------|--------|
| **A** : Variable `POSTGRES_DB=airflow` | Docker Postgres crée la base au 1er boot | Casse `crypto_bot_db` |
| **B** : `airflow db init` crée tout seul | Airflow gère ses migrations | Ne crée pas la base elle-même |
| **C** : `init-scripts/` ✅ | Script SQL idempotent au 1er boot | Aucun, pattern standard |

### Décision

Utiliser un script dans `init-scripts/` monté sur `/docker-entrypoint-initdb.d/`.

### Pourquoi c'est idempotent

```sql
SELECT 'CREATE DATABASE airflow'
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'airflow')\gexec
```

La base n'est créée **que si elle n'existe pas déjà**. Relancer le script est sans danger.

### Conséquences

- Création de `init-scripts/init-user-db.sh`
- Montage de volume ajouté dans `docker-compose.yml` pour le service `postgres`
- Le script ne s'exécute qu'au **1er boot** (quand le volume `postgres_data` est vide)
