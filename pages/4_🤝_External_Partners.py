import streamlit as st
import plotly.express as px

from utils.style import COLORS
from utils.sheets import load_activities
from utils.compute import enrich

st.title("MODEE / GIZ / MoL")
st.caption("Every activity naming an external partner as an owner, co-owner, or dependency.")

df = enrich(load_activities())
if df.empty:
    st.stop()

external = df[df["is_external"]].copy()

partner_filter = st.radio("Filter by partner", ["All", "MODEE", "GIZ", "MoL"], horizontal=True)
if partner_filter != "All":
    external = external[external["partners"].apply(lambda p: partner_filter in p)]

counts = {p: int(df["partners"].apply(lambda x: p in x).sum()) for p in ["MODEE", "GIZ", "MoL"]}
c1, c2, c3 = st.columns(3)
c1.metric("MODEE", counts["MODEE"])
c2.metric("GIZ", counts["GIZ"])
c3.metric("MoL", counts["MoL"])

wp_pct = (
    external.groupby("Original WP")["Bucket"]
    .value_counts(normalize=True)
    .mul(100)
    .round(1)
    .rename("pct")
    .reset_index()
)
fig = px.bar(
    wp_pct, x="Original WP", y="pct", color="Bucket",
    text=wp_pct["pct"].apply(lambda v: f"{v:.0f}%" if v >= 6 else ""),
    color_discrete_map={
        "Completed": COLORS["good"], "In Progress": COLORS["navy"],
        "Needs Confirmation": COLORS["warning"], "Not Started": COLORS["neutral"],
    },
    labels={"pct": "% of activities", "Original WP": ""},
)
fig.update_traces(textposition="inside", insidetextanchor="middle")
fig.update_layout(barmode="stack", height=320, legend_title="")
st.plotly_chart(fig, use_container_width=True)

st.dataframe(
    external[["No.", "Original WP", "Activity", "Responsible (Name)", "Status", "End Date"]],
    use_container_width=True, hide_index=True,
)
