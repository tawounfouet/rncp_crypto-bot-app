"""Worker entry points for active user bots."""

from __future__ import annotations

import asyncio
import logging

from bots.schemas import TradingDecisionResponse
from bots.service import BotService, bot_service

logger = logging.getLogger(__name__)


class BotWorker:
    """Small worker facade for scheduled bot execution."""

    def __init__(self, service: BotService | None = None, worker_id: str = "bot-worker") -> None:
        self.service = service or bot_service
        self.worker_id = worker_id

    def run_once(self, limit: int = 100) -> list[TradingDecisionResponse]:
        """Execute one signal/risk/order pass for active locked-template bots."""
        return self.service.execute_active_once(worker_id=self.worker_id, limit=limit)

    async def run_forever(
        self,
        *,
        interval_seconds: int = 60,
        limit: int = 100,
        stop_event: asyncio.Event | None = None,
    ) -> None:
        """Run scheduled bot passes until the application asks the worker to stop."""
        interval = max(int(interval_seconds), 1)
        batch_limit = max(int(limit), 1)

        while True:
            if stop_event and stop_event.is_set():
                return

            try:
                decisions = self.run_once(limit=batch_limit)
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("Bot worker pass failed")
            else:
                if decisions:
                    logger.info("Bot worker processed %s active bot(s)", len(decisions))

            if stop_event:
                try:
                    await asyncio.wait_for(stop_event.wait(), timeout=interval)
                except TimeoutError:
                    continue
            else:
                await asyncio.sleep(interval)
