"""Integration tests for bot API route matching."""

from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime
from decimal import Decimal
from types import SimpleNamespace
from typing import Any

from fastapi import FastAPI


def test_performance_summary_static_route_is_not_captured_by_user_bot_id() -> None:
    from auth.dependencies import get_current_user
    from bots.router import get_bot_service, router
    from bots.schemas import UserPerformanceGlobalResponse, UserPerformanceSummaryResponse

    class FakeBotService:
        def __init__(self) -> None:
            self.summary_called_with: dict[str, object] | None = None
            self.dynamic_called_with: dict[str, object] | None = None

        def get_user_performance_summary(
            self,
            user_id: str,
            *,
            period_days: int = 30,
            bot_id: str | None = None,
            model_name: str | None = None,
        ) -> UserPerformanceSummaryResponse:
            self.summary_called_with = {
                "user_id": user_id,
                "period_days": period_days,
                "bot_id": bot_id,
                "model_name": model_name,
            }
            now = datetime.now(UTC)
            return UserPerformanceSummaryResponse(
                generated_at=now,
                period_start=None,
                period_end=now,
                period_days=period_days,
                bot_id=bot_id,
                model_name=model_name,
                global_performance=UserPerformanceGlobalResponse(
                    capital_initial=Decimal("100"),
                    capital_current=Decimal("100"),
                    pnl_total=Decimal("0"),
                    pnl_realized=Decimal("0"),
                    pnl_unrealized=Decimal("0"),
                    total_orders=0,
                    total_trades=0,
                    win_rate_pct=None,
                ),
            )

        def get_user_bot(self, user_id: str, instance_id: str) -> None:
            self.dynamic_called_with = {
                "user_id": user_id,
                "instance_id": instance_id,
            }
            raise AssertionError("Dynamic /user-bots/{instance_id} route was called")

    fake_service = FakeBotService()
    app = FastAPI()
    app.include_router(router, prefix="/api/v1")
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(id="user-1")
    app.dependency_overrides[get_bot_service] = lambda: fake_service

    status_code, payload = asyncio.run(
        _asgi_get_json(
            app,
            path="/api/v1/user-bots/performance-summary",
            query_string=b"period_days=30",
        )
    )

    assert status_code == 200
    assert payload["period_days"] == 30
    assert payload["global_performance"]["pnl_realized"] == "0"
    assert fake_service.summary_called_with == {
        "user_id": "user-1",
        "period_days": 30,
        "bot_id": None,
        "model_name": None,
    }
    assert fake_service.dynamic_called_with is None


async def _asgi_get_json(
    app: FastAPI,
    *,
    path: str,
    query_string: bytes = b"",
) -> tuple[int, dict[str, Any]]:
    messages: list[dict[str, Any]] = []
    request_sent = False

    async def receive() -> dict[str, Any]:
        nonlocal request_sent
        if request_sent:
            return {"type": "http.disconnect"}
        request_sent = True
        return {"type": "http.request", "body": b"", "more_body": False}

    async def send(message: dict[str, Any]) -> None:
        messages.append(message)

    await app(
        {
            "type": "http",
            "asgi": {"version": "3.0"},
            "http_version": "1.1",
            "method": "GET",
            "scheme": "http",
            "path": path,
            "raw_path": path.encode("ascii"),
            "query_string": query_string,
            "headers": [(b"host", b"testserver")],
            "client": ("testclient", 50000),
            "server": ("testserver", 80),
        },
        receive,
        send,
    )

    start = next(message for message in messages if message["type"] == "http.response.start")
    body = b"".join(
        message.get("body", b"")
        for message in messages
        if message["type"] == "http.response.body"
    )
    return int(start["status"]), json.loads(body.decode("utf-8"))
