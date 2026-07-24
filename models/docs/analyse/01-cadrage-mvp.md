# Cadrage MVP — CryptoBot Models Training

Date : 2026-06-01

## Hypothèse à valider

Le MVP doit valider qu'un flux automatisé de données crypto peut produire, avec une latence maîtrisée, un signal exploitable `BUY`, `SELL` ou `HOLD` sur un périmètre restreint.

L'hypothèse n'est pas encore : "le bot gagne durablement de l'argent". L'hypothèse MVP est plus sobre :

> Si la donnée est collectée proprement, transformée de manière reproductible et servie rapidement, alors l'équipe peut comparer objectivement des modèles simples et préparer une décision d'industrialisation.

## Périmètre prioritaire

| Domaine | Inclus MVP | Exclu MVP |
|---|---|---|
| Données | `BTCUSDT`, `BTCETH`, OHLCV, intervalle principal `1h` | Multi-exchange, carnets d'ordres, sentiment, news |
| Modèles | Random Forest baseline, LSTM séquentiel | Reinforcement learning, Transformers, ensembles avancés |
| Signal | `BUY`, `SELL`, `HOLD`, score de confiance simple | Exécution d'ordres, sizing de position, arbitrage |
| API | Healthcheck, dernier signal, prédiction ponctuelle | Streaming temps réel, WebSocket, backtesting complet via API |
| MLOps | tracking local MLflow, run id, métriques, artefacts, model card, registry local | registry distant, retraining automatique, déploiement continu de modèle |
| Infra | exécution locale et Docker simple | Kafka, Airflow, Kubernetes dédiés au MVP modèle |

## Justification

Les analyses des labs précédents montrent une constante : l'architecture devient vite plus ambitieuse que la valeur livrée. Plusieurs projets possèdent Docker, monitoring, scheduler, Kafka, Airflow ou Kubernetes, mais des éléments essentiels restent fragiles : tests absents, scalers non persistés, endpoints de prédiction factices, modèles multi-sorties incompatibles avec le trainer.

Le MVP doit donc inverser la priorité :

1. Un flux de données fiable.
2. Un contrat de features et labels stable.
3. Un modèle baseline mesurable.
4. Un suivi MLOps minimal mais systématique.
5. Une API rapide.
6. Une documentation qui explique les limites.

## KPI MVP

| KPI | Cible MVP | Pourquoi |
|---|---:|---|
| Latence API hors collecte externe | `< 300 ms` p95 | Le signal doit être fluide pour le backend et le dashboard |
| Taux de bougies valides | `>= 99 %` sur dataset collecté | Les modèles sont inutiles si la donnée OHLCV est instable |
| Fraîcheur des données | dernière bougie disponible selon intervalle | Permet d'éviter un signal construit sur des données périmées |
| `f1_macro` signal | supérieur au baseline naïf | Mesure mieux les classes minoritaires que l'accuracy seule |
| Directional accuracy | supérieure au hasard sur test temporel | Vérifie la pertinence directionnelle |
| Traçabilité des runs | 100 % des entraînements avec config, métriques, artefacts | L'équipe doit comparer et rejouer les expériences |
| Couverture tests cœur | `>= 60 %` sur data/features/models API | Le MVP doit être démontrable et maintenable |

## Personas et besoins

| Persona | Besoin | Réponse MVP |
|---|---|---|
| Data engineer | Construire un flux fiable et reproductible | collecte, validation qualité, formats raw/processed, contrats de données |
| Data scientist | Comparer rapidement deux approches de modèle | Random Forest comme baseline, LSTM comme modèle séquentiel |
| Machine learning engineer | Industrialiser l'entraînement et tracer les runs | MLflow local, artefacts complets, registry local, model card |
| Backend engineer | Consommer un signal stable | Contrat API documenté et réponse typée |
| Product owner | Comprendre ce qui est validé | KPI lisibles, exclusions assumées |
| Évaluateur Datascientest | Voir une chaîne data complète | collecte, preprocessing, entraînement, API, tests, docs |

## Définition du signal

Le signal est une recommandation technique, pas un conseil financier.

| Signal | Sens métier MVP | Exemple de règle de label initiale |
|---|---|---|
| `BUY` | probabilité de hausse suffisante | rendement futur > seuil positif |
| `SELL` | probabilité de baisse suffisante | rendement futur < seuil négatif |
| `HOLD` | incertitude ou variation faible | rendement futur entre les seuils |

La règle de labellisation doit rester simple, documentée et versionnée. Le seuil initial recommandé est basé sur la volatilité récente ou, plus simplement pour démarrer, sur un seuil fixe de rendement futur.

## Critères de sortie du MVP

Le MVP est terminé quand l'équipe peut montrer :

- un script de collecte qui produit un dataset pour `BTCUSDT` et `BTCETH`
- un pipeline de features sans fuite de données entre train et test
- un Random Forest et un LSTM entraînés sur un split temporel
- une comparaison métrique des deux modèles
- un tracking MLOps local avec paramètres, métriques, artefacts et model card
- un endpoint API qui retourne le dernier signal avec métadonnées
- un plan clair des limites et extensions post-MVP
