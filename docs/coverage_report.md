# Rapport de couverture de test

Snapshot du 2026-08-02 -- regenere a chaque `python3 scripts/track_coverage.py`
(ecrase le precedent, pas un historique -- voir `coverage_history.csv` pour l'evolution du %).

## Backend + utils (57.5%)

| Fichier | Lignes | Manquantes | % | Lignes non couvertes |
|---|---|---|---|---|
| backend/src/auth/purge_inactive_users.py | 4 | 4 | 0% | 1, 3, 4, 5 |
| backend/src/auth/router.py | 74 | 74 | 0% | 6, 8, 9, 11, 12, 13, 15, 18, 19, 29, 31, 34, 35, 38, 40, ... |
| backend/src/auth/users_router.py | 130 | 130 | 0% | 6, 8, 9, 10, 11, 14, 16, 19, 20, 24, 27, 28, 32, 33, 34, ... |
| backend/src/main.py | 87 | 87 | 0% | 8, 9, 11, 12, 13, 14, 15, 16, 17, 20, 23, 24, 27, 28, 31, ... |
| backend/src/shared/config/asgi.py | 33 | 33 | 0% | 16, 17, 20, 22, 25, 28, 31, 32, 35, 36, 37, 39, 42, 46, 47, ... |
| backend/src/shared/config/wsgi.py | 22 | 22 | 0% | 17, 19, 22, 30, 32, 33, 35, 37, 43, 47, 54, 55, 56, 58, 59, ... |
| backend/src/trading/router.py | 167 | 167 | 0% | 6, 8, 9, 10, 11, 17, 18, 19, 21, 31, 33, 36, 40, 42, 50, ... |
| backend/src/strategy/engine/implementations/multi_indicator.py | 115 | 97 | 16% | 60, 63, 64, 65, 67, 68, 69, 71, 72, 74, 75, 77, 78, 90, 91, ... |
| backend/src/market/clients/minio.py | 117 | 97 | 17% | 23, 26, 27, 29, 34, 36, 46, 47, 48, 54, 57, 58, 59, 60, 61, ... |
| utils/connectors/minio.py | 107 | 88 | 18% | 31, 32, 35, 38, 39, 41, 42, 43, 47, 48, 54, 55, 56, 59, 60, ... |
| backend/src/strategy/engine/implementations/bollinger_bands.py | 71 | 57 | 20% | 46, 49, 50, 51, 52, 53, 54, 55, 67, 68, 69, 72, 75, 76, 77, ... |
| backend/src/strategy/engine/implementations/rsi_reversal.py | 60 | 46 | 23% | 53, 56, 57, 58, 59, 60, 63, 64, 76, 77, 80, 83, 86, 90, 93, ... |
| backend/src/strategy/engine/indicators/technical_indicators.py | 122 | 93 | 24% | 34, 35, 37, 52, 53, 55, 69, 70, 71, 73, 74, 75, 77, 78, 80, ... |
| backend/src/shared/database/connection.py | 130 | 99 | 24% | 43, 45, 47, 48, 51, 52, 54, 55, 56, 58, 59, 60, 61, 63, 64, ... |
| backend/src/strategy/engine/implementations/moving_average_crossover.py | 54 | 40 | 26% | 46, 49, 50, 51, 52, 55, 56, 68, 69, 72, 75, 76, 79, 83, 86, ... |
| backend/src/strategy/engine/base_strategy.py | 76 | 54 | 29% | 32, 33, 34, 35, 36, 68, 81, 93, 94, 97, 100, 103, 106, 107, 110, ... |
| backend/src/market/router.py | 238 | 165 | 31% | 60, 109, 110, 144, 145, 208, 209, 212, 215, 216, 217, 220, 223, 224, 227, ... |
| backend/src/market/service.py | 54 | 37 | 31% | 49, 52, 66, 67, 68, 80, 89, 92, 93, 94, 95, 96, 97, 98, 101, ... |
| backend/src/shared/models/__init__.py | 46 | 30 | 35% | 52, 53, 54, 61, 63, 94, 105, 106, 107, 110, 111, 112, 115, 116, 117, ... |
| backend/src/auth/dependencies.py | 37 | 24 | 35% | 28, 30, 33, 35, 37, 38, 39, 40, 56, 57, 59, 71, 72, 77, 90, ... |
| backend/src/market/clients/binance.py | 162 | 102 | 37% | 47, 48, 49, 50, 51, 52, 97, 100, 101, 102, 125, 132, 133, 134, 135, ... |
| backend/src/trading/service.py | 253 | 156 | 38% | 86, 157, 158, 159, 160, 161, 162, 186, 187, 190, 191, 192, 193, 194, 195, ... |
| backend/src/strategy/engine/registry.py | 102 | 61 | 40% | 46, 49, 63, 64, 65, 66, 67, 69, 84, 85, 87, 104, 105, 106, 107, ... |
| backend/src/inference/service.py | 62 | 37 | 40% | 33, 34, 35, 36, 37, 41, 45, 49, 50, 51, 55, 56, 57, 59, 60, ... |
| backend/src/strategy/service.py | 198 | 109 | 45% | 67, 68, 69, 70, 75, 76, 77, 80, 81, 92, 93, 94, 97, 99, 100, ... |
| backend/src/auth/service.py | 114 | 59 | 48% | 49, 81, 83, 85, 86, 88, 89, 91, 92, 94, 95, 100, 101, 102, 107, ... |
| backend/src/inference/router.py | 45 | 22 | 51% | 20, 21, 22, 32, 33, 34, 35, 36, 37, 38, 43, 55, 56, 57, 58, ... |
| utils/logging/formatters.py | 21 | 10 | 52% | 25, 26, 27, 28, 29, 30, 40, 49, 50, 51 |
| backend/src/shared/models/base.py | 94 | 37 | 61% | 48, 52, 56, 57, 61, 62, 70, 74, 92, 101, 102, 103, 107, 151, 152, ... |
| backend/src/strategy/models.py | 223 | 77 | 65% | 59, 63, 64, 65, 70, 75, 80, 83, 127, 132, 133, 134, 138, 139, 140, ... |
| backend/src/market/models.py | 88 | 30 | 66% | 55, 60, 71, 76, 81, 86, 91, 92, 93, 98, 103, 108, 113, 118, 124, ... |
| backend/src/shared/database/dependencies.py | 6 | 2 | 67% | 26, 27 |
| backend/src/trading/models.py | 162 | 54 | 67% | 73, 78, 88, 93, 98, 99, 100, 105, 106, 108, 109, 114, 115, 116, 121, ... |
| utils/tests/test_ccxt_driver.py | 59 | 16 | 73% | 58, 60, 61, 62, 63, 64, 65, 66, 68, 70, 71, 72, 73, 74, 75, ... |
| backend/src/auth/user_service.py | 173 | 45 | 74% | 117, 118, 119, 120, 123, 126, 127, 130, 131, 136, 137, 140, 141, 147, 148, ... |
| backend/src/shared/config/settings.py | 191 | 45 | 76% | 123, 133, 138, 139, 144, 145, 146, 148, 149, 151, 152, 155, 156, 174, 186, ... |
| backend/src/strategy/router.py | 129 | 27 | 79% | 41, 42, 58, 59, 118, 119, 153, 154, 189, 190, 220, 221, 222, 223, 263, ... |
| backend/src/shared/core/exceptions.py | 34 | 7 | 79% | 43, 45, 70, 71, 72, 73, 74 |
| utils/logging/logger.py | 49 | 9 | 82% | 46, 47, 48, 49, 50, 64, 89, 113, 127 |
| backend/src/auth/models.py | 195 | 35 | 82% | 73, 74, 75, 76, 77, 78, 80, 85, 88, 115, 117, 120, 158, 163, 167, ... |
| backend/src/market/clients/binance_native.py | 35 | 5 | 86% | 52, 59, 62, 63, 66 |
| utils/connectors/exchanges/binance_native.py | 31 | 2 | 94% | 65, 67 |
| utils/connectors/exchanges/registry.py | 20 | 1 | 95% | 45 |
| backend/src/market/clients/base.py | 35 | 1 | 97% | 24 |
| backend/src/market/clients/ccxt_client.py | 55 | 1 | 98% | 78 |
| backend/src/market/insert_service.py | 117 | 2 | 98% | 208, 293 |
| backend/src/auth/schemas.py | 90 | 0 | 100% |  |
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
| backend/src/strategy/engine/__init__.py | 6 | 0 | 100% |  |
| backend/src/strategy/engine/implementations/__init__.py | 5 | 0 | 100% |  |
| backend/src/strategy/engine/indicators/__init__.py | 2 | 0 | 100% |  |
| backend/src/strategy/schemas.py | 198 | 0 | 100% |  |
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
| utils/trading/signals.py | 2 | 0 | 100% |  |

## Frontend (81.0%)

| Fichier | Lignes | Manquantes | % | Lignes non couvertes |
|---|---|---|---|---|
| src/mocks/factories.py | 83 | 83 | 0% | 3, 5, 6, 8, 9, 15, 18, 19, 33, 36, 37, 44, 47, 48, 53, ... |
| src/utils/api_errors.py | 25 | 16 | 36% | 10, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30, ... |
| src/services/base.py | 15 | 7 | 53% | 17, 18, 19, 20, 21, 25, 26 |
| src/pages/05_Controle_Bot_Spot.py | 108 | 45 | 58% | 29, 31, 51, 52, 53, 56, 57, 92, 100, 101, 102, 103, 111, 114, 115, ... |
| src/utils/numeric.py | 11 | 4 | 64% | 9, 10, 16, 17 |
| src/app.py | 65 | 22 | 66% | 22, 23, 27, 28, 32, 33, 44, 45, 50, 51, 52, 53, 54, 55, 56, ... |
| src/services/auth_api_client.py | 75 | 24 | 68% | 45, 50, 51, 52, 53, 54, 57, 64, 71, 78, 106, 107, 109, 110, 113, ... |
| src/pages/06_Parametrage_Bot_Spot.py | 101 | 29 | 71% | 37, 38, 39, 43, 44, 45, 49, 60, 61, 63, 64, 65, 66, 68, 69, ... |
| src/components/alerts.py | 11 | 3 | 73% | 11, 13, 15 |
| src/pages/04_Performances_Spot.py | 83 | 21 | 75% | 9, 10, 48, 49, 50, 52, 53, 68, 76, 77, 78, 97, 98, 100, 111, ... |
| src/utils/streamlit_compat.py | 24 | 6 | 75% | 46, 47, 48, 49, 53, 54 |
| src/services/account_service.py | 131 | 32 | 76% | 34, 45, 46, 62, 73, 96, 103, 104, 105, 106, 107, 132, 133, 137, 149, ... |
| src/pages/02_Inscription.py | 47 | 11 | 77% | 56, 63, 64, 65, 66, 68, 69, 79, 80, 81, 83 |
| src/utils/dates.py | 18 | 4 | 78% | 16, 20, 21, 28 |
| src/pages/08_Admin.py | 84 | 18 | 79% | 30, 31, 32, 35, 36, 64, 66, 78, 79, 80, 105, 106, 107, 108, 122, ... |
| src/pages/07_Gestion_de_compte.py | 131 | 27 | 79% | 32, 35, 36, 37, 52, 53, 76, 96, 104, 105, 106, 139, 140, 141, 142, ... |
| src/services/auth_service.py | 109 | 22 | 80% | 39, 42, 63, 67, 70, 73, 76, 121, 122, 123, 125, 126, 127, 129, 134, ... |
| src/pages/01_Marche.py | 85 | 17 | 80% | 57, 58, 59, 62, 65, 66, 154, 155, 156, 159, 160, 182, 183, 184, 187, ... |
| src/state/session.py | 172 | 34 | 80% | 38, 39, 40, 41, 42, 43, 44, 48, 49, 53, 54, 55, 56, 60, 64, ... |
| src/services/bot_config_service.py | 102 | 18 | 82% | 18, 34, 41, 42, 43, 47, 52, 119, 120, 121, 122, 123, 124, 125, 126, ... |
| src/pydantic/__init__.py | 93 | 16 | 83% | 60, 61, 71, 72, 73, 77, 82, 93, 94, 95, 96, 99, 100, 111, 122, ... |
| src/utils/validators.py | 36 | 6 | 83% | 15, 24, 26, 34, 36, 38 |
| src/pages/03_Portefeuille_Spot.py | 130 | 18 | 86% | 10, 11, 46, 106, 107, 108, 112, 134, 136, 157, 174, 183, 184, 185, 186, ... |
| src/services/portfolio_service.py | 77 | 10 | 87% | 60, 125, 130, 132, 137, 138, 139, 140, 141, 142 |
| src/services/admin_service.py | 62 | 8 | 87% | 26, 31, 34, 52, 69, 86, 94, 103 |
| src/utils/selectors.py | 48 | 6 | 88% | 33, 34, 36, 39, 52, 64 |
| src/services/market_service.py | 32 | 3 | 91% | 20, 29, 50 |
| src/layouts/page_shell.py | 35 | 3 | 91% | 45, 46, 47 |
| src/services/bot_control_service.py | 80 | 6 | 92% | 40, 49, 54, 65, 114, 119 |
| src/services/api_client.py | 82 | 6 | 93% | 29, 61, 63, 67, 69, 171 |
| src/components/badges.py | 14 | 1 | 93% | 13 |
| src/components/prerequisites.py | 14 | 1 | 93% | 19 |
| src/components/cards.py | 16 | 1 | 94% | 19 |
| src/utils/formatters.py | 18 | 1 | 94% | 24 |
| src/components/tables.py | 26 | 1 | 96% | 17 |
| src/services/performance_service.py | 33 | 1 | 97% | 34 |
| src/navigation/rules.py | 35 | 1 | 97% | 91 |
| src/components/navigation.py | 72 | 2 | 97% | 111, 112 |
| src/schemas/auth.py | 51 | 1 | 98% | 29 |
| src/components/headers.py | 10 | 0 | 100% |  |
| src/mocks/db.py | 35 | 0 | 100% |  |
| src/mocks/scenarios.py | 15 | 0 | 100% |  |
| src/prerequisites/exchange.py | 46 | 0 | 100% |  |
| src/schemas/account.py | 22 | 0 | 100% |  |
| src/schemas/admin.py | 16 | 0 | 100% |  |
| src/schemas/bot.py | 39 | 0 | 100% |  |
| src/schemas/common.py | 26 | 0 | 100% |  |
| src/schemas/market.py | 22 | 0 | 100% |  |
| src/schemas/performance.py | 30 | 0 | 100% |  |
| src/schemas/portfolio.py | 42 | 0 | 100% |  |
| src/theme/manager.py | 18 | 0 | 100% |  |
| src/theme/plotly.py | 39 | 0 | 100% |  |
| src/theme/styles.py | 9 | 0 | 100% |  |
| src/theme/tokens.py | 7 | 0 | 100% |  |
| src/utils/constants.py | 10 | 0 | 100% |  |
