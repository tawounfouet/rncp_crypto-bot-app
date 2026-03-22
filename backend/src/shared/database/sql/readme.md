

# 📊 Structure de la Base de Données

## 🔐 Gestion des Utilisateurs (4 tables)
- `users` : Informations principales des utilisateurs
- `user_sessions` : Gestion des sessions et tokens
- `user_accounts` : Support OAuth et authentification multiple
- `user_settings` : Préférences et configuration utilisateur

## 🎯 Gestion des Stratégies (5 tables)
- `strategies` : Définitions des stratégies de trading
- `strategy_deployments` : Instances de trading en direct
- `strategy_states` : Suivi en temps réel des stratégies
- `trading_sessions` : Sessions de trading et analytics
- `backtest_results` : Résultats des tests historiques

## 📈 Trading et Ordres (3 tables)
- `orders` : Ordres compatibles API Binance
- `order_fills` : Exécutions partielles des ordres
- `transactions` : Mouvements financiers complets

## 📊 Données de Marché (1 table)
- `market_data` : Données OHLCV historiques


## 🚀 Fonctionnalités Avancées

### ⚡ Performance
- Index optimisés pour les requêtes fréquentes
- Index composites pour les requêtes complexes
- Contraintes uniques pour éviter les doublons

### 🔄 Automatisation
- Triggers automatiques pour les timestamps updated_at
- UUID par défaut pour tous les IDs
- Cascade approprié pour les suppressions

### 📊 Analytics
- 4 vues prédéfinies pour les statistiques :
- `v_user_statistics` - Statistiques utilisateur
- `v_strategy_performance` - Performance des stratégies
- `v_active_deployments` - Déploiements actifs
- `v_trading_activity` - Activité de trading

### 🔗 Compatibilité API Binance
- Champs exchange_order_id, client_order_id
- Support des order fills avec commissions
- Statuts d'ordres conformes à Binance
- Gestion des time_in_force et self_trade_prevention

## 💡 Points Clés
- Évolutivité : Architecture modulaire par domaines
- Sécurité : Clés étrangères avec CASCADE approprié
- Flexibilité : Champs JSON pour paramètres configurables
- Performance : Index optimisés pour les requêtes critiques
- Audit : Timestamps automatiques sur toutes les tables
