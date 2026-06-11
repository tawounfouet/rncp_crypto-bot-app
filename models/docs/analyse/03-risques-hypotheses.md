# Risques et hypothèses

## Hypothèses de départ

| Hypothèse | Impact si fausse | Validation MVP |
|---|---|---|
| Les données Binance suffisent pour un premier signal | Le modèle manque de contexte marché | Comparer modèle vs baseline naïf |
| `BTCUSDT` et `BTCETH` couvrent un cas utile | MVP trop étroit pour la soutenance | Montrer la généricité du collecteur |
| Un intervalle `1h` est un bon compromis | Signal trop lent ou trop bruité | Prévoir `15m` et `4h` en extension |
| Random Forest fournit une baseline lisible | Baseline trop faible ou instable | Mesurer f1_macro et matrice de confusion |
| LSTM capte une dynamique temporelle utile | Complexité non justifiée | Comparaison métrique stricte avec Random Forest |

## Risques data

| Risque | Sévérité | Prévention MVP |
|---|---|---|
| Bougies manquantes | Haute | contrôle continuité temporelle par symbole et intervalle |
| Données dupliquées | Moyenne | clé unique logique `symbol`, `interval`, `open_time` |
| Data leakage | Haute | split temporel avant scaler, scaler fit uniquement sur train |
| Différence de formats Binance | Moyenne | mapping explicite kline -> schéma interne |
| Donnée périmée | Haute | `data_freshness_seconds` dans la réponse signal |

## Risques ML

| Risque | Sévérité | Prévention MVP |
|---|---|---|
| Classe `HOLD` dominante | Haute | matrice de confusion, f1_macro, analyse distribution labels |
| Overfitting LSTM | Haute | early stopping, validation temporelle, dropout raisonnable |
| Signal instable | Moyenne | seuil minimal de confiance et comparaison avec signal précédent |
| Métrique trompeuse | Haute | ne pas utiliser accuracy seule |
| Artefact incomplet | Haute | sauvegarder modèle + scaler + features + config + métriques |

## Risques API

| Risque | Sévérité | Prévention MVP |
|---|---|---|
| Latence excessive | Haute | chargement modèle au démarrage, pas de collecte réseau dans `/signals/latest` |
| Erreur silencieuse | Haute | erreurs typées, healthcheck incluant modèle et dataset |
| Réponse non contractuelle | Moyenne | schéma Pydantic documenté |
| Modèle absent | Moyenne | endpoint health en `degraded`, message explicite |

## Risques métier

| Risque | Sévérité | Prévention MVP |
|---|---|---|
| Confusion entre signal et conseil financier | Haute | disclaimer dans docs et API |
| Attente de gains garantis | Haute | KPI de validation technique séparés des gains |
| Surinterprétation d'un backtest court | Moyenne | documenter période, split, limites |
| Passage trop tôt au trading réel | Haute | trading réel explicitement hors MVP |

## Risques conformité et sécurité

Le MVP ne doit pas exécuter d'ordres ni gérer de portefeuille. Il limite ainsi les risques réglementaires et financiers. Avant toute mise en production réelle, le cadre légal applicable au pays cible, les obligations liées aux crypto-actifs, les disclaimers utilisateur et la gestion des clés API devront être vérifiés par une personne compétente.

Pour le MVP :

- pas de clé Binance obligatoire pour les données publiques si l'API publique suffit
- aucune clé secrète en dépôt
- `.env.example` uniquement
- testnet uniquement si une clé est nécessaire
- aucune promesse de rendement dans l'interface ou la documentation

## Risques RSE et accessibilité

| Sujet | Mesure MVP |
|---|---|
| Sobriété calcul | modèles légers, dataset limité, pas de GPU obligatoire |
| Explicabilité | baseline Random Forest + importance de features |
| Inclusion | documentation claire, commandes reproductibles |
| Handicap | livrables textuels lisibles, éviter les informations portées seulement par couleur |

## Décision de pilotage

Le MVP doit avancer uniquement si les signaux de santé suivants restent verts :

- collecte reproductible
- tests data/features OK
- métriques modèle supérieures au baseline naïf
- API rapide sans appel réseau dans le chemin critique
- artefacts complets et rechargeables
