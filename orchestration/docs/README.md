# Orchestration — Apache Airflow dans Cryptobot

> Documentation complète de l'intégration d'Apache Airflow dans le projet `_dst-crypto-bot_v2`.

---

## 📚 Table des matières

| Fichier | Description |
|---------|-------------|
| [01-architecture.md](./01-architecture.md) | Vue d'ensemble de l'architecture et des composants |
| [02-setup-guide.md](./02-setup-guide.md) | Guide pas-à-pas de mise en place |
| [03-dags.md](./03-dags.md) | Écriture et structure des DAGs Cryptobot |
| [04-troubleshooting.md](./04-troubleshooting.md) | Problèmes rencontrés et solutions |
| [05-adr.md](./05-adr.md) | Architecture Decision Records (ADR) |

---

## Vue rapide

```
Cryptobot Stack
│
├── Frontend     (Streamlit)     :8501
├── Backend      (FastAPI)       :8009
├── Airflow UI   (Webserver)     :8080  ← nouveau
│
├── PostgreSQL                   :5434
│   ├── crypto_bot_db            ← base applicative
│   └── airflow                  ← base Airflow (créée au 1er boot)
│
├── MongoDB                      :27017
└── MinIO (S3)                   :9000
```

---

## Contexte

Airflow a été ajouté pour orchestrer les pipelines de données du bot de trading : collecte de prix, génération de signaux, et alimentation des modèles ML. Il remplace les scripts cron ad-hoc et offre une visibilité complète sur les exécutions.
