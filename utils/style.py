"""Shared visual identity (MASAR brand colors, sampled from the real logo) +
shared sidebar header for every page."""

import base64
from pathlib import Path

import streamlit as st
from utils.auth import current_user, logout, is_admin

# Colors sampled directly from assets/masar_logo.png (navy + orange + teal),
# so the app matches the actual project branding rather than a generic palette.
COLORS = {
    "navy": "#2C4A5C",
    "navy_dark": "#1C303D",
    "orange": "#F5A623",
    "teal": "#0A8F80",
    "ink": "#4D4D4D",
    "ink_strong": "#26282b",
    "good": "#0A8F80",       # Completed
    "progress": "#2C4A5C",   # In Progress
    "warning": "#F5A623",    # Needs confirmation / At risk
    "critical": "#D64545",   # Delayed / overdue
    "neutral": "#c7cbd1",    # Not started
    "border": "#e3e6ea",
    "page_bg": "#f6f8fa",
    # kept for backward compatibility with earlier chart code
    "blue": "#2C4A5C",
    "blue_dark": "#1C303D",
}


def inject_base_style():
    st.markdown(
        f"""
        <style>
        html, body, [class*="css"] {{
            font-family: 'Segoe UI', Tahoma, Arial, sans-serif;
        }}
        .stApp {{ background: {COLORS['page_bg']}; }}
        [data-testid="stMetricValue"] {{ font-weight: 800; color: {COLORS['navy']}; }}
        section[data-testid="stSidebar"] {{
            background: linear-gradient(180deg, {COLORS['navy']} 0%, {COLORS['navy_dark']} 100%);
        }}
        section[data-testid="stSidebar"] * {{ color: #ffffff !important; }}
        div.stButton > button {{
            border-radius: 999px;
            font-weight: 700;
        }}
        div.stButton > button[kind="primary"], div.stButton > button:not([kind]) {{
            background: {COLORS['navy']};
            border-color: {COLORS['navy']};
        }}
        .nav-card {{
            background: #ffffff;
            border: 1px solid {COLORS['border']};
            border-radius: 14px;
            padding: 16px 18px;
            box-shadow: 0 1px 2px rgba(20, 30, 40, 0.04);
        }}
        .nav-progress-track {{
            width: 100%;
            height: 9px;
            border-radius: 999px;
            background: #e9edf1;
            overflow: hidden;
            margin-top: 8px;
        }}
        .nav-progress-fill {{
            height: 100%;
            border-radius: 999px;
            background: linear-gradient(90deg, {COLORS['teal']}, {COLORS['navy']});
        }}
        .nav-pill {{
            display: inline-block;
            border-radius: 999px;
            padding: 2px 10px;
            font-size: 11.5px;
            font-weight: 700;
        }}
        </style>
        """,
        unsafe_allow_html=True,
    )


ASSETS_DIR = Path(__file__).resolve().parent.parent / "assets"
MASAR_LOGO_PATH = ASSETS_DIR / "masar_logo.png"
EJIM_LOGO_PATH = ASSETS_DIR / "ejim_logo.png"


@st.cache_data(show_spinner=False)
def _b64(path: Path) -> str:
    return base64.b64encode(path.read_bytes()).decode()


def logo_html(max_width: int = 150, with_ejim: bool = True) -> str:
    """Renders the MASAR logo (and, alongside it, the smaller EJIM program
    logo) inside one white rounded card. Kept as a single self-contained
    HTML string because Streamlit can't nest a separate st.image() call
    inside a div opened by st.markdown()."""
    masar_img = (
        f'<img src="data:image/png;base64,{_b64(MASAR_LOGO_PATH)}" '
        f'style="max-width:{max_width}px;width:100%;display:block;">'
    )
    if not with_ejim or not EJIM_LOGO_PATH.exists():
        inner = masar_img
    else:
        ejim_width = int(max_width * 0.62)
        inner = (
            '<div style="display:flex;align-items:center;gap:14px;">'
            f'{masar_img}'
            f'<div style="width:1px;align-self:stretch;background:{COLORS["border"]};"></div>'
            f'<img src="data:image/png;base64,{_b64(EJIM_LOGO_PATH)}" '
            f'style="max-width:{ejim_width}px;width:100%;display:block;">'
            '</div>'
        )
    return (
        '<div style="background:#fff;border-radius:12px;padding:10px 16px;'
        'display:inline-block;">' + inner + "</div>"
    )


def sidebar_user_box():
    """Renders once, in the sidebar only — this is the single fixed
    'header' logo shown throughout the app after login. Pages never render
    the logo a second time in the main content area."""
    user = current_user()
    with st.sidebar:
        st.markdown(logo_html(170), unsafe_allow_html=True)
        st.caption("CeLAPI · German Jordanian University")
        st.divider()
        if user:
            role_label = "Admin" if is_admin() else "Team member"
            st.markdown(f"**{user['name']}**  \n{role_label}")
            if st.button("Log out", use_container_width=True):
                logout()
        st.divider()
        st.caption("Data source: Google Sheets — refreshes every 20s")
