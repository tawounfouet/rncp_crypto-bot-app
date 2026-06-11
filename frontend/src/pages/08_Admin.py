"""Page Admin."""

from __future__ import annotations

import streamlit as st

from components.alerts import show_feedback
from components.badges import render_status_badge
from components.headers import render_page_header, render_section_title
from components.tables import render_dataframe
from layouts.page_shell import setup_page
from schemas.common import UserRole, UserStatus
from services.admin_service import AdminService
from services.base import ServiceError
from utils.formatters import bool_to_label, format_datetime
from utils.selectors import models_to_dataframe
from utils.streamlit_compat import button as compat_button


def main() -> None:
    store, _ = setup_page(title="Admin", icon="🛡️", page_key="admin")
    render_page_header(
        "Administration",
        "Gestion des utilisateurs: statut, role, dernier login et details.",
    )

    service = AdminService(store)
    try:
        rows = service.list_users()
    except ServiceError as exc:
        show_feedback("error", str(exc))
        return

    if not rows:
        show_feedback("warning", "Aucun utilisateur en base de donnees.")
        return

    users_df = models_to_dataframe(rows)
    users_df = users_df[
        [
            "email",
            "role",
            "status",
            "binance_configured",
            "last_login",
            "first_name",
            "last_name",
        ]
    ]
    users_df["last_login"] = users_df["last_login"].apply(format_datetime)
    users_df["binance_configured"] = users_df["binance_configured"].apply(bool_to_label)
    users_df = users_df.rename(columns={"binance_configured": "Binance configuré"})

    filter_col1, filter_col2 = st.columns(2)
    with filter_col1:
        role_filter = st.selectbox("Filtre role", options=["TOUS", "USER", "ADMIN"])
    with filter_col2:
        status_filter = st.selectbox(
            "Filtre statut", options=["TOUS", "ENABLED", "DISABLED", "PENDING"]
        )

    filtered_df = users_df.copy()
    if role_filter != "TOUS":
        filtered_df = filtered_df[filtered_df["role"] == role_filter]
    if status_filter != "TOUS":
        filtered_df = filtered_df[filtered_df["status"] == status_filter]

    render_section_title("Liste utilisateurs")
    render_dataframe(filtered_df, key="admin_users_table", height=330)

    st.markdown("<hr class='divider-soft'/>", unsafe_allow_html=True)
    render_section_title("Detail utilisateur")
    selected_email = st.selectbox(
        "Selection utilisateur", options=sorted(users_df["email"].tolist())
    )
    try:
        detail = service.get_user_detail(selected_email)
    except ServiceError as exc:
        show_feedback("error", str(exc))
        return

    left, right = st.columns([1, 1], gap="large")
    with left:
        st.markdown("<div class='premium-card'>", unsafe_allow_html=True)
        st.write(f"Email: `{detail.email}`")
        st.write(f"Nom: {detail.first_name} {detail.last_name or ''}")
        render_status_badge("Role", detail.role.value)
        render_status_badge("Statut", detail.status.value)
        st.caption(f"Dernier login: {format_datetime(detail.last_login)}")
        st.caption(f"Cree le: {format_datetime(detail.created_at)}")
        st.caption(f"Binance configure: {bool_to_label(detail.binance_configured)}")
        st.caption(f"Echecs login: {detail.failed_login_count}")
        st.markdown("</div>", unsafe_allow_html=True)

    with right:
        st.markdown("<div class='premium-card'>", unsafe_allow_html=True)
        st.markdown("##### Actions admin")
        target_enabled = detail.status != UserStatus.ENABLED
        toggle_label = "Activer le compte" if target_enabled else "Desactiver le compte"
        confirm_toggle = st.checkbox(
            f"Je confirme: {toggle_label.lower()}",
            key=f"confirm_toggle_{detail.email}",
        )
        if compat_button(toggle_label, width="stretch", disabled=not confirm_toggle):
            ok, message = service.set_enabled(detail.email, target_enabled)
            show_feedback("success" if ok else "error", message)
            if ok:
                st.rerun()

        st.markdown("---")
        next_role = st.selectbox(
            "Nouveau role",
            options=[UserRole.USER, UserRole.ADMIN],
            format_func=lambda role: role.value,
            index=0 if detail.role == UserRole.USER else 1,
        )
        confirm_role = st.checkbox(
            "Je confirme le changement de role",
            key=f"confirm_role_{detail.email}",
        )
        if compat_button("Appliquer le role", width="stretch", disabled=not confirm_role):
            ok, message = service.set_role(detail.email, next_role)
            show_feedback("success" if ok else "error", message)
            if ok:
                st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)


if __name__ == "__main__":
    main()
