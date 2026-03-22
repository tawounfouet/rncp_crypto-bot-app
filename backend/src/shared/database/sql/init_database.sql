/*
=============================================================
Crypto Trading Bot Database Initialization Script
=============================================================
Script Purpose:
    This script creates the complete database schema for the Crypto Trading Bot application.
    It includes all tables, indexes, triggers, views and relationships needed for:
    - User management and authentication
    - Trading strategies and deployments  
    - Order management with Binance API compatibility
    - Market data storage
    - Performance tracking and analytics
    
Database Structure:
    - 13 main tables with proper relationships
    - Optimized indexes for performance
    - Automated timestamp triggers
    - Views for analytics and reporting
    - JSON fields for flexible configuration storage

WARNING:
    This script will drop the entire 'crypto_trading_bot' database if it exists.
    All data in the database will be permanently deleted. Ensure you have proper 
    backups before running this script in production.

Author: Crypto Trading Bot Team
Version: 1.0
Date: July 2025
=============================================================
*/

-- Drop database if exists and create new one
DROP DATABASE IF EXISTS crypto_trading_bot;
CREATE DATABASE crypto_trading_bot;
USE crypto_trading_bot;

-- Enable UUID support (if using MySQL 8.0+)
-- For PostgreSQL, this would be: CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

/*
=============================================================
CORE TABLES - User Management
=============================================================
*/

-- Users table - Core user information
CREATE TABLE users (
    id VARCHAR(36) PRIMARY KEY DEFAULT (UUID()),
    email VARCHAR(255) UNIQUE NOT NULL,
    username VARCHAR(100) UNIQUE NOT NULL,
    first_name VARCHAR(100),
    last_name VARCHAR(100),
    hashed_password VARCHAR(255) NOT NULL,
    is_active BOOLEAN DEFAULT TRUE,
    is_admin BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    
    INDEX idx_users_email (email),
    INDEX idx_users_username (username),
    INDEX idx_users_active (is_active),
    INDEX idx_users_created (created_at)
);

-- User sessions table - Authentication and session management
CREATE TABLE user_sessions (
    id VARCHAR(36) PRIMARY KEY DEFAULT (UUID()),
    user_id VARCHAR(36) NOT NULL,
    token VARCHAR(255) UNIQUE NOT NULL,
    expires_at TIMESTAMP NOT NULL,
    ip_address VARCHAR(45),
    user_agent TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    INDEX idx_sessions_user (user_id),
    INDEX idx_sessions_token (token),
    INDEX idx_sessions_expires (expires_at)
);

-- User accounts table - Multiple auth providers (OAuth, credentials)
CREATE TABLE user_accounts (
    id VARCHAR(36) PRIMARY KEY DEFAULT (UUID()),
    user_id VARCHAR(36) NOT NULL,
    provider VARCHAR(50) NOT NULL DEFAULT 'credentials',
    provider_id VARCHAR(100),
    account_id VARCHAR(255) NOT NULL,
    scope VARCHAR(1024),
    access_token VARCHAR(1024),
    refresh_token VARCHAR(1024),
    access_token_expires_at TIMESTAMP,
    refresh_token_expires_at TIMESTAMP,
    password VARCHAR(255),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    UNIQUE KEY uq_user_provider_provider_id (user_id, provider, provider_id),
    INDEX idx_accounts_user (user_id),
    INDEX idx_accounts_account_id (account_id)
);

-- User settings table - Preferences and configuration
CREATE TABLE user_settings (
    id VARCHAR(36) PRIMARY KEY DEFAULT (UUID()),
    user_id VARCHAR(36) UNIQUE NOT NULL,
    theme VARCHAR(20) DEFAULT 'light',
    notification_preferences JSON DEFAULT ('{"email": true, "push": false}'),
    risk_profile VARCHAR(20) DEFAULT 'moderate',
    api_keys JSON,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    INDEX idx_settings_user (user_id)
);

/*
=============================================================
STRATEGY MANAGEMENT TABLES
=============================================================
*/

-- Strategies table - Trading strategy definitions
CREATE TABLE strategies (
    id VARCHAR(36) PRIMARY KEY DEFAULT (UUID()),
    user_id VARCHAR(36) NOT NULL,
    name VARCHAR(200) NOT NULL,
    description TEXT,
    strategy_type VARCHAR(100) NOT NULL,
    parameters JSON NOT NULL,
    asset_class VARCHAR(50) NOT NULL DEFAULT 'crypto',
    is_public BOOLEAN DEFAULT FALSE,
    is_active BOOLEAN DEFAULT TRUE,
    version VARCHAR(20) DEFAULT '1.0',
    parameter_hash VARCHAR(64),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    INDEX idx_strategies_user (user_id),
    INDEX idx_strategies_type (strategy_type),
    INDEX idx_strategies_public (is_public),
    INDEX idx_strategies_active (is_active),
    INDEX idx_strategies_asset_class (asset_class)
);

-- Strategy deployments table - Live trading instances
CREATE TABLE strategy_deployments (
    id VARCHAR(36) PRIMARY KEY DEFAULT (UUID()),
    strategy_id VARCHAR(36) NOT NULL,
    user_id VARCHAR(36) NOT NULL,
    exchange VARCHAR(50) NOT NULL,
    symbol VARCHAR(20) NOT NULL,
    timeframe VARCHAR(10) NOT NULL,
    amount DECIMAL(20,8) NOT NULL,
    parameters JSON,
    status VARCHAR(20) NOT NULL DEFAULT 'active',
    start_time TIMESTAMP NOT NULL,
    end_time TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    
    FOREIGN KEY (strategy_id) REFERENCES strategies(id) ON DELETE CASCADE,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    INDEX idx_deployments_strategy (strategy_id),
    INDEX idx_deployments_user (user_id),
    INDEX idx_deployments_exchange (exchange),
    INDEX idx_deployments_symbol (symbol),
    INDEX idx_deployments_status (status),
    INDEX idx_deployments_timeframe (timeframe)
);

-- Strategy states table - Real-time strategy tracking
CREATE TABLE strategy_states (
    id VARCHAR(36) PRIMARY KEY DEFAULT (UUID()),
    deployment_id VARCHAR(36) UNIQUE NOT NULL,
    user_id VARCHAR(36) NOT NULL,
    position VARCHAR(20),
    position_size DECIMAL(20,8) DEFAULT 0,
    entry_price DECIMAL(20,8),
    entry_time TIMESTAMP,
    total_trades INT DEFAULT 0,
    winning_trades INT DEFAULT 0,
    losing_trades INT DEFAULT 0,
    total_profit_loss DECIMAL(20,8) DEFAULT 0,
    cumulative_profit_loss DECIMAL(20,8) DEFAULT 0,
    max_drawdown DECIMAL(20,8) DEFAULT 0,
    is_active BOOLEAN DEFAULT TRUE,
    last_signal VARCHAR(10),
    last_signal_time TIMESTAMP,
    last_price DECIMAL(20,8),
    last_update TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    
    FOREIGN KEY (deployment_id) REFERENCES strategy_deployments(id) ON DELETE CASCADE,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    INDEX idx_states_deployment (deployment_id),
    INDEX idx_states_user (user_id),
    INDEX idx_states_position (position),
    INDEX idx_states_active (is_active)
);

-- Trading sessions table - Session tracking and analytics
CREATE TABLE trading_sessions (
    id VARCHAR(36) PRIMARY KEY DEFAULT (UUID()),
    deployment_id VARCHAR(36) NOT NULL,
    user_id VARCHAR(36) NOT NULL,
    start_time TIMESTAMP NOT NULL,
    end_time TIMESTAMP,
    duration_seconds INT,
    initial_balance DECIMAL(20,8) NOT NULL,
    final_balance DECIMAL(20,8),
    max_trades INT,
    total_trades INT DEFAULT 0,
    profitable_trades INT DEFAULT 0,
    total_profit_loss DECIMAL(20,8) DEFAULT 0,
    win_rate DECIMAL(5,4),
    status VARCHAR(20) NOT NULL DEFAULT 'ACTIVE',
    stop_reason VARCHAR(100),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    
    FOREIGN KEY (deployment_id) REFERENCES strategy_deployments(id) ON DELETE CASCADE,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    INDEX idx_sessions_deployment (deployment_id),
    INDEX idx_sessions_user (user_id),
    INDEX idx_sessions_status (status),
    INDEX idx_sessions_start_time (start_time)
);

-- Backtest results table - Historical strategy testing
CREATE TABLE backtest_results (
    id VARCHAR(36) PRIMARY KEY DEFAULT (UUID()),
    strategy_id VARCHAR(36) NOT NULL,
    user_id VARCHAR(36) NOT NULL,
    symbol VARCHAR(20) NOT NULL,
    timeframe VARCHAR(10) NOT NULL,
    start_date TIMESTAMP NOT NULL,
    end_date TIMESTAMP NOT NULL,
    parameters JSON,
    results JSON NOT NULL,
    metrics JSON NOT NULL,
    transactions JSON,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    
    FOREIGN KEY (strategy_id) REFERENCES strategies(id) ON DELETE CASCADE,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    INDEX idx_backtests_strategy (strategy_id),
    INDEX idx_backtests_user (user_id),
    INDEX idx_backtests_symbol (symbol),
    INDEX idx_backtests_timeframe (timeframe),
    INDEX idx_backtests_dates (start_date, end_date)
);

/*
=============================================================
TRADING AND ORDER MANAGEMENT TABLES
=============================================================
*/

-- Orders table - Binance API compatible order tracking
CREATE TABLE orders (
    id VARCHAR(36) PRIMARY KEY DEFAULT (UUID()),
    deployment_id VARCHAR(36) NOT NULL,
    user_id VARCHAR(36) NOT NULL,
    exchange VARCHAR(50) NOT NULL,
    exchange_order_id VARCHAR(100),
    client_order_id VARCHAR(100),
    order_list_id VARCHAR(100) DEFAULT '-1',
    symbol VARCHAR(20) NOT NULL,
    order_type VARCHAR(20) NOT NULL,
    side VARCHAR(10) NOT NULL,
    time_in_force VARCHAR(10),
    quantity DECIMAL(20,8) NOT NULL,
    executed_quantity DECIMAL(20,8) DEFAULT 0,
    quote_order_quantity DECIMAL(20,8),
    cumulative_quote_quantity DECIMAL(20,8),
    price DECIMAL(20,8),
    stop_price DECIMAL(20,8),
    status VARCHAR(20) NOT NULL DEFAULT 'NEW',
    self_trade_prevention_mode VARCHAR(20),
    transact_time TIMESTAMP,
    working_time TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    
    FOREIGN KEY (deployment_id) REFERENCES strategy_deployments(id) ON DELETE CASCADE,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    INDEX idx_orders_deployment (deployment_id),
    INDEX idx_orders_user (user_id),
    INDEX idx_orders_exchange (exchange),
    INDEX idx_orders_exchange_order_id (exchange_order_id),
    INDEX idx_orders_symbol (symbol),
    INDEX idx_orders_status (status),
    INDEX idx_orders_side (side),
    INDEX idx_orders_created (created_at)
);

-- Order fills table - Partial execution tracking
CREATE TABLE order_fills (
    id VARCHAR(36) PRIMARY KEY DEFAULT (UUID()),
    order_id VARCHAR(36) NOT NULL,
    trade_id VARCHAR(100) NOT NULL,
    price DECIMAL(20,8) NOT NULL,
    quantity DECIMAL(20,8) NOT NULL,
    commission DECIMAL(20,8) NOT NULL,
    commission_asset VARCHAR(20) NOT NULL,
    timestamp TIMESTAMP NOT NULL,
    is_buyer BOOLEAN,
    is_maker BOOLEAN,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    FOREIGN KEY (order_id) REFERENCES orders(id) ON DELETE CASCADE,
    INDEX idx_fills_order (order_id),
    INDEX idx_fills_trade_id (trade_id),
    INDEX idx_fills_timestamp (timestamp)
);

-- Transactions table - Financial movements tracking
CREATE TABLE transactions (
    id VARCHAR(36) PRIMARY KEY DEFAULT (UUID()),
    user_id VARCHAR(36) NOT NULL,
    exchange VARCHAR(50) NOT NULL,
    transaction_type VARCHAR(20) NOT NULL,
    order_id VARCHAR(36),
    asset VARCHAR(20) NOT NULL,
    amount DECIMAL(20,8) NOT NULL,
    direction VARCHAR(10) NOT NULL,
    quote_asset VARCHAR(20),
    quote_amount DECIMAL(20,8),
    price DECIMAL(20,8),
    fee_amount DECIMAL(20,8),
    fee_asset VARCHAR(20),
    external_id VARCHAR(100),
    status VARCHAR(20) NOT NULL DEFAULT 'COMPLETED',
    description TEXT,
    timestamp TIMESTAMP NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (order_id) REFERENCES orders(id) ON DELETE SET NULL,
    INDEX idx_transactions_user (user_id),
    INDEX idx_transactions_type (transaction_type),
    INDEX idx_transactions_asset (asset),
    INDEX idx_transactions_direction (direction),
    INDEX idx_transactions_timestamp (timestamp),
    INDEX idx_transactions_external_id (external_id)
);

/*
=============================================================
MARKET DATA TABLE
=============================================================
*/

-- Market data table - OHLCV data storage
CREATE TABLE market_data (
    id VARCHAR(36) PRIMARY KEY DEFAULT (UUID()),
    symbol VARCHAR(20) NOT NULL,
    exchange VARCHAR(50) NOT NULL DEFAULT 'binance',
    interval_timeframe VARCHAR(10) NOT NULL,
    open_time TIMESTAMP NOT NULL,
    open_price DECIMAL(20,8) NOT NULL,
    high_price DECIMAL(20,8) NOT NULL,
    low_price DECIMAL(20,8) NOT NULL,
    close_price DECIMAL(20,8) NOT NULL,
    volume DECIMAL(20,8) NOT NULL,
    close_time TIMESTAMP NOT NULL,
    quote_asset_volume DECIMAL(20,8),
    number_of_trades INT,
    taker_buy_base_volume DECIMAL(20,8),
    taker_buy_quote_volume DECIMAL(20,8),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    UNIQUE KEY uq_market_data_symbol_time (symbol, exchange, interval_timeframe, open_time),
    INDEX idx_market_data_symbol (symbol),
    INDEX idx_market_data_exchange (exchange),
    INDEX idx_market_data_interval (interval_timeframe),
    INDEX idx_market_data_open_time (open_time),
    INDEX idx_market_data_close_time (close_time)
);



/*
=============================================================
INDEXES FOR PERFORMANCE OPTIMIZATION
=============================================================
*/

-- Composite indexes for common queries
CREATE INDEX idx_orders_user_symbol_date ON orders(user_id, symbol, created_at);
CREATE INDEX idx_deployments_user_status ON strategy_deployments(user_id, status);
CREATE INDEX idx_transactions_user_type_date ON transactions(user_id, transaction_type, timestamp);
CREATE INDEX idx_market_data_symbol_interval_time ON market_data(symbol, interval_timeframe, open_time);

-- Full-text search indexes (if supported)
-- CREATE FULLTEXT INDEX idx_strategies_search ON strategies(name, description);

/*
=============================================================
SCRIPT COMPLETION
=============================================================
*/



-- Verify table creation
SELECT 
    TABLE_NAME,
    TABLE_ROWS,
    CREATE_TIME
FROM information_schema.TABLES 
WHERE TABLE_SCHEMA = 'crypto_trading_bot'
ORDER BY TABLE_NAME;