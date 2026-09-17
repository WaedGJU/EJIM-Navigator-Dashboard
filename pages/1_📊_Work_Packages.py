import streamlit as st
import plotly.express as px

from utils.auth import login_gate
from utils.style import inject_base_style, sidebar_user_box, COLORS
from utils.sheets import load_activities
from utils.compute import enrich

st.set_page_config(page_title="Work Packages", page_icon="📊", layout="wide")
inject_base_style()
login_gate()
sidebar_user_box()

st.title("Work Packages (WP1–WP9)")

df = enrich(load_activities())
if df.empty:
    st.stop()

wp_list = sorted(df["Original WP"].dropna().unique())
picked = st.multiselect("Filter by work package", wp_list, default=wp_list)
view = df[df["Original WP"].isin(picked)]

for wp in picked:
    sub = view[view["Original WP"] == wp]
    total = len(sub)
    done = int((sub["Bucket"] == "Completed").sum())
    pct = round(100 * done / total, 1) if total else 0

    with st.expander(f"{wp} — {pct}% ({done}/{total})", expanded=False):
        fig = px.pie(sub, names="Bucket", hole=0.55,
                     color="Bucket",
                     color_discrete_map={
                         "Completed": COLORS["good"], "In Progress": COLORS["blue"],
                         "Needs Confirmation": COLORS["warning"], "Not Started": "#c7cbd1",
                     })
        fig.update_layout(height=260, margin=dict(l=0, r=0, t=0, b=0))
        c1, c2 = st.columns([1, 2])
        with c1:
            st.plotly_chart(fig, use_container_width=True)
        with c2:
            st.dataframe(
                sub[["No.", "Activity", "Responsible (Name)", "Status", "End Date"]],
                use_container_width=True, hide_index=True, height=260,
            )
