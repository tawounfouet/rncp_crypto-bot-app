from __future__ import annotations

from mocks.scenarios import MockScenario
from services.auth_api_client import ApiResponse
from services.performance_service import PerformanceService
from state.session import set_auth_tokens


def test_performance_strong_scenario_positive_roi(store) -> None:
    store.current_user_email = "alice@cryptobot.dev"
    service = PerformanceService(store)
    snapshot = service.get_snapshot(
        bot_id="bot_btc_scalp",
        period_days=30,
        scenario_override=MockScenario.PERFORMANCE_STRONG,
    )
    assert snapshot.metrics.roi_pct > 0
    assert len(snapshot.equity_curve) == 31


def test_performance_weak_scenario_has_curve(store) -> None:
    store.current_user_email = "alice@cryptobot.dev"
    service = PerformanceService(store)
    snapshot = service.get_snapshot(
        bot_id="bot_btc_scalp",
        period_days=7,
        scenario_override=MockScenario.PERFORMANCE_WEAK,
    )
    assert len(snapshot.equity_curve) == 8
    assert snapshot.scenario_label


def test_dashboard_uses_backend_summary_with_ml_and_deterministic_decisions(store) -> None:
    class SummaryClient:
        def __init__(self) -> None:
            self.calls: list[dict[str, object]] = []

        def get_user_bot_performance_summary(
            self,
            access_token: str,
            *,
            period_days: int = 30,
            bot_id: str | None = None,
            model_name: str | None = None,
        ) -> ApiResponse:
            self.calls.append(
                {
                    "access_token": access_token,
                    "period_days": period_days,
                    "bot_id": bot_id,
                    "model_name": model_name,
                }
            )
            return ApiResponse(
                status_code=200,
                data={
                    "generated_at": "2026-06-28T10:00:00+00:00",
                    "period_start": "2026-05-29T10:00:00+00:00",
                    "period_end": "2026-06-28T10:00:00+00:00",
                    "period_days": 30,
                    "bot_id": None,
                    "model_name": None,
                    "unavailable_reasons": [],
                    "global_performance": {
                        "capital_initial": "175",
                        "capital_current": "195",
                        "pnl_total": "20",
                        "pnl_realized": "20",
                        "pnl_unrealized": "0",
                        "total_orders": 2,
                        "total_trades": 2,
                        "win_rate_pct": 50,
                    },
                    "bots": [
                        {
                            "bot_id": "bot-ai",
                            "bot_name": "AI RSI Mean Reversion BTCUSDC 1h",
                            "model_name": "bot_rsi_reversal_btcusdt_1h",
                            "model_version": "3",
                            "pnl_total": "25",
                            "pnl_realized": "25",
                            "pnl_unrealized": "0",
                            "orders": 1,
                            "trades": 1,
                            "last_decision": "BUY",
                            "last_decision_at": "2026-06-27T10:00:00+00:00",
                            "last_ai_signal": "BUY",
                            "average_confidence": 0.8,
                            "pnl_contribution_pct": 125,
                        },
                        {
                            "bot_id": "bot-det",
                            "bot_name": "AI Trend Following ETHUSDC 4h",
                            "model_name": "trend_classifier_v1",
                            "model_version": None,
                            "pnl_total": "-5",
                            "pnl_realized": "-5",
                            "pnl_unrealized": "0",
                            "orders": 1,
                            "trades": 1,
                            "last_decision": "SELL",
                            "last_decision_at": "2026-06-26T10:00:00+00:00",
                            "last_ai_signal": "SELL",
                            "average_confidence": None,
                            "pnl_contribution_pct": -25,
                        },
                    ],
                    "decisions": [
                        {
                            "id": "decision-ai",
                            "bot_id": "bot-ai",
                            "bot_name": "AI RSI Mean Reversion BTCUSDC 1h",
                            "timestamp": "2026-06-27T10:00:00+00:00",
                            "model_source": "ml_api",
                            "registry_source": "mlflow",
                            "model_name": "bot_rsi_reversal_btcusdt_1h",
                            "model_version": "3",
                            "confidence": 0.8,
                            "raw_ai_signal": "BUY",
                            "deterministic_signal": "HOLD",
                            "final_action": "BUY",
                            "risk_decision": "PASS",
                            "reason": "Risk gate passed.",
                        },
                        {
                            "id": "decision-det",
                            "bot_id": "bot-det",
                            "bot_name": "AI Trend Following ETHUSDC 4h",
                            "timestamp": "2026-06-26T10:00:00+00:00",
                            "model_source": "deterministic",
                            "registry_source": None,
                            "model_name": "trend_classifier_v1",
                            "model_version": None,
                            "confidence": None,
                            "raw_ai_signal": None,
                            "deterministic_signal": "SELL",
                            "final_action": "SELL",
                            "risk_decision": "PASS",
                            "reason": None,
                        },
                    ],
                    "orders": [],
                    "trades": [],
                    "pnl_curve": [
                        {
                            "timestamp": "2026-05-29T10:00:00+00:00",
                            "bot_id": None,
                            "bot_name": None,
                            "realized_pnl": "0",
                            "cumulative_realized_pnl": "0",
                            "capital_current": "175",
                        }
                    ],
                },
            )

    store.current_user_email = "alice@cryptobot.dev"
    set_auth_tokens("access-token", "refresh-token")
    client = SummaryClient()
    service = PerformanceService(store, client=client)

    dashboard = service.get_dashboard(period_days=30, bot_id=None, model_name=None)

    assert client.calls == [
        {
            "access_token": "access-token",
            "period_days": 30,
            "bot_id": None,
            "model_name": None,
        }
    ]
    assert dashboard.global_performance.pnl_total == 20
    assert dashboard.global_performance.win_rate_pct == 50
    assert dashboard.bots[0].model_name == "bot_rsi_reversal_btcusdt_1h"
    assert dashboard.bots[0].average_confidence == 0.8
    assert dashboard.bots[1].model_name == "trend_classifier_v1"
    assert dashboard.decisions[0].model_source == "ml_api"
    assert dashboard.decisions[1].raw_ai_signal is None


def test_dashboard_preserves_missing_data_reasons(store) -> None:
    class MissingDataClient:
        def get_user_bot_performance_summary(self, access_token: str, **kwargs) -> ApiResponse:
            return ApiResponse(
                status_code=200,
                data={
                    "generated_at": "2026-06-28T10:00:00+00:00",
                    "period_start": None,
                    "period_end": "2026-06-28T10:00:00+00:00",
                    "period_days": 0,
                    "unavailable_reasons": [
                        {
                            "field": "pnl_unrealized",
                            "reason": "prix marche Testnet indisponible pour BTCUSDC.",
                        }
                    ],
                    "global_performance": {
                        "capital_initial": None,
                        "capital_current": None,
                        "pnl_total": None,
                        "pnl_realized": "0",
                        "pnl_unrealized": None,
                        "total_orders": 0,
                        "total_trades": 0,
                        "win_rate_pct": None,
                    },
                    "bots": [],
                    "decisions": [],
                    "orders": [],
                    "trades": [],
                    "pnl_curve": [],
                },
            )

    set_auth_tokens("access-token", "refresh-token")
    service = PerformanceService(store, client=MissingDataClient())

    dashboard = service.get_dashboard(period_days=0)

    assert dashboard.global_performance.capital_current is None
    assert dashboard.unavailable_reasons[0].field == "pnl_unrealized"
