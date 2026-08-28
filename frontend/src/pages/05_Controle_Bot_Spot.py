"""Page Controle Bot Spot."""

from __future__ import annotations

from datetime import UTC, datetime

import streamlit as st

from components.alerts import show_feedback
from components.badges import render_status_badge
from components.headers import render_page_header, render_section_title
from components.prerequisites import render_exchange_prerequisite_state
from layouts.page_shell import setup_page
from prerequisites.exchange import evaluate_exchange_prerequisite
from schemas.bot import BotInfo
from services.base import ServiceError
from services.bot_control_service import (
    BotControlService,
    normalise_decision_trace,
    select_badge_decision_trace,
)
from utils.constants import ACTION_PAUSE, ACTION_START, ACTION_STOP
from utils.formatters import format_datetime
from utils.streamlit_compat import button as compat_button
from utils.streamlit_compat import dataframe as compat_dataframe


def _heartbeat_label(heartbeat_at: datetime) -> str:
    if heartbeat_at.tzinfo is None:
        heartbeat_at = heartbeat_at.replace(tzinfo=UTC)
    heartbeat_at = heartbeat_at.astimezone(UTC)
    delta = datetime.now(UTC) - heartbeat_at
    if delta.total_seconds() < 90:
        return "Actif"
    if delta.total_seconds() < 300:
        return "A surveiller"
    return "Retard heartbeat"


def _parse_backend_datetime(value: object) -> datetime | None:
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, str) and value.strip():
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
    else:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _short_id(value: object) -> str:
    text = str(value or "").strip()
    return text[:8] if text else "-"


def _link_orders_to_decisions(
    decisions: list[dict[str, object]],
    orders: list[dict[str, object]],
) -> tuple[dict[str, str], dict[str, list[dict[str, object]]]]:
    decision_traces = [normalise_decision_trace(item) for item in decisions]
    decision_times = {
        trace["id"]: _parse_backend_datetime(trace.get("timestamp"))
        for trace in decision_traces
        if trace.get("id") and trace.get("id") != "-"
    }
    order_to_decision: dict[str, str] = {}
    decision_to_orders: dict[str, list[dict[str, object]]] = {}
    for order in orders:
        order_id = str(order.get("id") or "")
        order_time = _parse_backend_datetime(order.get("created_at"))
        order_side = str(order.get("side") or "").upper()
        if not order_id or order_time is None or order_side not in {"BUY", "SELL"}:
            continue
        candidates = []
        for trace in decision_traces:
            decision_id = str(trace.get("id") or "")
            decision_time = decision_times.get(decision_id)
            if decision_time is None or str(trace.get("final_action")).upper() != order_side:
                continue
            elapsed = (order_time - decision_time).total_seconds()
            if 0 <= elapsed <= 300:
                candidates.append((elapsed, decision_id))
        if not candidates:
            continue
        _, decision_id = min(candidates, key=lambda item: item[0])
        order_to_decision[order_id] = decision_id
        decision_to_orders.setdefault(decision_id, []).append(order)
    return order_to_decision, decision_to_orders


def _render_ai_badge(bot: BotInfo, latest_trace: dict[str, object] | None = None) -> None:
    source = str((latest_trace or {}).get("model_source") or bot.model_source_label)
    registry = str((latest_trace or {}).get("registry_source") or bot.registry_source_label)
    model_name = str((latest_trace or {}).get("model_name") or bot.model_name)
    model_version = str((latest_trace or {}).get("model_version") or bot.model_version)
    last_signal = str((latest_trace or {}).get("signal") or bot.last_signal)
    st.caption(
        f"IA: {source} | Registry: {registry} | Modele: {model_name} | "
        f"Version: {model_version} | Mode: {bot.mode_label} | Dernier signal: {last_signal}"
    )


def _render_decision_details(
    traces: list[dict[str, object]],
    decision_to_orders: dict[str, list[dict[str, object]]],
) -> None:
    for trace in traces:
        decision_id = str(trace.get("id") or "-")
        label = (
            f"{trace.get('timestamp')} | {trace.get('model_source')} | "
            f"{trace.get('signal')} -> {trace.get('final_action')} | {trace.get('risk_decision')}"
        )
        with st.expander(label):
            c1, c2, c3, c4 = st.columns(4)
            with c1:
                st.metric("Signal IA", trace.get("raw_ai_signal", "-"))
            with c2:
                st.metric("Confiance", trace.get("confidence", "-"))
            with c3:
                st.metric("Signal deterministe", trace.get("deterministic_signal", "-"))
            with c4:
                st.metric("Decision finale", trace.get("final_action", "-"))

            st.write(f"**Moteur**: {trace.get('model_source', '-')}")
            st.write(
                f"**MLflow**: {trace.get('model_name', '-')} {trace.get('model_version', '-')}"
            )
            st.write(f"**Risk Manager**: {trace.get('risk_decision', '-')}")
            st.write(f"**Raison**: {trace.get('reason', '-')}")

            linked_orders = decision_to_orders.get(decision_id, [])
            if linked_orders:
                order_labels = [
                    f"{order.get('side')} {order.get('symbol')} #{order.get('binance_order_id') or order.get('id')}"
                    for order in linked_orders
                ]
                st.write(f"**Ordre envoye**: Oui ({', '.join(order_labels)})")
            elif trace.get("order_expected"):
                st.write(
                    "**Ordre envoye**: action finale trade, ordre non retrouve dans ce journal."
                )
            else:
                st.write("**Ordre envoye**: Non")

            features = trace.get("features") if isinstance(trace.get("features"), dict) else {}
            if features:
                st.caption("Features envoyees au modele")
                compat_dataframe(
                    [{"feature": key, "value": value} for key, value in sorted(features.items())],
                    width="stretch",
                    hide_index=True,
                )
            else:
                st.caption("Aucune feature IA disponible pour cette decision.")


def _render_runtime_journal(
    service: BotControlService,
    bot: BotInfo,
    *,
    prefetched_decisions: list[dict[str, object]] | None = None,
) -> None:
    if not service.has_backend_session():
        return

    st.markdown("##### Journal Testnet")
    try:
        performance = service.get_performance(bot.id)
        position = service.get_position(bot.id)
        decisions = (
            prefetched_decisions
            if prefetched_decisions is not None
            else service.list_decisions(bot.id)
        )
        orders = service.list_orders(bot.id)
        trades = service.list_trades(bot.id)
    except ServiceError as exc:
        show_feedback("error", str(exc))
        return

    all_traces = [normalise_decision_trace(item) for item in decisions]
    traces = all_traces[:10]
    latest_trace = select_badge_decision_trace(all_traces)
    _render_ai_badge(bot, latest_trace)
    order_to_decision, decision_to_orders = _link_orders_to_decisions(decisions, orders)

    if performance:
        k1, k2, k3, k4 = st.columns(4)
        with k1:
            st.metric("Ordres", performance.get("total_orders", 0))
        with k2:
            st.metric("Trades", performance.get("total_trades", 0))
        with k3:
            st.metric(
                "Dernier signal",
                (latest_trace or {}).get("signal") or performance.get("last_signal") or "-",
            )
        with k4:
            st.metric("Action", performance.get("last_action") or "-")

    if position:
        p1, p2, p3 = st.columns(3)
        with p1:
            st.metric("Quantite", position.get("quantity", "0"))
        with p2:
            st.metric("Prix moyen", position.get("average_entry_price") or "-")
        with p3:
            st.metric("PnL realise", position.get("realized_pnl", "0"))

    if traces:
        st.caption("Decisions")
        compat_dataframe(
            [
                {
                    "date": trace.get("timestamp"),
                    "model_source": trace.get("model_source"),
                    "registry_source": trace.get("registry_source"),
                    "model_name": trace.get("model_name"),
                    "model_version": trace.get("model_version"),
                    "confidence": trace.get("confidence"),
                    "raw_ai_signal": trace.get("raw_ai_signal"),
                    "deterministic_signal": trace.get("deterministic_signal"),
                    "final_action": trace.get("final_action"),
                    "risk_decision": trace.get("risk_decision"),
                    "reason": trace.get("reason"),
                }
                for trace in traces
            ],
            width="stretch",
            hide_index=True,
        )
        _render_decision_details(traces, decision_to_orders)

    if orders:
        st.caption("Ordres")
        compat_dataframe(
            [
                {
                    "date": item.get("created_at"),
                    "decision_ia": _short_id(order_to_decision.get(str(item.get("id") or ""))),
                    "symbole": item.get("symbol"),
                    "side": item.get("side"),
                    "type": item.get("order_type"),
                    "statut": item.get("status"),
                    "binance_id": item.get("binance_order_id"),
                }
                for item in orders[:10]
            ],
            width="stretch",
            hide_index=True,
        )

    if trades:
        st.caption("Trades")
        compat_dataframe(
            [
                {
                    "date": item.get("trade_time"),
                    "decision_ia": _short_id(
                        order_to_decision.get(str(item.get("order_id") or ""))
                    ),
                    "symbole": item.get("symbol"),
                    "side": item.get("side"),
                    "quantite": item.get("quantity"),
                    "prix": item.get("price"),
                    "fee": item.get("fee"),
                }
                for item in trades[:10]
            ],
            width="stretch",
            hide_index=True,
        )

    if not any([performance, position, decisions, orders, trades]):
        show_feedback("info", "Aucune execution journalisee.")


def main() -> None:
    store, user = setup_page(title="Controle Bot Spot", icon="🤖", page_key="bot_control")
    render_page_header(
        "Controle Bot Spot",
        "Supervision et actions de pilotage: start, pause, stop (avec confirmation).",
    )

    gate = evaluate_exchange_prerequisite("bot_control", user)
    if gate.missing:
        render_exchange_prerequisite_state("bot_control", cta_key="cta_exchange_bot_control")

    service = BotControlService(store)

    try:
        with st.spinner("Chargement des bots..."):
            bots = service.list_bots()
    except ServiceError as exc:
        show_feedback("error", str(exc))
        return

    if not bots:
        show_feedback("info", "Aucun bot configure.")
        return

    if gate.missing:
        render_section_title(
            "Bots Spot disponibles",
            "Configuration Binance requise avant toute supervision d'execution.",
        )
        st.markdown("<div class='premium-card'>", unsafe_allow_html=True)
        for bot in bots:
            st.markdown(f"- **{bot.name}**")
        st.markdown("</div>", unsafe_allow_html=True)
        return

    for bot in bots:
        prefetched_decisions = None
        badge_trace = None
        if service.has_backend_session():
            try:
                prefetched_decisions = service.list_decisions(bot.id)
                badge_trace = select_badge_decision_trace(
                    [normalise_decision_trace(item) for item in prefetched_decisions]
                )
            except ServiceError:
                prefetched_decisions = None
                badge_trace = None

        st.markdown("<div class='premium-card'>", unsafe_allow_html=True)
        head_col, actions_col = st.columns([2.1, 1.2], gap="medium")
        with head_col:
            st.markdown(f"#### {bot.name}")
            render_status_badge("Statut", bot.status.value)
            render_status_badge("Plateforme", bot.exchange.capitalize())
            render_status_badge("Mode", bot.mode_label)
            _render_ai_badge(bot, badge_trace)
            st.caption(
                f"Strategie: {bot.strategy} | "
                f"Heartbeat: {format_datetime(bot.heartbeat_at)} "
                f"({_heartbeat_label(bot.heartbeat_at)})"
            )
            st.caption(f"Derniere action: {bot.last_action_result}")
        with actions_col:
            btn_col1, btn_col2, btn_col3 = st.columns(3)
            with btn_col1:
                if compat_button(
                    "Start",
                    key=f"start_{bot.id}",
                    width="stretch",
                    disabled=gate.actions_disabled,
                ):
                    result = service.apply_action(bot.id, ACTION_START)
                    show_feedback("success" if result.success else "error", result.message)
                    st.rerun()
            with btn_col2:
                if compat_button(
                    "Pause",
                    key=f"pause_{bot.id}",
                    width="stretch",
                    disabled=gate.actions_disabled,
                ):
                    result = service.apply_action(bot.id, ACTION_PAUSE)
                    show_feedback("success" if result.success else "error", result.message)
                    st.rerun()
            with btn_col3:
                if compat_button(
                    "Stop",
                    key=f"stop_{bot.id}",
                    width="stretch",
                    disabled=gate.actions_disabled,
                ):
                    st.session_state[f"confirm_stop_{bot.id}"] = True

        if (not gate.actions_disabled) and st.session_state.get(f"confirm_stop_{bot.id}", False):
            show_feedback("warning", f"Confirmer l'arret du bot {bot.name}.")
            c1, c2 = st.columns(2)
            with c1:
                if st.button("Confirmer stop", key=f"confirm_{bot.id}", type="primary"):
                    result = service.apply_action(bot.id, ACTION_STOP)
                    st.session_state[f"confirm_stop_{bot.id}"] = False
                    show_feedback("success" if result.success else "error", result.message)
                    st.rerun()
            with c2:
                if st.button("Annuler", key=f"cancel_{bot.id}"):
                    st.session_state[f"confirm_stop_{bot.id}"] = False
                    st.rerun()

        _render_runtime_journal(service, bot, prefetched_decisions=prefetched_decisions)

        st.markdown("</div>", unsafe_allow_html=True)
        st.markdown("<br/>", unsafe_allow_html=True)


if __name__ == "__main__":
    main()
