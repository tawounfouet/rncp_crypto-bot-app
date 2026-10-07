# Architecture — ci/

> Document de référence de la **chaîne de tests d'intégration**. Vue CI globale dans [`../README.md`](../README.md) (§ infrastructure) et [`../CODEBASE_ANALYSIS.md`](../CODEBASE_ANALYSIS.md) §6.

---

## 1. Vue d'ensemble

`ci/` héberge le **compose de tests d'intégration** exécuté par la CI GitLab (`test:integration`) et rejouable en local via `make ci-test`. Il fait tourner la suite de tests backend dans l'**image Docker réelle** contre un **vrai PostgreSQL**, afin de valider migrations, connexions et persistance.

```
ci/
├── docker-compose.test.yml   # postgres + test-runner (image backend)
└── test-results/             # rapports générés, TRACKÉS dans git
    ├── report.xml            # JUnit
    ├── coverage.xml          # Cobertura
    └── test_report.txt       # résumé lisible
```

> `ci/test-results/` est **volontairement suivi par git** (traçabilité des rapports) — ne pas le gitignorer ni le supprimer.

---

## 2. Compose de test

`ci/docker-compose.test.yml` définit deux services sur le réseau `test-network` :

| Service | Image | Rôle |
|---|---|---|
| `postgres` | `${POSTGRES_IMAGE}` | Base éphémère (`test`/`test`, `crypto_bot_test`) avec healthcheck `pg_isready` |
| `test-runner` | `${IMAGE_TAG}` (cible `test` du backend) | Exécute `pytest tests -v` avec couverture |

Le `test-runner` lance :
```
pytest tests -v \
  --junitxml=/tmp/test-results/report.xml \
  --cov=src --cov-report=term-missing --cov-report=xml:/tmp/test-results/coverage.xml
python /app/ci/parse_test_report.py /tmp/test-results/report.xml /tmp/test-results/test_report.txt
```
(la génération du rapport est non bloquante ; le code de sortie de `pytest` est propagé — `docker-compose.test.yml:50-58`).

Variables injectées pour les tests : `ENVIRONMENT=test`, `DEBUG=true`, `JWT_SIGNING_KEY=test-…` (valeur de test uniquement), `CORS_ORIGINS`, `ALLOWED_HOSTS`, `POSTGRES_*`, `MINIO_*`.

---

## 3. Exécution

- **CI GitLab** : job `test:integration` (`.gitlab-ci.yml:205`) → `docker compose --env-file versions.env -f ci/docker-compose.test.yml up --abort-on-container-exit --exit-code-from test-runner`, puis copie des résultats dans `ci/test-results/` (artefacts JUnit/Cobertura — `.gitlab-ci.yml:238-243`).
- **Local** : `make ci-test` (`Makefile:171`) — build de la cible `test` du backend (`crypto-bot-backend:ci-test-local`), exécution du compose, copie des résultats.

> ⚠️ Le job `test:integration` est le **seul** test exécuté en CI : aucun test unitaire backend, ni frontend, ni `models/`, ni `orchestration/`.

---

## 4. Rapport JUnit

`backend/ci/parse_test_report.py` (inclus dans l'image `test` via `COPY backend/ci/parse_test_report.py`) parse le XML JUnit (`defusedxml`) et produit un résumé texte (`parse_and_report`, `parse_test_report.py:18`). Appelé par le compose et par la CI.

---

## 5. Limites structurelles (renvoi)

1. CI = **lint + intégration backend uniquement** (pas de tests unitaires, `models/`, `orchestration/`).
2. `make ci-test` laisse parfois des conteneurs `ci-*` arrêtés (voir `AGENTS.md` piège 9).
3. `ci/test-results/` est suivi : les builds mettent à jour des fichiers trackés.

Argumentation : [`../ANALYSE_CRITIQUE.md`](../ANALYSE_CRITIQUE.md) §6.
