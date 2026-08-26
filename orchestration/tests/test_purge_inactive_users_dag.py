"""Tests du DAG ``cryptobot_purge_inactive_users``.

L'import d'Airflow est requis : le module est skip si ``airflow`` n'est pas
installe (venv root / CI Python), et s'execute reellement dans l'image
Airflow (cf. orchestration/requirements.txt, apache-airflow 2.8.1).
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch

import pytest

pytest.importorskip("airflow")

DAGS_DIR = Path(__file__).resolve().parents[1] / "dags"
sys.path.insert(0, str(DAGS_DIR))

import purge_inactive_users as dag_module  # noqa: E402


def test_dag_is_registered_and_weekly() -> None:
    assert dag_module.dag.dag_id == "cryptobot_purge_inactive_users"
    assert dag_module.dag.schedule_interval == "0 3 * * 0"
    assert list(dag_module.dag.task_dict) == ["purge_inactive_users"]


def test_default_purge_threshold_is_730_days() -> None:
    assert dag_module.PURGE_INACTIVE_DAYS == 730


def test_callable_posts_to_purge_endpoint() -> None:
    with patch("purge_inactive_users.requests.post") as mock_post:
        mock_post.return_value.raise_for_status.return_value = None
        mock_post.return_value.json.return_value = {
            "success": True,
            "data": {"deleted": 2},
        }

        dag_module._purge_inactive_users_callable()

    mock_post.assert_called_once()
    args, kwargs = mock_post.call_args
    assert args[0] == dag_module.PURGE_URL
    assert kwargs["params"] == {"days": dag_module.PURGE_INACTIVE_DAYS}
