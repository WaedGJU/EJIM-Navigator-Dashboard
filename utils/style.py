"""Shared visual identity (MASAR brand colors, taken from the real logo) +
shared sidebar header for every page."""

import base64
from pathlib import Path

import streamlit as st
from utils.auth import current_user, logout, is_admin

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
        section[data-testid="stSidebar"] {{
            background: linear-gradient(180deg, {COLORS['navy']} 0%, {COLORS['navy_dark']} 100%);
        }}
        section[data-testid="stSidebar"] * {{ color: #ffffff !important; }}

        /* Streamlit's built-in sidebar page-nav highlights the active/hovered
           page with a light blue by default — force it to brand orange so no
           blue survives anywhere in the UI. */
        section[data-testid="stSidebarNav"] a[aria-current="page"],
        section[data-testid="stSidebarNav"] a:hover,
        [data-testid="stSidebarNavLink"][aria-selected="true"],
        [data-testid="stSidebarNavLink"]:hover {{
            background-color: rgba(247, 168, 49, 0.22) !important;
            border-radius: 8px !important;
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

        /* The sidebar forces all its text white (for contrast on the navy
           background) — but that also whited-out the Log out button's own
           label on top of Streamlit's default light button background,
           making it unreadable. Give sidebar buttons their own dark,
           bordered look so the white label stays legible. */
        section[data-testid="stSidebar"] div.stButton > button {{
            background: rgba(255, 255, 255, 0.12) !important;
            border: 1px solid rgba(255, 255, 255, 0.45) !important;
            color: #ffffff !important;
        }}
        section[data-testid="stSidebar"] div.stButton > button:hover {{
            background: rgba(255, 255, 255, 0.24) !important;
            border-color: #ffffff !important;
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
    _apply_top_left_logo()


ASSETS_DIR = Path(__file__).resolve().parent.parent / "assets"
MASAR_LOGO_PATH = ASSETS_DIR / "masar_logo.png"
EJIM_LOGO_PATH = ASSETS_DIR / "ejim_logo.png"


@st.cache_data(show_spinner=False)
def _b64(path: Path) -> str:
    return base64.b64encode(path.read_bytes()).decode()


@st.cache_resource(show_spinner=False)
def _combined_logo_image():
    """Merges the MASAR + EJIM marks into a single image so the app has one
    logo, pinned to the top-left corner via st.logo() — never repeated as a
    big card inside the page content. Uses a solid white backing (matching
    the app's own background) rather than transparency, since the MASAR
    source file itself is a flat, opaque square with no alpha to crop."""
    from PIL import Image, ImageDraw

    masar = Image.open(MASAR_LOGO_PATH).convert("RGBA")
    if not EJIM_LOGO_PATH.exists():
        return masar

    ejim = Image.open(EJIM_LOGO_PATH).convert("RGBA")
    target_h = 80

    def _resize(img, h):
        w = max(1, int(img.width * (h / img.height)))
        return img.resize((w, h), Image.LANCZOS)

    masar_r = _resize(masar, target_h)
    ejim_r = _resize(ejim, int(target_h * 0.68))
    gap = 20
    canvas_w = masar_r.width + gap + ejim_r.width
    canvas = Image.new("RGBA", (canvas_w, target_h), (255, 255, 255, 255))
    canvas.paste(masar_r, (0, 0), masar_r)
    draw = ImageDraw.Draw(canvas)
    divider_x = masar_r.width + gap // 2
    draw.line([(divider_x, 6), (divider_x, target_h - 6)], fill=(227, 230, 234, 255), width=2)
    canvas.paste(ejim_r, (masar_r.width + gap, (target_h - ejim_r.height) // 2), ejim_r)
    return canvas


def _apply_top_left_logo():
    """Pins the MASAR/EJIM logo to the top-left corner of the app (Streamlit's
    standard logo slot), including the login screen, so it always shows in the
    same spot whether the sidebar is open, collapsed, or not yet reachable
    (pre-login)."""
    try:
        st.logo(_combined_logo_image(), icon_image=str(MASAR_LOGO_PATH), size="large")
    except Exception:
        pass  # older Streamlit without st.logo() — fail silently, rest of UI still works


def logo_html(max_width: int = 150, with_ejim: bool = True) -> str:
    """Renders the MASAR logo (and, alongside it, the smaller EJIM program
    logo) inside one white rounded card. Kept as a single self-contained
    HTML string because Streamlit can't nest a separate st.image() call
    inside a div opened by st.markdown(). Used only where a bigger, one-off
    logo makes sense (e.g. a printable report header) — the app's own
    top-left logo comes from st.logo() in inject_base_style()."""
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


def sidebar_user_box():
    """Renders once, in the sidebar only. The brand logo itself is pinned to
    the top-left corner by st.logo() (called from inject_base_style()) — this
    just adds the user/session info below Streamlit's own page navigation."""
    user = current_user()
    with st.sidebar:
        st.caption("CeLAPI · German Jordanian University")
        st.divider()
        if user:
            role_label = "Admin" if is_admin() else "Team member"
            st.markdown(f"**{user['name']}**  \n{role_label}")
            if st.button("Log out", use_container_width=True):
                logout()
        st.divider()
        st.caption("Data source: Google Sheets — refreshes every 20s")
