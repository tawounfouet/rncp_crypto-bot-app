"""Page Politique de confidentialité."""

from __future__ import annotations

from pathlib import Path

import streamlit as st

from components.headers import render_page_header
from layouts.page_shell import setup_page

PRIVACY_PATH = Path(__file__).resolve().parents[2] / "privacy.md"


def main() -> None:
    setup_page(
        title="Politique de confidentialité",
        icon=":material/privacy_tip:",
        page_key="privacy",
    )
    render_page_header(
        "Politique de confidentialité",
        "Traitement des données personnelles (RGPD) — texte placeholder.",
    )

    if not PRIVACY_PATH.exists():
        st.error("Le fichier privacy.md est introuvable. Contactez l'administrateur.")
        return
    try:
        privacy_text = PRIVACY_PATH.read_text(encoding="utf-8")
    except Exception:
        st.error("Impossible de charger le fichier privacy.md.")
        return
    st.markdown(privacy_text)


if __name__ == "__main__":
    main()
