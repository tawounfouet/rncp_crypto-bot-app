"""Reseed built-in bot templates and optionally migrate user bot snapshots."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any


BACKEND_DIR = Path(__file__).resolve().parents[1]
SRC_DIR = BACKEND_DIR / "src"

if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

os.environ.setdefault("DATABASE_ECHO", "False")


def _active_bot_summary() -> list[dict[str, Any]]:
    from bots.models import UserBotInstance
    from shared.database.connection import get_db_session

    with get_db_session() as session:
        instances = (
            session.query(UserBotInstance)
            .filter(UserBotInstance.status == "ACTIVE", UserBotInstance.auto_trade_enabled.is_(True))
            .all()
        )
        summary = []
        for instance in instances:
            snapshot = dict(instance.config_snapshot or {})
            summary.append(
                {
                    "id": instance.id,
                    "template_slug": snapshot.get("template_slug"),
                    "name": snapshot.get("name"),
                    "symbol": snapshot.get("symbol"),
                    "timeframe": snapshot.get("timeframe"),
                    "model_type": snapshot.get("model_type"),
                    "signal_source": snapshot.get("signal_source"),
                    "status": instance.status,
                }
            )
        return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Sync built-in bot templates in the runtime database.")
    parser.add_argument(
        "--migrate-instances",
        action="store_true",
        help="Also replace snapshots for existing user bots based on built-in templates",
    )
    parser.add_argument("--show-active", action="store_true", help="Print active bot snapshots after sync")
    args = parser.parse_args()

    from bots.service import BotService
    from shared.database.connection import init_database

    if not init_database():
        raise SystemExit("Database initialization failed; bot templates were not synced.")

    result = BotService().sync_builtin_templates(migrate_instances=args.migrate_instances)
    payload: dict[str, Any] = {"sync": result}
    if args.show_active:
        payload["active_bots"] = _active_bot_summary()
    print(json.dumps(payload, indent=2, sort_keys=True, default=str))


if __name__ == "__main__":
    main()
