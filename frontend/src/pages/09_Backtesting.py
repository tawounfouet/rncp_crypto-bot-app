"""Page Backtesting - simulation de strategie sur donnees historiques OHLCV."""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

import streamlit as st

try:
    import pandas as pd
    import plotly.graph_objects as go

    _HAS_PLOTLY = True
except ModuleNotFoundError:
    _HAS_PLOTLY = False

from components.alerts import show_feedback
from components.headers import render_page_header, render_section_title
from layouts.page_shell import setup_page
from services.api_client import BackendApiClient
from services.backtest_service import BacktestService
from state.session import get_access_token, get_theme_mode
from theme.plotly import plotly_line_color, themed_axis, themed_layout
from utils.streamlit_compat import form_submit_button as compat_form_submit_button

# ---------------------------------------------------------------------------
# Constantes
# ---------------------------------------------------------------------------

_SYMBOLS = [
    "BTCUSDC",
    "ETHUSDC",
    "BNBUSDC",
    "SOLUSDC",
    "ADAUSDC",
    "XRPUSDC",
    "DOGEUSDC",
    "DOTUSDC",
    "LINKUSDC",
    "AVAXUSDC",
    "LTCUSDC",
    "UNIUSDC",
    "MATICUSDC",
    "ATOMUSDC",
    "SHIBUSDC",
]
_TIMEFRAMES = ["1m", "5m", "15m", "30m", "1h", "4h", "1d"]

# Nombre de bougies attendu par timeframe pour 2 ans
_EXPECTED_2Y: dict[str, int] = {
    "1m": 1_051_200,
    "5m": 210_240,
    "15m": 70_080,
    "30m": 35_040,
    "1h": 17_520,
    "4h": 4_380,
    "1d": 730,
}


# ---------------------------------------------------------------------------
# Helpers formatage
# ---------------------------------------------------------------------------


def _pct(v: float | None) -> str:
    return f"{v:+.2f} %" if v is not None else "—"


def _f2(v: float | None, d: int = 2) -> str:
    return f"{v:.{d}f}" if v is not None else "—"


def _parse_iso(s: str | None) -> date | None:
    if not s:
        return None
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00")).date()
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Chargement données auxiliaires
# ---------------------------------------------------------------------------


def _load_strategies(client: BackendApiClient, token: str) -> list[dict]:
    resp = client.list_strategies(token)
    if not resp.success:
        return []
    d = resp.data
    if isinstance(d, dict):
        return d.get("data") or d.get("strategies") or []
    if isinstance(d, list):
        return d
    return []


def _load_coverage(client: BackendApiClient, token: str) -> list[dict]:
    resp = client.get_market_coverage(token)
    if not resp.success:
        return []
    d = resp.data
    if isinstance(d, dict):
        return d.get("data") or []
    if isinstance(d, list):
        return d
    return []


def _coverage_index(coverage: list[dict]) -> dict[tuple[str, str], dict]:
    """Retourne un dict indexé par (symbol, timeframe) pour lookup rapide."""
    return {(c["symbol"], c["timeframe"]): c for c in coverage}


# ---------------------------------------------------------------------------
# Onglet 1 : Lancer un backtest
# ---------------------------------------------------------------------------


def _render_result(result: dict) -> None:
    metrics = result.get("metrics") or {}
    transactions = result.get("transactions") or []
    theme_mode = get_theme_mode()

    render_section_title(
        "Résultats",
        f"{result.get('symbol', '')} {result.get('timeframe', '')} — "
        f"{str(result.get('start_date', ''))[:10]} → {str(result.get('end_date', ''))[:10]}",
    )

    # Métriques KPI
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Rendement total", _pct(metrics.get("total_return")))
    c2.metric("Balance finale", f"{metrics.get('final_balance', 0):.2f} USDC")
    c3.metric("Max drawdown", _pct(metrics.get("max_drawdown")))
    c4.metric("Ratio de Sharpe", _f2(metrics.get("sharpe_ratio"), 3))

    c5, c6, c7, c8 = st.columns(4)
    c5.metric("Taux de succès", f"{metrics.get('win_rate', 0):.1f} %")
    c6.metric("Total trades", str(metrics.get("total_trades", 0)))
    c7.metric("Trades gagnants", str(metrics.get("winning_trades", 0)))
    c8.metric("Profit factor", _f2(metrics.get("profit_factor")))

    if not transactions:
        st.info("Pas de transactions disponibles pour ce backtest.")
        return

    st.markdown("---")

    # Courbe d'equity
    try:
        rows = [
            {
                "date": pd.to_datetime(
                    t.get("exit_time") or t.get("entry_time"), utc=True, errors="coerce"
                ),
                "balance": float(t.get("balance_after") or 0),
            }
            for t in transactions
        ]
        df_eq = pd.DataFrame(rows).dropna(subset=["date"]).sort_values("date")
        if not df_eq.empty:
            render_section_title("Courbe d'equity")
            if _HAS_PLOTLY:
                fig = go.Figure()
                fig.add_trace(
                    go.Scatter(
                        x=df_eq["date"],
                        y=df_eq["balance"],
                        mode="lines",
                        name="Balance",
                        line=dict(color=plotly_line_color(theme_mode), width=2),
                    )
                )
                fig.update_layout(
                    **themed_layout(
                        theme_mode,
                        height=300,
                        margin=dict(l=0, r=0, t=10, b=0),
                        xaxis_title=None,
                        yaxis_title="USDC",
                    )
                )
                fig.update_xaxes(**themed_axis(theme_mode))
                fig.update_yaxes(**themed_axis(theme_mode))
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.line_chart(df_eq.set_index("date")[["balance"]])
    except Exception:
        pass

    st.markdown("---")

    # Table des trades
    render_section_title("Détail des trades")
    try:
        wanted = [
            "entry_time",
            "exit_time",
            "side",
            "entry_price",
            "exit_price",
            "size",
            "pnl",
            "pnl_pct",
        ]
        df_tr = pd.DataFrame(transactions)
        cols_present = [c for c in wanted if c in df_tr.columns]
        if cols_present:
            st.dataframe(df_tr[cols_present], use_container_width=True)
    except Exception:
        pass


def _render_backtest_tab(
    service: BacktestService, strategies: list[dict], coverage_idx: dict
) -> None:
    last_result = st.session_state.get("last_backtest_result")

    if last_result:
        _render_result(last_result)
        st.markdown("---")
        if st.button("Nouveau backtest", key="bt_clear"):
            del st.session_state["last_backtest_result"]
            st.rerun()
        return

    if not strategies:
        show_feedback(
            "warning",
            "Aucune stratégie disponible. Créez d'abord une stratégie depuis la page Contrôle Bot Spot.",
        )
        return

    render_section_title(
        "Paramètres du backtest",
        "Simulation sur données OHLCV stockées dans PostgreSQL.",
    )

    strategy_options = {f"{s['name']} ({s.get('strategy_type', '')})": s["id"] for s in strategies}

    with st.form("backtest_form", clear_on_submit=False):
        col1, col2 = st.columns(2)
        with col1:
            strategy_label = st.selectbox("Stratégie", options=list(strategy_options.keys()))
            symbol = st.selectbox("Paire", options=_SYMBOLS)
            timeframe = st.selectbox("Timeframe", options=_TIMEFRAMES, index=4)

        with col2:
            # Adapter les dates par défaut selon les données disponibles
            cov = coverage_idx.get((symbol, timeframe))
            if cov:
                default_start = _parse_iso(cov["first_candle"]) or (
                    date.today() - timedelta(days=90)
                )
                default_end = _parse_iso(cov["last_candle"]) or date.today()
                candle_info = (
                    f"{cov['count']:,} bougies disponibles — "
                    f"{str(cov.get('first_candle', ''))[:10]} → "
                    f"{str(cov.get('last_candle', ''))[:10]}"
                )
            else:
                default_start = date.today() - timedelta(days=90)
                default_end = date.today()
                candle_info = None

            start_date = st.date_input("Date de début", value=default_start)
            end_date = st.date_input("Date de fin", value=default_end)
            initial_balance = st.number_input(
                "Capital initial (USDC)",
                min_value=100.0,
                max_value=1_000_000.0,
                value=10_000.0,
                step=500.0,
            )

        if candle_info:
            st.caption(f"Données en base : {candle_info}")
        elif (symbol, timeframe) not in coverage_idx:
            st.warning(
                f"Aucune donnée pour {symbol}/{timeframe}. "
                "Importez d'abord l'historique depuis l'onglet **Données historiques**."
            )

        submitted = compat_form_submit_button("Lancer le backtest", type="primary", width="stretch")

    if submitted:
        if start_date >= end_date:
            show_feedback("error", "La date de début doit être antérieure à la date de fin.")
            return

        strategy_id = strategy_options[strategy_label]
        with st.spinner("Simulation en cours... (quelques secondes)"):
            success, message, result = service.run_backtest(
                strategy_id=strategy_id,
                symbol=symbol,
                timeframe=timeframe,
                start_date=start_date.isoformat(),
                end_date=end_date.isoformat(),
                initial_balance=float(initial_balance),
            )

        show_feedback("success" if success else "error", message)
        if success and result:
            st.session_state["last_backtest_result"] = result
            st.rerun()


# ---------------------------------------------------------------------------
# Onglet 2 : Données historiques
# ---------------------------------------------------------------------------


def _render_coverage_table(coverage: list[dict]) -> None:
    if not coverage:
        st.info("Aucune donnée historique en base pour le moment.")
        return

    rows = []
    for c in coverage:
        tf = c["timeframe"]
        count = c["count"]
        expected = _EXPECTED_2Y.get(tf)
        completeness = f"{min(100, count / expected * 100):.0f} %" if expected else "—"
        rows.append(
            {
                "Paire": c["symbol"],
                "Timeframe": tf,
                "Bougies": f"{count:,}",
                "Première": str(c.get("first_candle", ""))[:10],
                "Dernière": str(c.get("last_candle", ""))[:10],
                "Complétude 2 ans": completeness,
            }
        )

    df = pd.DataFrame(rows)
    st.dataframe(df, use_container_width=True, hide_index=True)


def _render_import_form(client: BackendApiClient, token: str) -> None:
    render_section_title(
        "Importer des données depuis Binance",
        "Déclenche un import direct via le backend (API Binance publique, sans clé).",
    )

    with st.form("import_form", clear_on_submit=False):
        col1, col2 = st.columns(2)
        with col1:
            symbol = st.selectbox("Paire", options=_SYMBOLS, key="imp_symbol")
            interval = st.selectbox("Timeframe", options=_TIMEFRAMES, index=4, key="imp_tf")
        with col2:
            default_end = date.today()
            default_start = default_end - timedelta(days=365 * 2)
            start_date = st.date_input("Date de début", value=default_start, key="imp_start")
            end_date = st.date_input("Date de fin", value=default_end, key="imp_end")

        # Estimation de la durée
        if interval in _EXPECTED_2Y:
            days = (end_date - start_date).days
            hours_per_day = {
                "1m": 1440,
                "5m": 288,
                "15m": 96,
                "30m": 48,
                "1h": 24,
                "4h": 6,
                "1d": 1,
            }.get(interval, 24)
            estimated_candles = days * hours_per_day
            st.caption(
                f"Estimation : ~{estimated_candles:,} bougies — "
                f"durée attendue ~{max(5, estimated_candles // 1000 * 3)} s "
                f"(python-binance pagine automatiquement par blocs de 1 000)."
            )

        submitted = compat_form_submit_button("Importer", type="primary", width="stretch")

    if submitted:
        if start_date >= end_date:
            show_feedback("error", "La date de début doit être antérieure à la date de fin.")
            return

        start_iso = datetime(
            start_date.year, start_date.month, start_date.day, tzinfo=timezone.utc
        ).isoformat()
        end_iso = datetime(
            end_date.year, end_date.month, end_date.day, tzinfo=timezone.utc
        ).isoformat()

        with st.spinner(
            f"Import {symbol} {interval} en cours... (patientez, peut prendre plusieurs dizaines de secondes)"
        ):
            resp = client.insert_market_data(
                token,
                symbol=symbol,
                interval=interval,
                start_time=start_iso,
                end_time=end_iso,
                limit=1000,
            )

        if resp.success:
            data = resp.data or {}
            if isinstance(data, dict) and "data" in data:
                data = data["data"]
            total = data.get("total", "?") if isinstance(data, dict) else "?"
            show_feedback(
                "success",
                f"Import terminé : {total} bougies traitées pour {symbol} {interval}.",
            )
            st.rerun()
        else:
            err = resp.error or str(resp.data)
            show_feedback("error", f"Échec import : {err}")


def _render_data_tab(client: BackendApiClient, token: str, coverage: list[dict]) -> None:
    render_section_title(
        "Données OHLCV en base",
        "Résumé des séries temporelles stockées dans PostgreSQL (table market_data).",
    )
    _render_coverage_table(coverage)

    st.markdown("---")
    _render_import_form(client, token)

    st.markdown("---")
    with st.container(border=True):
        st.markdown("##### Backfill automatisé via Airflow")
        st.caption(
            "Pour un backfill planifié (ex. 2 ans de 1h sur BTCUSDC + ETHUSDC), "
            "déclenchez le DAG Airflow depuis l'UI ou via CLI :"
        )
        st.code(
            "airflow dags trigger backfill_ohlcv_binance \\\n"
            '  --conf \'{"symbols": ["BTCUSDC", "ETHUSDC"], "interval": "1h",\n'
            '           "start_date": "2024-06-01", "end_date": "2026-06-12"}\'',
            language="bash",
        )
        st.caption(
            "Le DAG `backfill_ohlcv_binance` gère la pagination automatiquement "
            "et passe par MinIO (Parquet) avant PostgreSQL."
        )


# ---------------------------------------------------------------------------
# Onglet 3 : Historique des backtests
# ---------------------------------------------------------------------------


def _render_history_tab(service: BacktestService) -> None:
    render_section_title("Backtests passés")
    history = service.list_backtests()

    if not history:
        st.info("Aucun backtest effectué pour le moment.")
        return

    for bt in history:
        m = bt.get("metrics") or {}
        with st.container(border=True):
            col_info, col_btn = st.columns([5, 1])
            with col_info:
                ret = m.get("total_return")
                ret_str = f"{ret:+.2f} %" if ret is not None else "—"
                st.write(
                    f"**{bt.get('symbol', '')} {bt.get('timeframe', '')}** — "
                    f"{str(bt.get('start_date', ''))[:10]} → {str(bt.get('end_date', ''))[:10]} | "
                    f"Rendement : **{ret_str}** | "
                    f"Drawdown : {_pct(m.get('max_drawdown'))} | "
                    f"Trades : {m.get('total_trades', 0)} | "
                    f"Win rate : {m.get('win_rate', 0):.1f} %"
                )
            with col_btn:
                if st.button("Détail", key=f"bt_hist_{bt.get('id', '')}"):
                    detail = service.get_backtest(bt["id"])
                    if detail:
                        st.session_state["last_backtest_result"] = detail
                        st.session_state["_jump_to_bt_tab"] = True
                    st.rerun()


# ---------------------------------------------------------------------------
# Point d'entrée
# ---------------------------------------------------------------------------


def main() -> None:
    store, user = setup_page(title="Backtesting", icon="📊", page_key="backtesting")
    render_page_header(
        "Backtesting",
        "Simulez vos stratégies sur des données OHLCV historiques — importez l'historique puis lancez la simulation.",
    )

    token = get_access_token()
    if not token:
        show_feedback("warning", "Vous devez être connecté pour accéder au backtesting.")
        return

    client = BackendApiClient()
    service = BacktestService(store, client)

    strategies: list[dict] = []
    coverage: list[dict] = []
    try:
        strategies = _load_strategies(client, token)
    except Exception:
        pass
    try:
        coverage = _load_coverage(client, token)
    except Exception:
        pass

    coverage_idx = _coverage_index(coverage)

    tab_bt, tab_data, tab_hist = st.tabs(["📈 Backtest", "🗄️ Données historiques", "📋 Historique"])

    # Saut automatique vers l'onglet Backtest quand on clique "Détail" dans l'historique
    # (Streamlit ne permet pas de sélectionner un onglet programmatiquement,
    #  mais on affiche un lien indicatif)
    if st.session_state.pop("_jump_to_bt_tab", False):
        st.info("Résultat chargé — consultez l'onglet **📈 Backtest**.")

    with tab_bt:
        _render_backtest_tab(service, strategies, coverage_idx)

    with tab_data:
        _render_data_tab(client, token, coverage)

    with tab_hist:
        _render_history_tab(service)


if __name__ == "__main__":
    main()
