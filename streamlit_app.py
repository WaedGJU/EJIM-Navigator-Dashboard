import datetime

import streamlit as st
import plotly.express as px
import pandas as pd

from utils.auth import login_gate
from utils.style import inject_base_style, sidebar_user_box, COLORS, MASAR_LOGO_PATH
from utils.sheets import load_activities
from utils.compute import enrich, kpis
from utils.constants import PROJECT_NAME, PROJECT_END_DATE, INTERNAL_DEADLINE

st.set_page_config(page_title="Navigator (MASAR) — Overview", page_icon="🧭", layout="wide")
inject_base_style()
login_gate()  # stops here if nobody is logged in
sidebar_user_box()  # the one fixed logo/header for the whole app — never repeated on the page itself

# ---------- Hero: big logo + big project name ----------
hero_logo, hero_text = st.columns([0.5, 2])
with hero_logo:
    st.image(str(MASAR_LOGO_PATH), use_container_width=True)
with hero_text:
    st.markdown(
        f"""
        <div style="height:100%;display:flex;flex-direction:column;justify-content:center;">
          <div style="font-size:42px;font-weight:800;color:{COLORS['navy']};line-height:1.05;">{PROJECT_NAME}</div>
          <div style="font-size:15px;color:{COLORS['ink']};margin-top:6px;">         
           Designed by Eng. Waed Alswaeer — waed.alswaer@gju.edu.jo — +962795948223
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

# ---------- Project end date + countdown ----------
days_left = (PROJECT_END_DATE - datetime.date.today()).days
if days_left >= 0:
    counter_value, counter_label = days_left, "days left"
    counter_color = COLORS["critical"] if days_left <= 14 else (COLORS["warning"] if days_left <= 30 else COLORS["teal"])
else:
    counter_value, counter_label = abs(days_left), "days past the project end date"
    counter_color = COLORS["critical"]

st.markdown(
    f"""
    <div class="nav-card" style="margin-top:16px;display:flex;justify-content:space-between;
                                  align-items:center;flex-wrap:wrap;gap:16px;">
      <div>
        <div style="font-size:12px;color:{COLORS['ink']};font-weight:700;text-transform:uppercase;letter-spacing:.04em;">
          Project end date
        </div>
        <div style="font-size:22px;font-weight:800;color:{COLORS['navy']};margin-top:2px;">
          {PROJECT_END_DATE.strftime('%d %B %Y')}
        </div>
        <div style="font-size:12px;color:{COLORS['ink']};margin-top:2px;">
          Internal deadline: {INTERNAL_DEADLINE.strftime('%d %B %Y')} (2-week buffer)
        </div>
      </div>
      <div style="text-align:center;min-width:120px;">
        <div style="font-size:36px;font-weight:800;color:{counter_color};line-height:1;">{counter_value}</div>
        <div style="font-size:12px;color:{COLORS['ink']};font-weight:700;">{counter_label}</div>
      </div>
    </div>
    """,
    unsafe_allow_html=True,
)

st.divider()
st.subheader("Project Overview")
st.caption("Status dashboard — live data from Google Sheets")

with st.spinner("Loading data..."):
    df = enrich(load_activities())

if df.empty:
    st.warning("The activity registry is empty or unreachable. Check the sheet link and connection permissions.")
    st.stop()

k = kpis(df)
STATUS_COLORS = {
    "Completed": COLORS["good"],
    "In Progress": COLORS["progress"],
    "Needs Confirmation": COLORS["warning"],
    "Not Started": COLORS["neutral"],
}

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

# ---------- Work-package cards with progress bars ----------
st.subheader("Work packages")
wp_list = sorted(df["Original WP"].dropna().unique())
cols = st.columns(3)
for i, wp in enumerate(wp_list):
    sub = df[df["Original WP"] == wp]
    total = len(sub)
    done = int((sub["Bucket"] == "Completed").sum())
    pct = round(100 * done / total, 1) if total else 0
    delayed = int(sub["is_overdue"].sum())
    at_risk = int(sub["is_atrisk"].sum())
    with cols[i % 3]:
        badges = ""
        if delayed:
            badges += f'<span class="nav-pill" style="background:#fbe7e7;color:{COLORS["critical"]};margin-right:6px;">{delayed} delayed</span>'
        if at_risk:
            badges += f'<span class="nav-pill" style="background:#fdeed2;color:{COLORS["warning"]};">{at_risk} at risk</span>'
        st.markdown(
            f"""
            <div class="nav-card" style="margin-bottom:14px;">
              <div style="display:flex;justify-content:space-between;align-items:baseline;">
                <div style="font-weight:800;color:{COLORS['navy']};font-size:15px;">{wp}</div>
                <div style="font-weight:800;color:{COLORS['teal']};font-size:15px;">{pct}%</div>
              </div>
              <div class="nav-progress-track"><div class="nav-progress-fill" style="width:{pct}%;"></div></div>
              <div style="margin-top:8px;font-size:12px;color:{COLORS['ink']};">{done}/{total} completed</div>
              <div style="margin-top:6px;">{badges or '&nbsp;'}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

st.divider()

col_left, col_right = st.columns([1.4, 1])

with col_left:
    st.subheader("Progress by work package")
    wp_summary = (
        df.groupby("Original WP")["Bucket"]
        .value_counts(normalize=True)
        .mul(100)
        .round(1)
        .rename("pct")
        .reset_index()
    )
    fig = px.bar(
        wp_summary,
        x="pct",
        y="Original WP",
        color="Bucket",
        orientation="h",
        text=wp_summary["pct"].apply(lambda v: f"{v:.0f}%" if v >= 6 else ""),
        color_discrete_map=STATUS_COLORS,
        labels={"pct": "% of activities", "Original WP": ""},
    )
    fig.update_traces(textposition="inside", insidetextanchor="middle")
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
        color_discrete_map=STATUS_COLORS,
    )
    fig2.update_traces(textposition="inside", textinfo="percent+label")
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
              text=team["Completion %"].apply(lambda v: f"{v:.0f}%"),
              color="Completion %",
              color_continuous_scale=[COLORS["critical"], COLORS["warning"], COLORS["good"]])
fig3.update_traces(textposition="outside")
fig3.update_layout(height=380, coloraxis_showscale=False, margin=dict(l=0, r=0, t=10, b=0),
                    yaxis_title="", xaxis_title="")
st.plotly_chart(fig3, use_container_width=True)

st.divider()

# ---------- This week / delayed / at-risk ----------
today = pd.Timestamp(datetime.date.today())
week_ahead = today + pd.Timedelta(days=7)
this_week = df[(df["Bucket"] != "Completed") & (df["End_dt"] >= today) & (df["End_dt"] <= week_ahead)]
delayed_df = df[df["is_overdue"]].sort_values("days_overdue", ascending=False)
at_risk_df = df[df["is_atrisk"]]

t1, t2, t3 = st.tabs([
    f"📅 Due this week ({len(this_week)})",
    f"🔴 Delayed ({len(delayed_df)})",
    f"🟠 At risk ({len(at_risk_df)})",
])


def _mini_table(sub: pd.DataFrame, extra_col: str | None = None):
    if sub.empty:
        st.success("Nothing here 🎉")
        return
    cols = ["No.", "Original WP", "Activity", "Responsible (Name)", "Status", "End Date"]
    if extra_col and extra_col in sub.columns:
        cols.append(extra_col)
    st.dataframe(sub[cols], use_container_width=True, hide_index=True)


with t1:
    st.caption(f"Activities due between today ({today.date()}) and {week_ahead.date()}, not yet completed.")
    _mini_table(this_week)
with t2:
    _mini_table(delayed_df, "days_overdue")
with t3:
    _mini_table(at_risk_df)

st.info("💡 Use the sidebar to jump to Work Packages, Team, Critical Follow-up, External Partners, Full Registry, or Meeting Prep.")
