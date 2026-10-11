import streamlit as st

from utils.style import COLORS, status_badge_html
from utils.sheets import load_activities
from utils.compute import enrich
from utils.activity_editor import activity_editor, wp_options, team_options

st.title("Team")
st.caption("Progress per person. Admins can edit or delete any activity; everyone else can edit or "
           "delete their own — work package, owner, dates, or mark it Done. Every change is written to "
           "the Edit Log with who did it and when. Status is never picked manually — it's computed "
           "automatically from the Done flag and the dates.")

df = enrich(load_activities())
if df.empty:
    st.stop()

people = sorted(df["Responsible (Name)"].dropna().astype(str).str.strip().unique())
people = [p for p in people if p]

wps = wp_options(df)
team_names = team_options(df)


for person in people:
    sub = df[df["Responsible (Name)"].astype(str).str.strip() == person]
    total = len(sub)
    done = int((sub["Bucket"] == "Completed").sum())
    overdue = int(sub["is_overdue"].sum())
    pct = round(100 * done / total, 1) if total else 0

    st.markdown(
        f"""
        <div class="nav-card" style="margin-bottom:10px;">
          <div style="display:flex;justify-content:space-between;align-items:baseline;">
            <div style="font-weight:800;color:{COLORS['navy']};font-size:15px;">{person}</div>
            <div style="font-weight:800;color:{COLORS['teal']};font-size:15px;">{pct}%</div>
          </div>
          <div class="nav-progress-track"><div class="nav-progress-fill" style="width:{pct}%;"></div></div>
          <div style="margin-top:8px;font-size:12px;color:{COLORS['ink']};">
            {total} activities · {done} completed · {overdue} delayed
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    with st.expander("✏️ Update activities"):
        for row_number, row in sub.iterrows():
            with st.container(border=True):
                c1, c2 = st.columns([2, 1])
                with c1:
                    st.markdown(f"**{row['Activity']}**")
                    st.caption(f"{row['Original WP']}")
                with c2:
                    st.markdown(status_badge_html(row["AutoStatus"]), unsafe_allow_html=True)
                    if row.get("is_overdue"):
                        st.error(f"{int(row['days_overdue'])} days overdue")
                    elif row.get("is_atrisk"):
                        st.warning("At risk")

                activity_editor(row, f"team_{row_number}", wps, team_names)
    st.divider()
