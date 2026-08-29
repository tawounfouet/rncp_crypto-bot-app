"""Client REST pour declencher/suivre des DAGs Airflow depuis le backend.

Meme principe que bots/ml_client.py::BotMlClient (client HTTP minimal, timeout court,
exceptions dediees plutot que de laisser fuiter requests.RequestException) -- utilise par
backtesting/service.py pour lancer un backfill (jobs/backfill/backfill_ohlcv.py, DAGs
backfill_ohlcv_binance / backfill_ohlcv_kraken) quand les donnees historiques demandees ne
sont pas deja couvertes en base.

Authentification : basic auth (AIRFLOW_ADMIN_USER/AIRFLOW_ADMIN_PASSWORD), necessite
AIRFLOW__API__AUTH_BACKENDS=airflow.api.auth.backend.basic_auth cote Airflow (defaut
Airflow 2.8 = auth par session uniquement, inutilisable depuis un service sans navigateur)
-- cf. docker-compose.yml.
"""

from __future__ import annotations

import logging
import os
from typing import Any

import requests

logger = logging.getLogger(__name__)


class AirflowUnavailable(RuntimeError):
    """Raised when the Airflow REST API cannot be reached or rejects the request."""


class AirflowClient:
    """Small HTTP client for the Airflow REST API (v1)."""

    def __init__(
        self,
        base_url: str | None = None,
        username: str | None = None,
        password: str | None = None,
        timeout_seconds: float = 10.0,
    ) -> None:
        self.base_url = (base_url or os.getenv("AIRFLOW_API_URL") or "http://airflow-webserver:8080").rstrip("/")
        self.auth = (
            username or os.getenv("AIRFLOW_ADMIN_USER") or "admin",
            password or os.getenv("AIRFLOW_ADMIN_PASSWORD") or "admin",
        )
        self.timeout_seconds = timeout_seconds

    def trigger_dag_run(self, dag_id: str, conf: dict[str, Any] | None = None) -> dict[str, Any]:
        """Declenche une nouvelle execution du DAG et retourne son dag_run_id/state.

        Un dag_run_id unique (timestamp) est genere cote Airflow par defaut -- pas besoin
        de le fournir, on le lit dans la reponse pour le suivi via get_dag_run_state().
        """
        url = f"{self.base_url}/api/v1/dags/{dag_id}/dagRuns"
        try:
            logger.info("Triggering Airflow DAG: POST %s conf=%s", url, conf)
            response = requests.post(
                url,
                json={"conf": conf or {}},
                auth=self.auth,
                timeout=self.timeout_seconds,
            )
        except requests.RequestException as exc:
            raise AirflowUnavailable(f"Airflow API unavailable: {exc}") from exc

        if response.status_code >= 400:
            try:
                detail = response.json().get("detail") or response.json().get("title")
            except ValueError:
                detail = response.text
            raise AirflowUnavailable(f"Failed to trigger DAG {dag_id}: {detail or response.status_code}")

        try:
            payload = response.json()
        except ValueError as exc:
            raise AirflowUnavailable(f"Airflow API returned an invalid JSON response for {dag_id}") from exc

        logger.info(
            "Airflow DAG triggered dag_id=%s dag_run_id=%s state=%s",
            dag_id,
            payload.get("dag_run_id"),
            payload.get("state"),
        )
        return payload

    def get_dag_run_state(self, dag_id: str, dag_run_id: str) -> str:
        """Retourne l'etat courant d'une execution (queued/running/success/failed)."""
        url = f"{self.base_url}/api/v1/dags/{dag_id}/dagRuns/{dag_run_id}"
        try:
            response = requests.get(url, auth=self.auth, timeout=self.timeout_seconds)
            response.raise_for_status()
        except requests.RequestException as exc:
            raise AirflowUnavailable(f"Airflow API unavailable: {exc}") from exc

        try:
            return str(response.json()["state"])
        except (ValueError, KeyError) as exc:
            raise AirflowUnavailable(f"Airflow API returned an invalid dagRun response for {dag_id}") from exc
