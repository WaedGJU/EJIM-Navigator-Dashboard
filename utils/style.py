"""Shared visual identity (GJU brand colors) + shared sidebar for every page."""

import base64
from pathlib import Path

import streamlit as st
from utils.auth import current_user, logout, is_admin

COLORS = {
    "blue": "#0088C9",
    "blue_dark": "#0a6da3",
    "orange": "#F6A800",
    "ink": "#4D4D4D",
    "ink_strong": "#26282b",
    "good": "#0ca30c",
    "warning": "#e8a300",
    "critical": "#d03b3b",
    "border": "#e3e6ea",
    "page_bg": "#f6f8fa",
}


def inject_base_style():
    st.markdown(
        f"""
        <style>
        html, body, [class*="css"] {{
            font-family: 'Segoe UI', Tahoma, Arial, sans-serif;
        }}
        .stApp {{ background: {COLORS['page_bg']}; }}
        [data-testid="stMetricValue"] {{ font-weight: 800; }}
        section[data-testid="stSidebar"] {{
            background: linear-gradient(180deg, {COLORS['blue']} 0%, {COLORS['blue_dark']} 100%);
        }}
        section[data-testid="stSidebar"] * {{ color: #ffffff !important; }}
        div.stButton > button {{
            border-radius: 999px;
            font-weight: 700;
        }}
        </style>
        """,
        unsafe_allow_html=True,
    )


LOGO_PATH = Path(__file__).resolve().parent.parent / "assets" / "masar_logo.png"


@st.cache_data(show_spinner=False)
def _logo_b64() -> str:
    return base64.b64encode(LOGO_PATH.read_bytes()).decode()


def logo_html(max_width: int = 150) -> str:
    return (
        f'<div style="background:#fff;border-radius:12px;padding:10px 16px;'
        f'display:inline-block;">'
        f'<img src="data:image/png;base64,{_logo_b64()}" style="max-width:{max_width}px;width:100%;display:block;">'
        f"</div>"
    )


def sidebar_user_box():
    user = current_user()
    with st.sidebar:
        st.markdown(logo_html(180), unsafe_allow_html=True)
        st.caption("CeLAPI · German Jordanian University")
        st.divider()
        if user:
            role_label = "Admin" if is_admin() else "Team member"
            st.markdown(f"**{user['name']}**  \n{role_label}")
            if st.button("Log out", use_container_width=True):
                logout()
        st.divider()
        st.caption("Data source: Google Sheets — refreshes every 20s")
