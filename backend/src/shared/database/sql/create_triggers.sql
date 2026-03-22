/*
=============================================================
TRIGGERS FOR AUTOMATIC TIMESTAMP UPDATES
=============================================================
*/

-- Note: MySQL syntax for triggers. For PostgreSQL, syntax would be different.

DELIMITER $$

CREATE TRIGGER tr_users_updated_at
    BEFORE UPDATE ON users
    FOR EACH ROW
BEGIN
    SET NEW.updated_at = CURRENT_TIMESTAMP;
END$$

CREATE TRIGGER tr_user_sessions_updated_at
    BEFORE UPDATE ON user_sessions
    FOR EACH ROW
BEGIN
    SET NEW.updated_at = CURRENT_TIMESTAMP;
END$$

CREATE TRIGGER tr_user_accounts_updated_at
    BEFORE UPDATE ON user_accounts
    FOR EACH ROW
BEGIN
    SET NEW.updated_at = CURRENT_TIMESTAMP;
END$$

CREATE TRIGGER tr_user_settings_updated_at
    BEFORE UPDATE ON user_settings
    FOR EACH ROW
BEGIN
    SET NEW.updated_at = CURRENT_TIMESTAMP;
END$$

CREATE TRIGGER tr_strategies_updated_at
    BEFORE UPDATE ON strategies
    FOR EACH ROW
BEGIN
    SET NEW.updated_at = CURRENT_TIMESTAMP;
END$$

CREATE TRIGGER tr_strategy_deployments_updated_at
    BEFORE UPDATE ON strategy_deployments
    FOR EACH ROW
BEGIN
    SET NEW.updated_at = CURRENT_TIMESTAMP;
END$$

CREATE TRIGGER tr_strategy_states_updated_at
    BEFORE UPDATE ON strategy_states
    FOR EACH ROW
BEGIN
    SET NEW.updated_at = CURRENT_TIMESTAMP;
END$$

CREATE TRIGGER tr_trading_sessions_updated_at
    BEFORE UPDATE ON trading_sessions
    FOR EACH ROW
BEGIN
    SET NEW.updated_at = CURRENT_TIMESTAMP;
END$$

CREATE TRIGGER tr_backtest_results_updated_at
    BEFORE UPDATE ON backtest_results
    FOR EACH ROW
BEGIN
    SET NEW.updated_at = CURRENT_TIMESTAMP;
END$$

CREATE TRIGGER tr_orders_updated_at
    BEFORE UPDATE ON orders
    FOR EACH ROW
BEGIN
    SET NEW.updated_at = CURRENT_TIMESTAMP;
END$$

DELIMITER ;