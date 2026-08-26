# Rapport de couverture de test

Snapshot du 2026-08-26 -- regenere a chaque `python3 scripts/track_coverage.py`
(ecrase le precedent, pas un historique -- voir `coverage_history.csv` pour l'evolution du %).

## Backend + utils (60.5%)

| Fichier | Lignes | Manquantes | % | Lignes non couvertes |
|---|---|---|---|---|
| backend/src/auth/purge_inactive_users.py | 4 | 4 | 0% | 1, 3, 4, 5 |
| backend/src/market/binance_testnet_router.py | 49 | 49 | 0% | 3, 5, 7, 8, 9, 11, 12, 14, 17, 18, 21, 22, 25, 28, 29, ... |
| backend/src/market/binance_testnet_schemas.py | 35 | 35 | 0% | 3, 5, 6, 8, 10, 11, 12, 15, 18, 19, 20, 21, 22, 23, 24, ... |
| backend/src/market/binance_testnet_service.py | 160 | 160 | 0% | 8, 10, 11, 12, 13, 14, 15, 17, 18, 19, 20, 22, 24, 25, 26, ... |
| backend/src/shared/config/asgi.py | 33 | 33 | 0% | 16, 17, 20, 22, 25, 28, 31, 32, 35, 36, 37, 39, 42, 46, 47, ... |
| backend/src/shared/config/wsgi.py | 22 | 22 | 0% | 17, 19, 22, 30, 32, 33, 35, 37, 43, 47, 54, 55, 56, 58, 59, ... |
| backend/src/strategy/engine/implementations/multi_indicator.py | 115 | 97 | 16% | 60, 63, 64, 65, 67, 68, 69, 71, 72, 74, 75, 77, 78, 90, 91, ... |
| backend/src/market/clients/minio.py | 123 | 102 | 17% | 12, 13, 14, 27, 30, 31, 33, 38, 40, 50, 51, 52, 53, 54, 60, ... |
| utils/connectors/minio.py | 107 | 88 | 18% | 31, 32, 35, 38, 39, 41, 42, 43, 47, 48, 54, 55, 56, 59, 60, ... |
| backend/src/strategy/engine/implementations/bollinger_bands.py | 71 | 57 | 20% | 46, 49, 50, 51, 52, 53, 54, 55, 67, 68, 69, 72, 75, 76, 77, ... |
| backend/src/shared/database/connection.py | 156 | 124 | 21% | 43, 45, 47, 48, 51, 52, 54, 55, 56, 58, 59, 60, 61, 63, 64, ... |
| backend/src/auth/users_router.py | 207 | 155 | 25% | 25, 33, 34, 35, 37, 38, 39, 40, 51, 52, 54, 55, 60, 62, 63, ... |
| backend/src/trading/router.py | 167 | 124 | 26% | 42, 73, 74, 76, 78, 80, 81, 82, 90, 91, 92, 96, 97, 98, 102, ... |
| backend/src/strategy/service.py | 347 | 252 | 27% | 66, 67, 68, 69, 74, 75, 76, 79, 80, 91, 92, 93, 96, 98, 99, ... |
| backend/src/market/router.py | 243 | 168 | 31% | 60, 109, 110, 144, 145, 181, 182, 183, 223, 224, 227, 230, 231, 232, 235, ... |
| backend/src/market/service.py | 54 | 37 | 31% | 49, 52, 66, 67, 68, 80, 89, 92, 93, 94, 95, 96, 97, 98, 101, ... |
| backend/src/strategy/engine/indicators/technical_indicators.py | 122 | 82 | 33% | 35, 52, 53, 55, 70, 71, 101, 102, 103, 104, 106, 107, 109, 110, 111, ... |
| backend/src/auth/router.py | 74 | 49 | 34% | 33, 35, 38, 39, 42, 44, 46, 47, 48, 49, 50, 67, 71, 72, 74, ... |
| backend/src/shared/models/__init__.py | 46 | 30 | 35% | 52, 53, 54, 61, 63, 94, 105, 106, 107, 110, 111, 112, 115, 116, 117, ... |
| backend/src/auth/dependencies.py | 37 | 24 | 35% | 28, 30, 33, 35, 37, 38, 39, 40, 56, 57, 59, 71, 72, 77, 90, ... |
| backend/src/market/clients/binance.py | 162 | 102 | 37% | 47, 48, 49, 50, 51, 52, 97, 100, 101, 102, 125, 132, 133, 134, 135, ... |
| backend/src/bots/ml_client.py | 32 | 20 | 38% | 32, 36, 37, 39, 40, 43, 48, 49, 51, 52, 53, 54, 55, 56, 58, ... |
| backend/src/trading/service.py | 253 | 156 | 38% | 86, 157, 158, 159, 160, 161, 162, 186, 187, 190, 191, 192, 193, 194, 195, ... |
| backend/src/inference/service.py | 67 | 41 | 39% | 34, 35, 36, 37, 38, 42, 46, 50, 51, 52, 56, 57, 58, 60, 61, ... |
| backend/src/strategy/engine/registry.py | 102 | 62 | 39% | 46, 49, 63, 64, 65, 66, 67, 69, 85, 107, 108, 109, 118, 133, 134, ... |
| backend/src/auth/service.py | 200 | 114 | 43% | 17, 18, 22, 23, 24, 53, 55, 64, 69, 70, 71, 75, 76, 77, 78, ... |
| backend/src/main.py | 112 | 60 | 46% | 40, 41, 44, 46, 48, 49, 52, 53, 54, 55, 57, 59, 61, 67, 68, ... |
| backend/src/inference/router.py | 45 | 22 | 51% | 20, 21, 22, 32, 33, 34, 35, 36, 37, 38, 43, 55, 56, 57, 58, ... |
| utils/logging/formatters.py | 21 | 10 | 52% | 25, 26, 27, 28, 29, 30, 40, 49, 50, 51 |
| backend/src/strategy/engine/base_strategy.py | 76 | 34 | 55% | 81, 93, 94, 97, 100, 103, 106, 107, 110, 112, 113, 115, 116, 117, 125, ... |
| backend/src/shared/models/base.py | 94 | 37 | 61% | 48, 52, 56, 57, 61, 62, 70, 74, 92, 101, 102, 103, 107, 151, 152, ... |
| backend/src/strategy/engine/implementations/moving_average_crossover.py | 54 | 20 | 63% | 56, 69, 112, 116, 117, 118, 120, 121, 123, 124, 126, 127, 129, 130, 132, ... |
| backend/src/strategy/engine/implementations/rsi_reversal.py | 60 | 22 | 63% | 64, 77, 138, 142, 143, 144, 146, 147, 149, 150, 152, 153, 158, 159, 161, ... |
| backend/src/auth/user_service.py | 247 | 90 | 64% | 42, 43, 44, 45, 46, 146, 147, 148, 149, 152, 155, 156, 159, 160, 165, ... |
| backend/src/strategy/models.py | 224 | 77 | 66% | 59, 63, 64, 65, 70, 75, 80, 83, 128, 133, 134, 135, 139, 140, 141, ... |
| backend/src/market/models.py | 88 | 30 | 66% | 55, 60, 71, 76, 81, 86, 91, 92, 93, 98, 103, 108, 113, 118, 124, ... |
| backend/src/shared/database/dependencies.py | 6 | 2 | 67% | 26, 27 |
| backend/src/trading/models.py | 162 | 54 | 67% | 73, 78, 88, 93, 98, 99, 100, 105, 106, 108, 109, 114, 115, 116, 121, ... |
| backend/src/auth/models.py | 338 | 108 | 68% | 83, 84, 85, 86, 87, 88, 90, 95, 98, 125, 127, 130, 168, 173, 177, ... |
| backend/src/strategy/router.py | 158 | 50 | 68% | 43, 44, 60, 61, 120, 121, 155, 156, 191, 192, 222, 223, 224, 225, 265, ... |
| backend/src/bots/ai.py | 40 | 12 | 70% | 14, 27, 28, 30, 31, 48, 49, 51, 52, 69, 71, 72 |
| backend/src/bots/router.py | 51 | 14 | 73% | 27, 36, 45, 58, 67, 96, 106, 116, 126, 136, 146, 156, 166, 176 |
| backend/src/market/clients/binance_native.py | 42 | 11 | 74% | 53, 54, 55, 56, 57, 64, 67, 68, 71, 72, 75 |
| backend/src/bots/service.py | 784 | 204 | 74% | 177, 179, 199, 200, 201, 202, 203, 204, 218, 229, 249, 250, 251, 257, 260, ... |
| utils/tests/test_ccxt_driver.py | 62 | 16 | 74% | 65, 67, 68, 69, 70, 71, 72, 73, 75, 77, 78, 79, 80, 81, 82, ... |
| backend/src/shared/config/settings.py | 199 | 46 | 77% | 135, 145, 150, 151, 156, 157, 158, 160, 161, 163, 164, 167, 168, 187, 194, ... |
| backend/src/shared/core/exceptions.py | 34 | 7 | 79% | 43, 45, 70, 71, 72, 73, 74 |
| utils/logging/logger.py | 49 | 9 | 82% | 46, 47, 48, 49, 50, 64, 89, 113, 127 |
| backend/src/market/clients/ccxt_client.py | 75 | 13 | 83% | 78, 95, 96, 97, 98, 102, 103, 106, 123, 124, 125, 129, 130 |
| backend/src/market/insert_service.py | 125 | 9 | 93% | 208, 293, 372, 374, 375, 387, 397, 398, 399 |
| utils/connectors/exchanges/binance_native.py | 31 | 2 | 94% | 65, 67 |
| utils/connectors/exchanges/registry.py | 20 | 1 | 95% | 45 |
| backend/src/market/clients/base.py | 37 | 1 | 97% | 24 |
| backend/src/bots/models.py | 124 | 1 | 99% | 36 |
| backend/src/auth/schemas.py | 128 | 1 | 99% | 16 |
| backend/src/bots/execution.py | 62 | 0 | 100% |  |
| backend/src/bots/schemas.py | 236 | 0 | 100% |  |
| backend/src/bots/worker.py | 32 | 0 | 100% |  |
| backend/src/inference/live_features.py | 22 | 0 | 100% |  |
| backend/src/inference/schemas.py | 30 | 0 | 100% |  |
| backend/src/market/clients/factory.py | 14 | 0 | 100% |  |
| backend/src/market/clients/quotes.py | 7 | 0 | 100% |  |
| backend/src/market/clients/registry.py | 10 | 0 | 100% |  |
| backend/src/market/schemas.py | 157 | 0 | 100% |  |
| backend/src/shared/config/__init__.py | 3 | 0 | 100% |  |
| backend/src/shared/config/constants.py | 144 | 0 | 100% |  |
| backend/src/shared/config/security.py | 22 | 0 | 100% |  |
| backend/src/shared/core/__init__.py | 2 | 0 | 100% |  |
| backend/src/shared/database/__init__.py | 3 | 0 | 100% |  |
| backend/src/shared/schemas/__init__.py | 2 | 0 | 100% |  |
| backend/src/shared/schemas/common.py | 34 | 0 | 100% |  |
| backend/src/strategy/engine/__init__.py | 5 | 0 | 100% |  |
| backend/src/strategy/engine/implementations/__init__.py | 5 | 0 | 100% |  |
| backend/src/strategy/engine/indicators/__init__.py | 2 | 0 | 100% |  |
| backend/src/strategy/schemas.py | 202 | 0 | 100% |  |
| backend/src/trading/schemas.py | 190 | 0 | 100% |  |
| utils/__init__.py | 5 | 0 | 100% |  |
| utils/connectors/__init__.py | 4 | 0 | 100% |  |
| utils/connectors/exchanges/__init__.py | 4 | 0 | 100% |  |
| utils/connectors/exchanges/base.py | 25 | 0 | 100% |  |
| utils/connectors/exchanges/ccxt_driver.py | 28 | 0 | 100% |  |
| utils/connectors/postgres.py | 23 | 0 | 100% |  |
| utils/features/indicators.py | 66 | 0 | 100% |  |
| utils/logging/__init__.py | 2 | 0 | 100% |  |
| utils/tests/test_base.py | 44 | 0 | 100% |  |
| utils/tests/test_binance_native.py | 58 | 0 | 100% |  |
| utils/tests/test_postgres.py | 28 | 0 | 100% |  |
| utils/tests/test_registry.py | 11 | 0 | 100% |  |
| utils/tests/test_signals.py | 6 | 0 | 100% |  |
| utils/trading/signals.py | 3 | 0 | 100% |  |

## Frontend (75.1%)

| Fichier | Lignes | Manquantes | % | Lignes non couvertes |
|---|---|---|---|---|
| src/services/backtest_service.py | 60 | 60 | 0% | 3, 5, 6, 7, 8, 11, 12, 13, 14, 15, 16, 17, 18, 19, 22, ... |
| src/services/binance_testnet_lab_service.py | 84 | 84 | 0% | 3, 5, 6, 8, 9, 10, 13, 14, 15, 17, 18, 20, 21, 23, 24, ... |
| src/utils/api_errors.py | 25 | 16 | 36% | 10, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30, ... |
| src/utils/numeric.py | 11 | 6 | 45% | 9, 10, 14, 15, 16, 17 |
| src/pages/05_Controle_Bot_Spot.py | 227 | 118 | 48% | 30, 34, 36, 41, 42, 43, 44, 45, 46, 47, 49, 50, 51, 52, 56, ... |
| src/services/bot_config_service.py | 150 | 63 | 58% | 36, 38, 54, 55, 56, 57, 60, 61, 62, 63, 64, 65, 75, 76, 77, ... |
| src/mocks/factories.py | 83 | 34 | 59% | 19, 33, 37, 44, 48, 53, 54, 55, 66, 70, 77, 78, 79, 91, 100, ... |
| src/services/account_service.py | 172 | 69 | 60% | 40, 51, 52, 68, 79, 102, 109, 110, 111, 112, 113, 138, 139, 143, 155, ... |
| src/services/auth_api_client.py | 160 | 56 | 65% | 45, 50, 51, 52, 53, 54, 57, 64, 71, 78, 92, 106, 118, 130, 137, ... |
| src/app.py | 68 | 23 | 66% | 22, 27, 28, 32, 33, 37, 38, 49, 50, 55, 56, 57, 58, 59, 60, ... |
| src/services/admin_service.py | 168 | 52 | 69% | 26, 29, 38, 70, 71, 72, 73, 76, 77, 78, 79, 80, 81, 103, 105, ... |
| src/services/bot_control_service.py | 274 | 83 | 70% | 39, 61, 62, 65, 71, 141, 185, 193, 194, 196, 197, 198, 199, 205, 208, ... |
| src/utils/dates.py | 18 | 5 | 72% | 16, 20, 21, 24, 28 |
| src/services/base.py | 15 | 4 | 73% | 19, 20, 21, 26 |
| src/pages/10_Politique_de_confidentialite.py | 20 | 5 | 75% | 27, 28, 31, 32, 33 |
| src/utils/streamlit_compat.py | 24 | 6 | 75% | 46, 47, 48, 49, 53, 54 |
| src/pages/04_Performances_Spot.py | 153 | 38 | 75% | 13, 14, 54, 55, 56, 58, 59, 83, 91, 92, 93, 96, 120, 121, 123, ... |
| src/services/performance_service.py | 147 | 35 | 76% | 46, 57, 84, 93, 106, 136, 137, 138, 146, 149, 181, 182, 188, 192, 193, ... |
| src/services/auth_service.py | 113 | 25 | 78% | 40, 43, 64, 68, 71, 74, 77, 122, 123, 124, 126, 127, 128, 130, 131, ... |
| src/pages/08_Admin.py | 84 | 18 | 79% | 30, 31, 32, 35, 36, 66, 68, 80, 81, 82, 106, 107, 108, 109, 123, ... |
| src/pages/07_Gestion_de_compte.py | 128 | 27 | 79% | 32, 35, 36, 37, 52, 53, 78, 97, 105, 106, 107, 140, 141, 142, 143, ... |
| src/pages/01_Marche.py | 85 | 17 | 80% | 57, 58, 59, 62, 65, 66, 154, 155, 156, 159, 160, 182, 183, 184, 187, ... |
| src/state/session.py | 177 | 35 | 80% | 38, 39, 40, 41, 42, 43, 44, 48, 49, 53, 54, 55, 56, 60, 64, ... |
| src/components/alerts.py | 11 | 2 | 82% | 11, 13 |
| src/services/runtime_mode.py | 11 | 2 | 82% | 17, 22 |
| src/services/api_client.py | 105 | 19 | 82% | 29, 61, 63, 67, 69, 172, 187, 278, 289, 302, 309, 329, 337, 338, 339, ... |
| src/pydantic/__init__.py | 93 | 16 | 83% | 60, 61, 71, 72, 73, 77, 82, 93, 94, 95, 96, 99, 100, 111, 122, ... |
| src/utils/validators.py | 36 | 6 | 83% | 15, 24, 26, 34, 36, 38 |
| src/pages/06_Parametrage_Bot_Spot.py | 86 | 14 | 84% | 22, 70, 71, 72, 75, 76, 97, 98, 99, 106, 107, 108, 109, 110 |
| src/pages/03_Portefeuille_Spot.py | 130 | 19 | 85% | 10, 11, 46, 105, 106, 107, 111, 116, 134, 136, 157, 174, 183, 184, 185, ... |
| src/pages/02_Inscription.py | 56 | 8 | 86% | 78, 79, 88, 89, 99, 100, 101, 103 |
| src/services/portfolio_service.py | 77 | 10 | 87% | 60, 125, 130, 132, 137, 138, 139, 140, 141, 142 |
| src/utils/selectors.py | 48 | 6 | 88% | 33, 34, 36, 39, 52, 64 |
| src/pages/00_Tableau_de_bord.py | 41 | 5 | 88% | 55, 56, 57, 60, 61 |
| src/services/market_service.py | 32 | 3 | 91% | 20, 29, 50 |
| src/layouts/page_shell.py | 35 | 3 | 91% | 45, 46, 47 |
| src/components/prerequisites.py | 13 | 1 | 92% | 19 |
| src/components/badges.py | 14 | 1 | 93% | 13 |
| src/components/cards.py | 16 | 1 | 94% | 19 |
| src/utils/formatters.py | 18 | 1 | 94% | 24 |
| src/components/tables.py | 26 | 1 | 96% | 17 |
| src/components/navigation.py | 72 | 2 | 97% | 111, 112 |
| src/navigation/rules.py | 36 | 1 | 97% | 112 |
| src/schemas/auth.py | 51 | 1 | 98% | 29 |
| src/components/headers.py | 10 | 0 | 100% |  |
| src/mocks/db.py | 35 | 0 | 100% |  |
| src/mocks/scenarios.py | 15 | 0 | 100% |  |
| src/prerequisites/exchange.py | 46 | 0 | 100% |  |
| src/schemas/account.py | 36 | 0 | 100% |  |
| src/schemas/admin.py | 17 | 0 | 100% |  |
| src/schemas/bot.py | 67 | 0 | 100% |  |
| src/schemas/common.py | 26 | 0 | 100% |  |
| src/schemas/dashboard.py | 22 | 0 | 100% |  |
| src/schemas/market.py | 22 | 0 | 100% |  |
| src/schemas/performance.py | 119 | 0 | 100% |  |
| src/schemas/portfolio.py | 42 | 0 | 100% |  |
| src/services/dashboard_service.py | 28 | 0 | 100% |  |
| src/theme/manager.py | 18 | 0 | 100% |  |
| src/theme/plotly.py | 39 | 0 | 100% |  |
| src/theme/styles.py | 9 | 0 | 100% |  |
| src/theme/tokens.py | 7 | 0 | 100% |  |
| src/utils/constants.py | 10 | 0 | 100% |  |
