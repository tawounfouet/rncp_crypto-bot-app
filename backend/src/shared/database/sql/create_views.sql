
/*
=============================================================
VIEWS FOR ANALYTICS AND REPORTING
=============================================================
*/

-- User statistics view
CREATE VIEW v_user_statistics AS
SELECT 
    u.id,
    u.username,
    u.email,
    u.created_at as user_since,
    COUNT(DISTINCT s.id) as total_strategies,
    COUNT(DISTINCT sd.id) as total_deployments,
    COUNT(DISTINCT o.id) as total_orders,
    COALESCE(SUM(CASE WHEN t.direction = 'IN' THEN t.amount ELSE -t.amount END), 0) as net_balance,
    COUNT(DISTINCT br.id) as total_backtests
FROM users u
LEFT JOIN strategies s ON u.id = s.user_id
LEFT JOIN strategy_deployments sd ON u.id = sd.user_id
LEFT JOIN orders o ON u.id = o.user_id
LEFT JOIN transactions t ON u.id = t.user_id AND t.transaction_type = 'TRADE'
LEFT JOIN backtest_results br ON u.id = br.user_id
GROUP BY u.id, u.username, u.email, u.created_at;

-- Strategy performance view
CREATE VIEW v_strategy_performance AS
SELECT 
    s.id,
    s.name,
    s.strategy_type,
    s.user_id,
    u.username,
    COUNT(DISTINCT sd.id) as deployment_count,
    COUNT(DISTINCT o.id) as total_orders,
    COALESCE(AVG(ss.total_profit_loss), 0) as avg_profit_loss,
    COALESCE(AVG(ss.win_rate), 0) as avg_win_rate,
    MAX(ss.max_drawdown) as max_drawdown,
    s.created_at
FROM strategies s
JOIN users u ON s.user_id = u.id
LEFT JOIN strategy_deployments sd ON s.id = sd.strategy_id
LEFT JOIN strategy_states ss ON sd.id = ss.deployment_id
LEFT JOIN orders o ON sd.id = o.deployment_id
GROUP BY s.id, s.name, s.strategy_type, s.user_id, u.username, s.created_at;

-- Active deployments view
CREATE VIEW v_active_deployments AS
SELECT 
    sd.id,
    sd.exchange,
    sd.symbol,
    sd.timeframe,
    sd.status,
    s.name as strategy_name,
    s.strategy_type,
    u.username,
    ss.position,
    ss.position_size,
    ss.total_profit_loss,
    ss.last_signal,
    ss.last_signal_time,
    sd.start_time,
    sd.created_at
FROM strategy_deployments sd
JOIN strategies s ON sd.strategy_id = s.id
JOIN users u ON sd.user_id = u.id
LEFT JOIN strategy_states ss ON sd.id = ss.deployment_id
WHERE sd.status = 'active' AND sd.end_time IS NULL;

-- Trading activity summary view
CREATE VIEW v_trading_activity AS
SELECT 
    DATE(o.created_at) as trading_date,
    o.exchange,
    o.symbol,
    COUNT(*) as total_orders,
    COUNT(CASE WHEN o.side = 'BUY' THEN 1 END) as buy_orders,
    COUNT(CASE WHEN o.side = 'SELL' THEN 1 END) as sell_orders,
    COUNT(CASE WHEN o.status = 'FILLED' THEN 1 END) as filled_orders,
    SUM(o.executed_quantity) as total_volume,
    COUNT(DISTINCT o.user_id) as active_users
FROM orders o
GROUP BY DATE(o.created_at), o.exchange, o.symbol
ORDER BY trading_date DESC;