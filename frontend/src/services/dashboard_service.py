"""Service tableau de bord - agrege les bots et leurs performances."""

from __future__ import annotations

from mocks.db import MockStore
from schemas.bot import BotInfo
from schemas.common import BotRuntimeStatus
from schemas.dashboard import DashboardBotRow, DashboardOverview
from schemas.performance import PerformanceSnapshot
from services.api_client import BackendApiClient
from services.bot_control_service import BotControlService
from services.performance_service import PerformanceService

DEFAULT_PERIOD_DAYS = 30


def aggregate_overview(
    bots: list[BotInfo],
    snapshots: dict[str, PerformanceSnapshot],
    period_days: int = DEFAULT_PERIOD_DAYS,
) -> DashboardOverview:
    """Construit la vue d'ensemble agregee a partir des bots et de leurs snapshots."""
    rows: list[DashboardBotRow] = []
    for bot in bots:
        snapshot = snapshots.get(bot.id)
        metrics = snapshot.metrics if snapshot else None
        rows.append(
            DashboardBotRow(
                bot_id=bot.id,
                name=bot.name,
                strategy=bot.strategy,
                mode_live=bot.mode_live,
                status=bot.status.value,
                pnl_usdc=metrics.pnl_realized_usdc if metrics else 0.0,
                roi_pct=metrics.roi_pct if metrics else 0.0,
                fees_usdc=metrics.fees_usdc if metrics else 0.0,
                last_signal_at=bot.last_action_at,
                last_action_result=bot.last_action_result,
            )
        )

    active_bots = sum(1 for row in rows if row.status == BotRuntimeStatus.RUNNING.value)
    return DashboardOverview(
        period_days=period_days,
        total_bots=len(rows),
        active_bots=active_bots,
        pnl_usdc=sum(row.pnl_usdc for row in rows),
        avg_roi_pct=(sum(row.roi_pct for row in rows) / len(rows)) if rows else 0.0,
        fees_usdc=sum(row.fees_usdc for row in rows),
        bots=rows,
    )


class DashboardService:
    def __init__(self, store: MockStore, client: BackendApiClient | None = None) -> None:
        self._bot_service = BotControlService(store, client)
        self._perf_service = PerformanceService(store, client)

    def get_overview(self, period_days: int = DEFAULT_PERIOD_DAYS) -> DashboardOverview:
        bots = self._bot_service.list_bots()
        snapshots: dict[str, PerformanceSnapshot] = {}
        for bot in bots:
            snapshots[bot.id] = self._perf_service.get_snapshot(bot.id, period_days=period_days)
        return aggregate_overview(bots, snapshots, period_days)
