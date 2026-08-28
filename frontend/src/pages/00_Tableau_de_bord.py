"""Page Tableau de bord - vue d'ensemble agregee des bots et performances."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from components.alerts import show_feedback
from components.cards import KpiItem, render_kpi_cards
from components.headers import render_page_header, render_section_title
from components.prerequisites import render_exchange_prerequisite_state
from components.tables import render_dataframe
from layouts.page_shell import setup_page
from prerequisites.exchange import evaluate_exchange_prerequisite
from schemas.dashboard import DashboardOverview
from services.base import ServiceError
from services.dashboard_service import DEFAULT_PERIOD_DAYS, DashboardService
from utils.formatters import format_currency, format_datetime, format_pct


def _overview_to_dataframe(overview: DashboardOverview) -> pd.DataFrame:
    records = []
    for row in overview.bots:
        mode = "Live" if row.mode_live else "Paper"
        records.append(
            {
                "Bot": row.name,
                "Strategie": row.strategy,
                "Plateforme": row.exchange.capitalize(),
                "Statut": row.status,
                "Mode": mode,
                "PnL": format_currency(row.pnl_usdc),
                "ROI": format_pct(row.roi_pct),
                "Dernier signal": format_datetime(row.last_signal_at),
                "Derniere action": row.last_action_result,
            }
        )
    return pd.DataFrame(records)


def main() -> None:
    store, user = setup_page(title="Tableau de bord", icon="📊", page_key="dashboard")
    render_page_header(
        "Tableau de bord",
        "Vue d'ensemble agregee de vos bots Spot et de leurs performances.",
    )

    gate = evaluate_exchange_prerequisite("dashboard", user)
    if gate.should_block_content:
        render_exchange_prerequisite_state("dashboard", cta_key="cta_exchange_dashboard")
        return

    try:
        with st.spinner("Chargement du tableau de bord..."):
            overview = DashboardService(store).get_overview(period_days=DEFAULT_PERIOD_DAYS)
    except ServiceError as exc:
        show_feedback("error", str(exc))
        return

    if not overview.bots:
        show_feedback("warning", "Aucun bot disponible.")
        return

    render_kpi_cards(
        [
            KpiItem("Bots actifs", f"{overview.active_bots} / {overview.total_bots}"),
            KpiItem("PnL global", format_currency(overview.pnl_usdc)),
            KpiItem("ROI moyen", format_pct(overview.avg_roi_pct)),
            KpiItem("Frais globaux", format_currency(overview.fees_usdc)),
        ],
        columns=4,
    )

    render_section_title(
        "Derniers signaux par bot",
        caption=f"Periode de reference: {DEFAULT_PERIOD_DAYS} jours",
    )
    render_dataframe(_overview_to_dataframe(overview), key="dashboard_bots", height=320)


if __name__ == "__main__":
    main()
