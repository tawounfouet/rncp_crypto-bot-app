# Architecture de la Base de Données - Crypto Trading Bot

Statut: référence
Derniere revision: 2026-04-03

## 📋 Vue d'Ensemble

Cette documentation présente l'architecture complète de la base de données du bot de trading crypto. L'architecture suit une approche modulaire organisée par domaines métier, optimisée pour les performances et la scalabilité.

### 🎯 Objectifs de l'Architecture

- **Modulaire** : Séparation claire des domaines métier
- **Scalable** : Optimisée pour la croissance des données
- **Compatible** : Intégration native avec l'API Binance
- **Performante** : Index optimisés pour les requêtes critiques
- **Sécurisée** : Contraintes et validations appropriées

---

## 🏗️ Diagramme Global de l'Architecture

```mermaid
graph TB
    subgraph "USER DOMAIN"
        U[users]
        US[user_sessions]
        UA[user_accounts]
        UST[user_settings]
    end
    
    subgraph "STRATEGY DOMAIN"
        S[strategies]
        SD[strategy_deployments]
        SS[strategy_states]
        TS[trading_sessions]
        BR[backtest_results]
    end
    
    subgraph "TRADING DOMAIN"
        O[orders]
        OF[order_fills]
        T[transactions]
    end
    
    subgraph "MARKET DATA"
        MD[market_data]
    end
    
    subgraph "ANALYTICS VIEWS"
        V1[v_user_statistics]
        V2[v_strategy_performance]
        V3[v_active_deployments]
        V4[v_trading_activity]
    end
    
    %% Relations principales
    U --> US
    U --> UA
    U --> UST
    U --> S
    U --> SD
    U --> SS
    U --> TS
    U --> BR
    U --> O
    U --> T
    
    S --> SD
    S --> BR
    SD --> SS
    SD --> TS
    SD --> O
    
    O --> OF
    O --> T
    
    %% Vers les vues
    U -.-> V1
    S -.-> V2
    SD -.-> V3
    O -.-> V4
    
    classDef userDomain fill:#e1f5fe
    classDef strategyDomain fill:#f3e5f5
    classDef tradingDomain fill:#e8f5e8
    classDef marketData fill:#fff3e0
    classDef views fill:#fce4ec
    
    class U,US,UA,UST userDomain
    class S,SD,SS,TS,BR strategyDomain
    class O,OF,T tradingDomain
    class MD marketData
    class V1,V2,V3,V4 views
```

---

## 🔐 Domaine Utilisateurs (User Domain)

### Diagramme Relationnel

```mermaid
erDiagram
    users {
        varchar id PK
        varchar email UK
        varchar username UK
        varchar first_name
        varchar last_name
        varchar hashed_password
        boolean is_active
        boolean is_admin
        timestamp created_at
        timestamp updated_at
    }
    
    user_sessions {
        varchar id PK
        varchar user_id FK
        varchar token UK
        timestamp expires_at
        varchar ip_address
        text user_agent
        timestamp created_at
        timestamp updated_at
    }
    
    user_accounts {
        varchar id PK
        varchar user_id FK
        varchar provider
        varchar provider_id
        varchar account_id
        varchar scope
        varchar access_token
        varchar refresh_token
        timestamp access_token_expires_at
        timestamp refresh_token_expires_at
        varchar password
        timestamp created_at
        timestamp updated_at
    }
    
    user_settings {
        varchar id PK
        varchar user_id FK,UK
        varchar theme
        json notification_preferences
        varchar risk_profile
        json api_keys
        timestamp created_at
        timestamp updated_at
    }
    
    users ||--o{ user_sessions : "has"
    users ||--o{ user_accounts : "has"
    users ||--|| user_settings : "has"
```

### 📝 Description des Tables

#### `users` - Table Principale des Utilisateurs
- **Objectif** : Stockage des informations de base des utilisateurs
- **Champs clés** :
  - `email` / `username` : Identifiants uniques
  - `hashed_password` : Mot de passe chiffré
  - `is_active` / `is_admin` : Statuts et permissions

#### `user_sessions` - Gestion des Sessions
- **Objectif** : Gestion des tokens de session et sécurité
- **Champs clés** :
  - `token` : Token de session unique
  - `expires_at` : Expiration pour la sécurité
  - `ip_address` / `user_agent` : Traçabilité des connexions

#### `user_accounts` - Authentification Multiple
- **Objectif** : Support OAuth et providers externes
- **Champs clés** :
  - `provider` : 'credentials', 'google', 'github', etc.
  - `access_token` / `refresh_token` : Tokens OAuth

#### `user_settings` - Préférences Utilisateur
- **Objectif** : Configuration personnalisée
- **Champs clés** :
  - `theme` : Interface utilisateur
  - `notification_preferences` : JSON flexible
  - `api_keys` : Clés API chiffrées (Binance, etc.)

---

## 🎯 Domaine Stratégies (Strategy Domain)

### Diagramme Relationnel

```mermaid
erDiagram
    strategies {
        varchar id PK
        varchar user_id FK
        varchar name
        text description
        varchar strategy_type
        json parameters
        varchar asset_class
        boolean is_public
        boolean is_active
        varchar version
        varchar parameter_hash
        timestamp created_at
        timestamp updated_at
    }
    
    strategy_deployments {
        varchar id PK
        varchar strategy_id FK
        varchar user_id FK
        varchar exchange
        varchar symbol
        varchar timeframe
        decimal amount
        json parameters
        varchar status
        timestamp start_time
        timestamp end_time
        timestamp created_at
        timestamp updated_at
    }
    
    strategy_states {
        varchar id PK
        varchar deployment_id FK,UK
        varchar user_id FK
        varchar position
        decimal position_size
        decimal entry_price
        timestamp entry_time
        int total_trades
        int winning_trades
        int losing_trades
        decimal total_profit_loss
        decimal cumulative_profit_loss
        decimal max_drawdown
        boolean is_active
        varchar last_signal
        timestamp last_signal_time
        decimal last_price
        timestamp last_update
        timestamp created_at
        timestamp updated_at
    }
    
    trading_sessions {
        varchar id PK
        varchar deployment_id FK
        varchar user_id FK
        timestamp start_time
        timestamp end_time
        int duration_seconds
        decimal initial_balance
        decimal final_balance
        int max_trades
        int total_trades
        int profitable_trades
        decimal total_profit_loss
        decimal win_rate
        varchar status
        varchar stop_reason
        timestamp created_at
        timestamp updated_at
    }
    
    backtest_results {
        varchar id PK
        varchar strategy_id FK
        varchar user_id FK
        varchar symbol
        varchar timeframe
        timestamp start_date
        timestamp end_date
        json parameters
        json results
        json metrics
        json transactions
        timestamp created_at
        timestamp updated_at
    }
    
    users ||--o{ strategies : "creates"
    strategies ||--o{ strategy_deployments : "deployed_as"
    strategies ||--o{ backtest_results : "tested_as"
    strategy_deployments ||--|| strategy_states : "has_state"
    strategy_deployments ||--o{ trading_sessions : "runs_in"
    users ||--o{ strategy_deployments : "owns"
    users ||--o{ strategy_states : "monitors"
    users ||--o{ trading_sessions : "participates"
    users ||--o{ backtest_results : "runs"
```

### 📝 Description des Tables

#### `strategies` - Définitions des Stratégies
- **Objectif** : Templates de stratégies de trading
- **Champs clés** :
  - `strategy_type` : 'moving_average_crossover', 'rsi_reversal', etc.
  - `parameters` : Configuration JSON flexible
  - `parameter_hash` : Cache et versionning
  - `is_public` : Partage communautaire

#### `strategy_deployments` - Instances de Trading
- **Objectif** : Déploiements actifs des stratégies
- **Champs clés** :
  - `exchange` / `symbol` / `timeframe` : Contexte de marché
  - `amount` : Capital alloué
  - `status` : 'active', 'paused', 'stopped', 'error'

#### `strategy_states` - État en Temps Réel
- **Objectif** : Suivi en direct des performances
- **Champs clés** :
  - `position` : 'LONG', 'SHORT', 'NEUTRAL'
  - `total_profit_loss` / `max_drawdown` : Métriques de performance
  - `last_signal` : Dernier signal généré

#### `trading_sessions` - Sessions de Trading
- **Objectif** : Analytics et historique des sessions
- **Champs clés** :
  - `initial_balance` / `final_balance` : Évolution du capital
  - `win_rate` : Taux de réussite
  - `duration_seconds` : Durée des sessions

#### `backtest_results` - Tests Historiques
- **Objectif** : Validation des stratégies sur données historiques
- **Champs clés** :
  - `results` / `metrics` : Résultats complets JSON
  - `transactions` : Détail des trades simulés

---

## 📈 Domaine Trading (Trading Domain)

### Diagramme Relationnel

```mermaid
erDiagram
    orders {
        varchar id PK
        varchar deployment_id FK
        varchar user_id FK
        varchar exchange
        varchar exchange_order_id
        varchar client_order_id
        varchar order_list_id
        varchar symbol
        varchar order_type
        varchar side
        varchar time_in_force
        decimal quantity
        decimal executed_quantity
        decimal quote_order_quantity
        decimal cumulative_quote_quantity
        decimal price
        decimal stop_price
        varchar status
        varchar self_trade_prevention_mode
        timestamp transact_time
        timestamp working_time
        timestamp created_at
        timestamp updated_at
    }
    
    order_fills {
        varchar id PK
        varchar order_id FK
        varchar trade_id
        decimal price
        decimal quantity
        decimal commission
        varchar commission_asset
        timestamp timestamp
        boolean is_buyer
        boolean is_maker
        timestamp created_at
    }
    
    transactions {
        varchar id PK
        varchar user_id FK
        varchar exchange
        varchar transaction_type
        varchar order_id FK
        varchar asset
        decimal amount
        varchar direction
        varchar quote_asset
        decimal quote_amount
        decimal price
        decimal fee_amount
        varchar fee_asset
        varchar external_id
        varchar status
        text description
        timestamp timestamp
        timestamp created_at
    }
    
    strategy_deployments ||--o{ orders : "generates"
    users ||--o{ orders : "owns"
    orders ||--o{ order_fills : "filled_by"
    orders ||--o{ transactions : "creates"
    users ||--o{ transactions : "has"
```

### 📝 Description des Tables

#### `orders` - Ordres de Trading (Compatible Binance)
- **Objectif** : Gestion complète des ordres avec compatibilité API Binance
- **Champs clés** :
  - `exchange_order_id` / `client_order_id` : IDs Binance
  - `order_type` : 'MARKET', 'LIMIT', 'STOP_LOSS', etc.
  - `side` : 'BUY' / 'SELL'
  - `status` : 'NEW', 'FILLED', 'CANCELED', etc.
  - `executed_quantity` / `cumulative_quote_quantity` : Exécution

#### `order_fills` - Exécutions Partielles
- **Objectif** : Détail des fills pour ordres partiellement exécutés
- **Champs clés** :
  - `trade_id` : ID unique du trade Binance
  - `commission` / `commission_asset` : Frais détaillés
  - `is_buyer` / `is_maker` : Type d'exécution

#### `transactions` - Mouvements Financiers
- **Objectif** : Historique complet des transactions
- **Champs clés** :
  - `transaction_type` : 'TRADE', 'DEPOSIT', 'WITHDRAWAL', 'FEE'
  - `direction` : 'IN' / 'OUT'
  - `external_id` : Référence exchange

---

## 📊 Données de Marché (Market Data)

### Diagramme de la Table

```mermaid
erDiagram
    market_data {
        varchar id PK
        varchar symbol
        varchar exchange
        varchar interval_timeframe
        timestamp open_time
        decimal open_price
        decimal high_price
        decimal low_price
        decimal close_price
        decimal volume
        timestamp close_time
        decimal quote_asset_volume
        int number_of_trades
        decimal taker_buy_base_volume
        decimal taker_buy_quote_volume
        timestamp created_at
    }
```

### 📝 Description

#### `market_data` - Données OHLCV Historiques
- **Objectif** : Stockage des données de marché pour backtesting et analyse
- **Champs clés** :
  - **OHLCV** : `open_price`, `high_price`, `low_price`, `close_price`, `volume`
  - `interval_timeframe` : '1m', '5m', '15m', '1h', '4h', '1d'
  - **Données Binance** : `quote_asset_volume`, `taker_buy_*`
  - **Contrainte unique** : Évite les doublons par (symbol, exchange, timeframe, open_time)

---

## 📊 Vues Analytiques (Analytics Views)

### Structure des Vues

```mermaid
graph LR
    subgraph "Sources de Données"
        U[users]
        S[strategies]
        SD[strategy_deployments]
        SS[strategy_states]
        O[orders]
        T[transactions]
        BR[backtest_results]
    end
    
    subgraph "Vues Analytiques"
        V1[v_user_statistics]
        V2[v_strategy_performance]
        V3[v_active_deployments]
        V4[v_trading_activity]
    end
    
    U --> V1
    S --> V1
    SD --> V1
    O --> V1
    T --> V1
    BR --> V1
    
    S --> V2
    SD --> V2
    SS --> V2
    O --> V2
    
    SD --> V3
    S --> V3
    U --> V3
    SS --> V3
    
    O --> V4
    
    classDef source fill:#e3f2fd
    classDef view fill:#f1f8e9
    
    class U,S,SD,SS,O,T,BR source
    class V1,V2,V3,V4 view
```

### 📝 Description des Vues

#### `v_user_statistics` - Statistiques Utilisateur
```sql
-- Agrégation des données par utilisateur
- total_strategies, total_deployments, total_orders
- net_balance (basé sur les transactions)
- total_backtests
```

#### `v_strategy_performance` - Performance des Stratégies
```sql
-- Métriques de performance par stratégie
- deployment_count, total_orders
- avg_profit_loss, avg_win_rate, max_drawdown
```

#### `v_active_deployments` - Déploiements Actifs
```sql
-- Vue temps réel des stratégies actives
- Informations de déploiement + état + performance
- Filtrée sur status='active' et end_time IS NULL
```

#### `v_trading_activity` - Activité de Trading
```sql
-- Résumé quotidien de l'activité
- Par date/exchange/symbol
- Compteurs buy/sell/filled orders
- Volume total et utilisateurs actifs
```

---

## ⚡ Optimisations de Performance

### Index Principaux

```mermaid
graph TB
    subgraph "Index Simples"
        I1[users: email, username]
        I2[orders: symbol, status, side]
        I3[market_data: symbol, interval]
        I4[strategies: type, active]
    end
    
    subgraph "Index Composites"
        I5[orders: user_id + symbol + created_at]
        I6[deployments: user_id + status]
        I7[transactions: user_id + type + timestamp]
        I8[market_data: symbol + interval + open_time]
    end
    
    subgraph "Index Uniques"
        I9[users: email, username]
        I10[user_sessions: token]
        I11[market_data: symbol + exchange + interval + open_time]
    end
    
    classDef simple fill:#e8f5e8
    classDef composite fill:#fff3e0
    classDef unique fill:#fce4ec
    
    class I1,I2,I3,I4 simple
    class I5,I6,I7,I8 composite
    class I9,I10,I11 unique
```

### Contraintes et Triggers

#### Triggers Automatiques
- **updated_at** : Mise à jour automatique sur toutes les tables principales
- **UUID** : Génération automatique des IDs

#### Contraintes de Sécurité
- **Foreign Keys** avec CASCADE approprié
- **Unique Keys** pour éviter les doublons
- **Check Constraints** pour la validation des données

---

## 🔄 Flux de Données Principaux

### Flux de Trading

```mermaid
sequenceDiagram
    participant U as User
    participant S as Strategy
    participant D as Deployment
    participant O as Order
    participant E as Exchange
    
    U->>S: Crée stratégie
    U->>D: Déploie stratégie
    D->>O: Génère ordre
    O->>E: Envoie à Binance
    E-->>O: Confirmation + fills
    O->>D: Mise à jour état
    D->>S: Mise à jour métriques
```

### Flux d'Analytics

```mermaid
sequenceDiagram
    participant T as Tables
    participant V as Views
    participant A as Analytics
    participant D as Dashboard
    
    T->>V: Agrégation temps réel
    V->>A: Calculs métriques
    A->>D: Affichage utilisateur
    
    Note over T,V: Triggers automatiques
    Note over V,A: Vues pré-calculées
    Note over A,D: Cache intelligent
```

---

## 🚀 Évolutivité et Maintenance

### Stratégies de Scaling

1. **Partitioning** : Tables `market_data` et `orders` par date
2. **Archivage** : Données historiques anciennes
3. **Read Replicas** : Pour les analytics
4. **Caching** : Redis pour les données fréquentes

### Monitoring et Observabilité

1. **Métriques** : Via les vues analytiques
2. **Logs** : Audit des modifications
3. **Alertes** : Surveillance des performances
4. **Backups** : Stratégie de sauvegarde

---

## 📚 Conclusion

Cette architecture de base de données offre :

✅ **Modularité** : Domaines bien séparés  
✅ **Performance** : Index optimisés  
✅ **Compatibilité** : API Binance native  
✅ **Analytics** : Vues pré-calculées  
✅ **Sécurité** : Contraintes robustes  
✅ **Évolutivité** : Prête pour la croissance  

L'architecture est conçue pour supporter l'évolution du projet, de la phase de développement à la production en passant par les tests de charge.
