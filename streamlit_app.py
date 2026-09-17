import streamlit as st
import plotly.express as px
import pandas as pd

from utils.auth import login_gate
from utils.style import inject_base_style, sidebar_user_box, COLORS
from utils.sheets import load_activities
from utils.compute import enrich, kpis

st.set_page_config(page_title="Navigator (MASAR) — Overview", page_icon="🧭", layout="wide")
inject_base_style()
login_gate()  # stops here if nobody is logged in
sidebar_user_box()

st.title("Project Overview")
st.caption("Labour Mobility Navigator (MASAR) status dashboard — live data from Google Sheets")

with st.spinner("Loading data..."):
    df = enrich(load_activities())

if df.empty:
    st.warning("The activity registry is empty or unreachable. Check the sheet link and connection permissions.")
    st.stop()

k = kpis(df)

# ---------- KPI cards ----------
c1, c2, c3, c4, c5, c6, c7, c8 = st.columns(8)
c1.metric("Total activities", k["total"])
c2.metric("Completed", k["completed"], f"{k['completed_pct']}%")
c3.metric("In progress", k["in_progress"])
c4.metric("Not started", k["not_started"])
c5.metric("Needs confirmation", k["needs_confirmation"])
c6.metric("Delayed", k["overdue"])
c7.metric("At risk", k["at_risk"])
c8.metric("No owner", k["unassigned"])

st.divider()

col_left, col_right = st.columns([1.4, 1])

with col_left:
    st.subheader("Progress by work package")
    wp_summary = (
        df.groupby("Original WP")["Bucket"]
        .value_counts(normalize=True)
        .mul(100)
        .rename("pct")
        .reset_index()
    )
    fig = px.bar(
        wp_summary,
        x="pct",
        y="Original WP",
        color="Bucket",
        orientation="h",
        color_discrete_map={
            "Completed": COLORS["good"],
            "In Progress": COLORS["blue"],
            "Needs Confirmation": COLORS["warning"],
            "Not Started": "#c7cbd1",
        },
        labels={"pct": "% of activities", "Original WP": ""},
    )
    fig.update_layout(barmode="stack", legend_title="", height=420, margin=dict(l=0, r=0, t=10, b=0))
    st.plotly_chart(fig, use_container_width=True)

with col_right:
    st.subheader("Status distribution")
    status_counts = df["Bucket"].value_counts().reset_index()
    status_counts.columns = ["Status", "Count"]
    fig2 = px.pie(
        status_counts,
        names="Status",
        values="Count",
        hole=0.6,
        color="Status",
        color_discrete_map={
            "Completed": COLORS["good"],
            "In Progress": COLORS["blue"],
            "Needs Confirmation": COLORS["warning"],
            "Not Started": "#c7cbd1",
        },
    )
    fig2.update_layout(height=420, showlegend=True, legend=dict(orientation="h", y=-0.15))
    st.plotly_chart(fig2, use_container_width=True)

st.subheader("Team completion")
team = (
    df[df["Responsible (Name)"].astype(str).str.strip() != ""]
    .groupby("Responsible (Name)")
    .apply(lambda g: pd.Series({
        "Activities": len(g),
        "Completion %": round(100 * (g["Bucket"] == "Completed").sum() / len(g), 1),
    }))
    .reset_index()
    .sort_values("Completion %", ascending=False)
)
fig3 = px.bar(team, x="Completion %", y="Responsible (Name)", orientation="h",
              text="Activities", color="Completion %",
              color_continuous_scale=[COLORS["critical"], COLORS["warning"], COLORS["good"]])
fig3.update_layout(height=380, coloraxis_showscale=False, margin=dict(l=0, r=0, t=10, b=0),
                    yaxis_title="", xaxis_title="")
st.plotly_chart(fig3, use_container_width=True)

st.info("💡 Use the sidebar to jump to Work Packages, Team, Critical Follow-up, External Partners, Full Registry, or Meeting Prep.")
