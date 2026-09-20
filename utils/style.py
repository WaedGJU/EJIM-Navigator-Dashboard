"""Shared visual identity (MASAR brand colors, taken from the real logo) +
the shared top user bar for every page. Navigation itself lives in a
horizontal top tab bar (st.navigation(..., position="top"), wired up in
streamlit_app.py) — there is no left sidebar anywhere in this app."""

import base64
from pathlib import Path

import streamlit as st
from utils.auth import current_user, logout, is_admin
from utils.constants import PROJECT_NAME

BRAND_BAR_HEIGHT = 50  # px — kept as one constant so the CSS offsets below always agree

# Brand palette — matches the MASAR/EJIM logo exactly:
#   navy  #355265   orange  #f7a831   teal  #2b8782
# No blue accent color is used anywhere in the app; the only non-brand color
# kept is a red for "delayed / critical" items, since that's a universal
# warning color and not a stray blue.
COLORS = {
    "navy": "#355265",
    "navy_dark": "#22394A",
    "orange": "#F7A831",
    "teal": "#2B8782",
    "ink": "#4D4D4D",
    "ink_strong": "#26282B",
    "good": "#2B8782",       # Completed
    "progress": "#355265",   # In Progress
    "warning": "#F7A831",    # Needs confirmation / At risk
    "critical": "#D64545",   # Delayed / overdue
    "neutral": "#c7cbd1",    # Not started
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
        [data-testid="stMetricValue"] {{ font-weight: 800; color: {COLORS['navy']}; }}

        /* Navigation now lives in a horizontal top tab bar (st.navigation(...,
           position="top")) instead of the old left sidebar, and nothing in
           this app calls st.sidebar anymore. A couple of Streamlit releases
           had a transient bug where position="top" still also drew the old
           sidebar nav — hide it outright so there is never a second, stray
           nav even if that resurfaces. */
        section[data-testid="stSidebar"], section[data-testid="stSidebarNav"] {{
            display: none !important;
        }}

        /* A slim fixed bar (logo + project name) pinned above everything
           else — Streamlit's own header is otherwise always the topmost
           element on the page, so this is the only way to get the brand
           above the tabs instead of inside/below them. */
        #brand-bar {{
            position: fixed;
            top: 0; left: 0; right: 0;
            height: {BRAND_BAR_HEIGHT}px;
            z-index: 999999;
            background: {COLORS['navy_dark']};
            display: flex;
            align-items: center;
            gap: 12px;
            padding: 0 22px;
            box-shadow: 0 1px 4px rgba(0, 0, 0, 0.25);
        }}
        #brand-bar img {{ height: 28px; display: block; }}
        #brand-bar span {{
            color: #ffffff;
            font-weight: 800;
            font-size: 15.5px;
            letter-spacing: .02em;
        }}

        /* Streamlit's own top header (which hosts the page tabs) is pushed
           down to make room for the brand bar above it, and the page's own
           content gets that same extra space added back on top of whatever
           top offset Streamlit already reserves for its header. */
        header[data-testid="stHeader"], .stAppHeader {{
            top: {BRAND_BAR_HEIGHT}px !important;
            background: {COLORS['navy']} !important;
        }}
        div[data-testid="stAppViewContainer"] {{
            margin-top: {BRAND_BAR_HEIGHT}px !important;
        }}

        /* The page tabs themselves — styled as raised, rounded boxes instead
           of a plain link row, with the active tab picked out in brand
           orange. Streamlit doesn't publish a stable class name for these
           yet, so this targets every plausible link/tab element inside the
           header rather than one exact selector. */
        .stAppHeader a,
        .stAppHeader [data-testid="stNavigationLink"],
        .stAppHeader [role="tab"] {{
            background: rgba(255, 255, 255, 0.10) !important;
            border: 1px solid rgba(255, 255, 255, 0.22) !important;
            border-radius: 10px !important;
            margin: 0 4px !important;
            padding: 6px 16px !important;
            color: #ffffff !important;
            font-weight: 700 !important;
            box-shadow: 0 1px 3px rgba(0, 0, 0, 0.15);
        }}
        .stAppHeader a:hover,
        .stAppHeader [role="tab"]:hover {{
            background: rgba(255, 255, 255, 0.2) !important;
        }}
        .stAppHeader a[aria-current="page"],
        .stAppHeader [aria-selected="true"] {{
            background: {COLORS['orange']} !important;
            border-color: {COLORS['orange']} !important;
            color: {COLORS['navy']} !important;
        }}

        /* Links and other native widget accents default to Streamlit's theme
           blue when unset — pin them to brand teal/orange instead. */
        a, a:visited {{ color: {COLORS['teal']}; }}
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
    _render_top_brand_bar()


ASSETS_DIR = Path(__file__).resolve().parent.parent / "assets"
MASAR_LOGO_PATH = ASSETS_DIR / "masar_logo.png"
EJIM_LOGO_PATH = ASSETS_DIR / "ejim_logo.png"


@st.cache_data(show_spinner=False)
def _b64(path: Path) -> str:
    return base64.b64encode(path.read_bytes()).decode()


def _render_top_brand_bar():
    """Renders the fixed logo + project-name strip pinned above Streamlit's
    own header/tabs (see the '#brand-bar' CSS above) — on every page,
    including the login screen, so branding always shows in the same spot."""
    try:
        st.markdown(
            f"""
            <div id="brand-bar">
                <img src="data:image/png;base64,{_b64(MASAR_LOGO_PATH)}" alt="MASAR logo">
                <span>{PROJECT_NAME}</span>
            </div>
            """,
            unsafe_allow_html=True,
        )
    except Exception:
        pass  # missing logo file etc. — fail silently, rest of UI still works


def logo_html(max_width: int = 150, with_ejim: bool = True) -> str:
    """Renders the MASAR logo (and, alongside it, the smaller EJIM program
    logo) inside one white rounded card. Kept as a single self-contained
    HTML string because Streamlit can't nest a separate st.image() call
    inside a div opened by st.markdown(). Used only where a bigger, one-off
    logo makes sense (e.g. a printable report header) — the app's own
    branding comes from the fixed brand bar in inject_base_style()."""
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


STATUS_BADGE_COLORS = {
    "Completed": COLORS["good"],
    "Delayed": COLORS["critical"],
    "Not started": COLORS["neutral"],
    "In Progress": COLORS["navy"],
}


def status_badge_html(label: str) -> str:
    """A small colored pill for an auto-computed status (compute.py's
    'AutoStatus' column) — used wherever status is shown but never picked
    from a dropdown."""
    color = STATUS_BADGE_COLORS.get(label, COLORS["neutral"])
    return f'<span class="nav-pill" style="background:{color}22;color:{color};">{label}</span>'


def top_user_bar():
    """Renders once, from the router (streamlit_app.py), right under the top
    navigation tabs — replaces the old left sidebar box entirely. Shows who's
    logged in, their role, the data-source note, and Log out, in one slim
    horizontal strip at the top of the page content."""
    user = current_user()
    if not user:
        return
    role_label = "Admin" if is_admin() else "Team member"
    ink = COLORS["ink"]
    border = COLORS["border"]
    info_col, logout_col = st.columns([6, 1])
    with info_col:
        st.markdown(
            f"<div style='font-size:12.5px;color:{ink};padding-top:8px;'>"
            f"👤 <b>{user['name']}</b> · {role_label} &nbsp;·&nbsp; "
            "Data source: Google Sheets — refreshes every 20s</div>",
            unsafe_allow_html=True,
        )
    with logout_col:
        if st.button("Log out", use_container_width=True, key="top_user_bar_logout"):
            logout()
    st.markdown(
        f"<hr style='margin:8px 0 18px 0;border:none;border-top:1px solid {border};'>",
        unsafe_allow_html=True,
    )
