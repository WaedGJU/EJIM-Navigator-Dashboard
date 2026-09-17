import streamlit as st

from utils.auth import login_gate
from utils.style import inject_base_style, sidebar_user_box
from utils.sheets import load_activities
from utils.compute import enrich

st.set_page_config(page_title="Team", page_icon="👥", layout="wide")
inject_base_style()
login_gate()
sidebar_user_box()

st.title("Team Completion")

df = enrich(load_activities())
if df.empty:
    st.stop()

people = sorted(df["Responsible (Name)"].dropna().astype(str).str.strip().unique())
people = [p for p in people if p]

for person in people:
    sub = df[df["Responsible (Name)"].astype(str).str.strip() == person]
    total = len(sub)
    done = int((sub["Bucket"] == "Completed").sum())
    overdue = int(sub["is_overdue"].sum())
    pct = round(100 * done / total, 1) if total else 0

    c1, c2, c3, c4 = st.columns([2, 1, 1, 1])
    c1.markdown(f"**{person}** — {total} activities")
    c1.progress(pct / 100)
    c2.metric("Completed", f"{pct}%")
    c3.metric("Delayed", overdue)
    c4.metric("In progress", int((sub["Bucket"] == "In Progress").sum()))
    with st.expander("View activities"):
        st.dataframe(
            sub[["No.", "Original WP", "Activity", "Status", "End Date"]],
            use_container_width=True, hide_index=True,
        )
    st.divider()
