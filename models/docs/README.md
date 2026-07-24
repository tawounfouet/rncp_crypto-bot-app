# Documentation — Models Training MVP

Ce dossier centralise les documents de décision et de mise en œuvre de la couche modèles du CryptoBot v2.

## Objectif

Créer une base documentaire claire avant l'implémentation du MVP :

- expliquer pourquoi le périmètre est limité à `BTCUSDT` et `BTCETH`
- capitaliser sur les labs précédents sans reprendre leur complexité inutile
- spécifier les contrats de données, modèles, signaux et API
- donner un guide d'implémentation directement exploitable par l'équipe

## Index

### Configuration

| Document | Rôle |
|---|---|
| [../config.yaml](../config.yaml) | Configuration centrale du MVP |

### Analyse

| Document | Rôle |
|---|---|
| [analyse/01-cadrage-mvp.md](analyse/01-cadrage-mvp.md) | Cadrage produit, hypothèse, KPI et périmètre |
| [analyse/02-retour-experience-labs.md](analyse/02-retour-experience-labs.md) | Ce qu'on reprend et ce qu'on écarte des anciens labs |
| [analyse/03-risques-hypotheses.md](analyse/03-risques-hypotheses.md) | Risques data, ML, API, métier et conformité |

### Spécifications

| Document | Rôle |
|---|---|
| [specs/01-specifications-fonctionnelles.md](specs/01-specifications-fonctionnelles.md) | Fonctionnalités MVP et exclusions |
| [specs/02-architecture-data-ml.md](specs/02-architecture-data-ml.md) | Architecture cible data + ML |
| [specs/03-contrats-donnees-api.md](specs/03-contrats-donnees-api.md) | Schémas de données, signaux et endpoints |

### Implémentation

| Document | Rôle |
|---|---|
| [implementation/01-guide-implementation.md](implementation/01-guide-implementation.md) | Guide de construction progressif du MVP |
| [implementation/02-roadmap-livrables.md](implementation/02-roadmap-livrables.md) | Roadmap courte, livrables et jalons |
| [implementation/03-plan-tests-validation.md](implementation/03-plan-tests-validation.md) | Stratégie de tests et critères d'acceptation |

## Principe directeur

Le MVP ne cherche pas à prouver qu'un modèle complexe peut battre le marché. Il cherche d'abord à prouver que l'équipe sait construire une chaîne fiable, mesurable et rapide :

```text
donnée fiable -> features explicables -> modèle simple -> signal traçable -> API rapide
```
