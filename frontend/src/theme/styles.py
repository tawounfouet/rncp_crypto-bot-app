"""Styles globaux Streamlit."""

from __future__ import annotations

import streamlit as st

from theme.manager import DEFAULT_THEME_MODE, ThemeMode
from theme.tokens import get_theme_tokens


def build_global_css(theme_mode: ThemeMode = DEFAULT_THEME_MODE) -> str:
    tokens = get_theme_tokens(theme_mode)
    return f"""
    <style>
      @import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@400;500;600;700&display=swap');
      /* theme-mode:{theme_mode} */

      :root {{
        --primary-color: {tokens["accent"]};
        --background-color: {tokens["bg_main"]};
        --secondary-background-color: {tokens["bg_surface"]};
        --text-color: {tokens["txt_primary"]};

        --bg-main: {tokens["bg_main"]};
        --bg-surface: {tokens["bg_surface"]};
        --bg-card: {tokens["bg_card"]};
        --bg-card-hover: {tokens["bg_card_hover"]};
        --txt-primary: {tokens["txt_primary"]};
        --txt-secondary: {tokens["txt_secondary"]};
        --accent: {tokens["accent"]};
        --accent-alt: {tokens["accent_alt"]};
        --danger: {tokens["danger"]};
        --warning: {tokens["warning"]};
        --success: {tokens["success"]};
        --info: {tokens["info"]};
        --border: {tokens["border"]};
        --border-hover: {tokens["border_hover"]};
        --shadow: {tokens["shadow"]};
        --radius: {tokens["radius"]};
        --input-bg: {tokens["input_bg"]};
        --input-border: {tokens["input_border"]};
        --dropdown-bg: {tokens["dropdown_bg"]};
        --dropdown-text: {tokens["dropdown_text"]};
        --dropdown-hover-bg: {tokens["dropdown_hover_bg"]};
        --dropdown-selected-bg: {tokens["dropdown_selected_bg"]};
        --dropdown-selected-text: {tokens["dropdown_selected_text"]};
        --dropdown-border: {tokens["dropdown_border"]};
        --dropdown-shadow: {tokens["dropdown_shadow"]};
        --table-header-bg: {tokens["table_header_bg"]};
        --table-row-bg: {tokens["table_row_bg"]};
        --table-row-alt-bg: {tokens["table_row_alt_bg"]};
        --table-row-hover: {tokens["table_row_hover"]};
        --sidebar-bg: {tokens["sidebar_bg"]};
        --sidebar-text: {tokens["sidebar_text"]};
        --sidebar-muted-text: {tokens["sidebar_muted_text"]};
        --sidebar-nav-bg: {tokens["sidebar_nav_bg"]};
        --sidebar-nav-hover-bg: {tokens["sidebar_nav_hover_bg"]};
        --sidebar-nav-active-bg: {tokens["sidebar_nav_active_bg"]};
        --button-primary-bg: {tokens["button_primary_bg"]};
        --button-primary-bg-hover: {tokens["button_primary_bg_hover"]};
        --button-primary-txt: {tokens["button_primary_txt"]};
        --button-secondary-bg: {tokens["button_secondary_bg"]};
        --button-secondary-bg-hover: {tokens["button_secondary_bg_hover"]};
        --button-secondary-txt: {tokens["button_secondary_txt"]};
        --button-secondary-border: {tokens["button_secondary_border"]};
        --input-placeholder: {tokens["input_placeholder"]};
        --alert-info-bg: {tokens["alert_info_bg"]};
        --alert-info-txt: {tokens["alert_info_txt"]};
        --alert-info-border: {tokens["alert_info_border"]};
        --alert-success-bg: {tokens["alert_success_bg"]};
        --alert-success-txt: {tokens["alert_success_txt"]};
        --alert-success-border: {tokens["alert_success_border"]};
        --alert-warning-bg: {tokens["alert_warning_bg"]};
        --alert-warning-txt: {tokens["alert_warning_txt"]};
        --alert-warning-border: {tokens["alert_warning_border"]};
        --alert-error-bg: {tokens["alert_error_bg"]};
        --alert-error-txt: {tokens["alert_error_txt"]};
        --alert-error-border: {tokens["alert_error_border"]};

        --badge-ok-bg: {tokens["badge_ok_bg"]};
        --badge-ok-txt: {tokens["badge_ok_txt"]};
        --badge-ok-border: {tokens["badge_ok_border"]};
        --badge-warning-bg: {tokens["badge_warning_bg"]};
        --badge-warning-txt: {tokens["badge_warning_txt"]};
        --badge-warning-border: {tokens["badge_warning_border"]};
        --badge-error-bg: {tokens["badge_error_bg"]};
        --badge-error-txt: {tokens["badge_error_txt"]};
        --badge-error-border: {tokens["badge_error_border"]};
      }}

      .stApp,
      [data-testid="stAppViewContainer"],
      section[data-testid="stSidebar"] {{
        --primary-color: {tokens["accent"]} !important;
        --background-color: {tokens["bg_main"]} !important;
        --secondary-background-color: {tokens["bg_surface"]} !important;
        --text-color: {tokens["txt_primary"]} !important;
      }}

      .stApp {{
        background:
          radial-gradient(circle at 5% 5%, {tokens["app_spot_a"]}, transparent 28%),
          radial-gradient(circle at 95% 0%, {tokens["app_spot_b"]}, transparent 24%),
          linear-gradient(180deg, {tokens["app_bg_gradient_start"]} 0%, {tokens["app_bg_gradient_end"]} 100%);
        color: var(--txt-primary);
        font-family: 'Space Grotesk', 'Segoe UI', sans-serif;
        color-scheme: {tokens["native_color_scheme"]};
      }}

      header[data-testid="stHeader"] {{
        background: var(--bg-surface) !important;
        opacity: 0.98;
        border-bottom: 1px solid var(--border);
      }}

      header[data-testid="stHeader"] * {{
        color: var(--txt-secondary);
      }}

      section[data-testid="stSidebar"] {{
        background: var(--sidebar-bg) !important;
        border-right: 1px solid var(--border);
      }}

      section[data-testid="stSidebar"] > div {{
        background: var(--sidebar-bg) !important;
      }}

      section[data-testid="stSidebar"] * {{
        color: var(--sidebar-text);
      }}

      section[data-testid="stSidebar"] hr {{
        border-color: var(--border);
      }}

      section[data-testid="stSidebar"] [data-testid="stPageLink"],
      section[data-testid="stSidebar"] [data-testid="stPageLink"] a,
      section[data-testid="stSidebar"] [data-testid="stPageLink-NavLink"] {{
        background: var(--sidebar-nav-bg);
        border-radius: 0.45rem;
        border: 1px solid transparent;
        color: var(--sidebar-text) !important;
      }}

      section[data-testid="stSidebar"] [data-testid="stPageLink"]:hover,
      section[data-testid="stSidebar"] [data-testid="stPageLink"] a:hover,
      section[data-testid="stSidebar"] [data-testid="stPageLink-NavLink"]:hover {{
        background: var(--sidebar-nav-hover-bg);
      }}

      section[data-testid="stSidebar"] [aria-current="page"] {{
        background: var(--sidebar-nav-active-bg) !important;
        border-color: color-mix(in srgb, var(--accent) 32%, var(--border)) !important;
      }}

      section[data-testid="stSidebar"] [data-testid="stCaptionContainer"] p {{
        color: var(--sidebar-muted-text) !important;
      }}

      section[data-testid="stSidebar"] .block-container {{
        padding-top: 0.4rem;
      }}

      .sidebar-logo-wrap {{
        text-align: center !important;
        margin-bottom: 0.4rem;
      }}

      #sidebar-logo-img {{
        width: 96px !important;
        height: auto !important;
        display: inline-block !important;
        margin: 0 !important;
      }}

      .block-container {{
        padding-top: 1.2rem;
        padding-bottom: 2.4rem;
      }}

      .premium-card {{
        background: linear-gradient(
          160deg,
          {tokens["card_gradient_from"]},
          {tokens["card_gradient_to"]}
        );
        border: 1px solid var(--border);
        border-radius: var(--radius);
        padding: 1rem 1rem;
        box-shadow: var(--shadow);
        transition: all .15s ease-in-out;
      }}

      .premium-card,
      .premium-card p,
      .premium-card li,
      .premium-card span {{
        color: var(--txt-secondary);
      }}

      .premium-card h1,
      .premium-card h2,
      .premium-card h3,
      .premium-card h4,
      .premium-card h5,
      .premium-card h6,
      .premium-card b,
      .premium-card strong,
      .premium-card code {{
        color: var(--txt-primary);
      }}

      .premium-card:hover {{
        border-color: var(--border-hover);
        background: linear-gradient(
          160deg,
          {tokens["card_hover_from"]},
          {tokens["card_hover_to"]}
        );
      }}

      .kpi-label {{
        color: var(--txt-secondary);
        font-size: 0.85rem;
      }}

      .kpi-value {{
        color: var(--txt-primary);
        font-size: 1.45rem;
        font-weight: 700;
        margin-top: 0.2rem;
      }}

      .kpi-delta {{
        font-size: 0.82rem;
        margin-top: 0.25rem;
      }}

      .page-title {{
        font-size: 1.7rem;
        font-weight: 700;
        letter-spacing: 0.2px;
        margin: 0 0 0.3rem 0;
      }}

      .page-subtitle {{
        font-size: 0.95rem;
        color: var(--txt-secondary);
        margin: 0 0 1rem 0;
      }}

      h1, h2, h3, h4, h5, h6 {{
        color: var(--txt-primary);
      }}

      [data-testid="stMarkdownContainer"] p,
      [data-testid="stMarkdownContainer"] li,
      [data-testid="stMarkdownContainer"] label {{
        color: var(--txt-primary);
      }}

      [data-testid="stCaptionContainer"] p {{
        color: var(--txt-secondary) !important;
      }}

      [data-testid="stMetric"] {{
        background: var(--bg-card);
        border: 1px solid var(--border);
        border-radius: var(--radius);
        padding: 0.6rem 0.8rem;
      }}

      [data-testid="stMetricLabel"] p {{
        color: var(--txt-secondary) !important;
      }}

      [data-testid="stMetricValue"] * {{
        color: var(--txt-primary) !important;
      }}

      [data-testid="stMetricDelta"] * {{
        color: var(--txt-secondary) !important;
      }}

      .status-badge {{
        display: inline-block;
        border-radius: 999px;
        padding: 0.2rem 0.65rem;
        font-size: 0.75rem;
        font-weight: 600;
        border: 1px solid transparent;
        margin-right: 0.3rem;
      }}

      .status-ok {{
        background: var(--badge-ok-bg);
        color: var(--badge-ok-txt);
        border-color: var(--badge-ok-border);
      }}

      .status-warning {{
        background: var(--badge-warning-bg);
        color: var(--badge-warning-txt);
        border-color: var(--badge-warning-border);
      }}

      .status-error {{
        background: var(--badge-error-bg);
        color: var(--badge-error-txt);
        border-color: var(--badge-error-border);
      }}

      .divider-soft {{
        height: 1px;
        border: 0;
        margin: 1rem 0;
        background: linear-gradient(90deg, transparent, var(--border), transparent);
      }}

      div[data-baseweb=\"select\"] > div {{
        background-color: var(--input-bg);
        border-color: var(--input-border);
      }}

      div[data-baseweb=\"select\"] * {{
        color: var(--txt-primary);
      }}

      div[data-baseweb=\"select\"] [aria-expanded=\"true\"] {{
        border-color: var(--accent);
      }}

      div[data-baseweb=\"popover\"],
      div[data-baseweb=\"popover\"] > div,
      div[data-baseweb=\"popover\"] > div > div,
      [data-testid=\"stSelectboxVirtualDropdown\"] {{
        background: var(--dropdown-bg) !important;
        border: 1px solid var(--dropdown-border) !important;
        border-radius: 0.6rem;
        box-shadow: var(--dropdown-shadow) !important;
      }}

      div[data-baseweb=\"popover\"] [role=\"listbox\"],
      [data-testid=\"stSelectboxVirtualDropdown\"] [role=\"listbox\"] {{
        background: transparent !important;
        color: var(--dropdown-text) !important;
      }}

      div[data-baseweb=\"popover\"] [role=\"option\"],
      [data-testid=\"stSelectboxVirtualDropdown\"] [role=\"option\"] {{
        color: var(--dropdown-text) !important;
        border-radius: 0.45rem;
      }}

      div[data-baseweb=\"popover\"] [role=\"option\"]:hover,
      [data-testid=\"stSelectboxVirtualDropdown\"] [role=\"option\"]:hover {{
        background: var(--dropdown-hover-bg) !important;
      }}

      div[data-baseweb=\"popover\"] [role=\"option\"][aria-selected=\"true\"],
      [data-testid=\"stSelectboxVirtualDropdown\"] [role=\"option\"][aria-selected=\"true\"] {{
        background: var(--dropdown-selected-bg) !important;
        color: var(--dropdown-selected-text) !important;
      }}

      div[data-baseweb=\"input\"] > div,
      div[data-baseweb=\"textarea\"] > div {{
        background-color: var(--input-bg);
        border-color: var(--input-border);
      }}

      div[data-baseweb=\"input\"] input,
      div[data-baseweb=\"textarea\"] textarea {{
        color: var(--txt-primary);
      }}

      div[data-baseweb=\"input\"] button,
      div[data-baseweb=\"textarea\"] button {{
        background: transparent;
        color: var(--txt-secondary);
        border-color: var(--input-border);
      }}

      button[data-testid=\"stNumberInputStepUp\"],
      button[data-testid=\"stNumberInputStepDown\"] {{
        background: var(--button-secondary-bg) !important;
        color: var(--button-secondary-txt) !important;
        border-color: var(--button-secondary-border) !important;
      }}

      button[data-testid=\"stNumberInputStepUp\"]:hover,
      button[data-testid=\"stNumberInputStepDown\"]:hover {{
        background: var(--button-secondary-bg-hover) !important;
      }}

      input::placeholder,
      textarea::placeholder {{
        color: var(--input-placeholder) !important;
      }}

      .stButton > button {{
        border-radius: 0.55rem;
        border: 1px solid var(--button-secondary-border);
        background: var(--button-secondary-bg);
        color: var(--button-secondary-txt);
        transition: all .12s ease-in-out;
      }}

      .stButton > button:hover {{
        background: var(--button-secondary-bg-hover);
        border-color: var(--border-hover);
      }}

      .stButton > button[kind=\"primary\"] {{
        background: var(--button-primary-bg);
        border-color: var(--button-primary-bg);
        color: var(--button-primary-txt);
      }}

      .stButton > button[kind=\"primary\"]:hover {{
        background: var(--button-primary-bg-hover);
        border-color: var(--button-primary-bg-hover);
      }}

      .stFormSubmitButton > button {{
        border-radius: 0.55rem;
        border: 1px solid var(--button-secondary-border);
        background: var(--button-secondary-bg);
        color: var(--button-secondary-txt);
      }}

      .stFormSubmitButton > button:hover {{
        background: var(--button-secondary-bg-hover);
      }}

      div[data-testid=\"stAlert\"] {{
        border-radius: 0.65rem;
      }}

      div[data-testid=\"stAlert\"] [data-testid=\"stNotificationContentInfo\"] {{
        background: var(--alert-info-bg);
        border: 1px solid var(--alert-info-border);
      }}

      div[data-testid=\"stAlert\"] [data-testid=\"stNotificationContentSuccess\"] {{
        background: var(--alert-success-bg);
        border: 1px solid var(--alert-success-border);
      }}

      div[data-testid=\"stAlert\"] [data-testid=\"stNotificationContentWarning\"] {{
        background: var(--alert-warning-bg);
        border: 1px solid var(--alert-warning-border);
      }}

      div[data-testid=\"stAlert\"] [data-testid=\"stNotificationContentError\"] {{
        background: var(--alert-error-bg);
        border: 1px solid var(--alert-error-border);
      }}

      div[data-testid=\"stAlert\"] p {{
        color: var(--txt-primary);
      }}

      div[data-testid=\"stDataFrame\"] {{
        border: 1px solid var(--border);
        border-radius: var(--radius);
        overflow: hidden;
        --gdg-bg-cell: var(--table-row-bg);
        --gdg-bg-cell-medium: var(--table-row-alt-bg);
        --gdg-bg-header: var(--table-header-bg);
        --gdg-bg-header-has-focus: var(--table-header-bg);
        --gdg-bg-search-result: var(--table-row-hover);
        --gdg-border-color: var(--border);
        --gdg-horizontal-border-color: var(--border);
        --gdg-header-horizontal-border-color: var(--border);
        --gdg-header-vertical-border-color: var(--border);
        --gdg-vertical-border-color: var(--border);
        --gdg-text-dark: var(--txt-primary);
        --gdg-text-medium: var(--txt-secondary);
        --gdg-text-light: var(--txt-secondary);
        --gdg-accent-color: var(--accent);
        --gdg-accent-fg: var(--txt-primary);
      }}

      div[data-testid=\"stDataFrame\"] [role=\"columnheader\"] {{
        background-color: var(--table-header-bg) !important;
        color: var(--txt-primary) !important;
      }}

      div[data-testid=\"stDataFrame\"] [role=\"gridcell\"] {{
        color: var(--txt-primary) !important;
      }}

      .theme-table-wrapper {{
        width: 100%;
        overflow: auto;
        border: 1px solid var(--border);
        border-radius: var(--radius);
        background: var(--table-row-bg);
        box-shadow: var(--shadow);
      }}

      .theme-table {{
        width: 100%;
        border-collapse: separate;
        border-spacing: 0;
        font-size: 0.86rem;
      }}

      .theme-table thead th {{
        position: sticky;
        top: 0;
        z-index: 1;
        background: var(--table-header-bg);
        color: var(--txt-primary);
        font-weight: 600;
        text-align: left;
        border-bottom: 1px solid var(--border);
        padding: 0.45rem 0.5rem;
      }}

      .theme-table tbody tr:nth-child(odd) {{
        background: var(--table-row-bg);
      }}

      .theme-table tbody tr:nth-child(even) {{
        background: var(--table-row-alt-bg);
      }}

      .theme-table tbody tr:hover {{
        background: var(--table-row-hover);
      }}

      .theme-table td {{
        color: var(--txt-primary);
        border-bottom: 1px solid var(--border);
        padding: 0.4rem 0.5rem;
        white-space: nowrap;
      }}

      .theme-table tbody tr:last-child td {{
        border-bottom: 0;
      }}

      [data-testid=\"stWidgetLabel\"] p,
      [data-testid=\"stWidgetLabel\"] span {{
        color: var(--txt-primary) !important;
      }}

      a {{
        color: var(--accent);
      }}
    </style>
    """


def apply_global_styles(theme_mode: ThemeMode = DEFAULT_THEME_MODE) -> None:
    st.markdown(build_global_css(theme_mode), unsafe_allow_html=True)
