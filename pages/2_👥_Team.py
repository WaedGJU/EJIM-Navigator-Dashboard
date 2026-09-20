import pandas as pd
import streamlit as st

from utils.auth import current_user
from utils.style import COLORS, status_badge_html
from utils.sheets import load_activities, load_users, update_activity_cell, ConflictError
from utils.compute import enrich

st.title("Team")
st.caption("Progress per person. Editing is open to everyone here — anyone can update any activity's "
           "start/end dates, owner, or mark it Done. Every change is written to the Edit Log with who "
           "did it and when, so there's no need for a separate permission check. Status is never picked "
           "manually — it's computed automatically from the Done flag and the dates.")

user = current_user()
df = enrich(load_activities())
if df.empty:
    st.stop()

people = sorted(df["Responsible (Name)"].dropna().astype(str).str.strip().unique())
people = [p for p in people if p]

# The owner dropdown lists every active team member from the Users tab (not
# just people who already own an activity), so reassigning to someone new
# works too — falls back to whoever already appears in the registry if the
# Users tab can't be reached.
users_df = load_users()
if not users_df.empty and "Name" in users_df.columns:
    team_names = sorted(set(users_df["Name"].dropna().astype(str).str.strip()) | set(people))
else:
    team_names = people


def _parse_date(value):
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return pd.to_datetime(text).date()
    except Exception:
        return None


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

                k = f"team_{row_number}"
                current_owner = str(row.get("Responsible (Name)", "")).strip()
                owner_options = team_names if current_owner in team_names else [current_owner] + team_names

                owner_col, done_col = st.columns([2, 1])
                new_owner = owner_col.selectbox(
                    "Owner", owner_options,
                    index=owner_options.index(current_owner) if current_owner in owner_options else 0,
                    key=f"owner_{k}",
                )
                current_team_update = str(row.get("Team Update", "") or "").strip()
                done_checked = done_col.checkbox(
                    "Done ✅", value=current_team_update.lower() == "done", key=f"done_{k}",
                )

                start_col, end_col = st.columns(2)
                current_start = str(row.get("Start Date", "") or "").strip()
                current_end = str(row.get("End Date", "") or "").strip()
                new_start = start_col.date_input("Start date", value=_parse_date(current_start), key=f"start_{k}")
                new_end = end_col.date_input("End date", value=_parse_date(current_end), key=f"end_{k}")

                if st.button("💾 Save", key=f"save_{k}"):
                    try:
                        new_team_update = "Done" if done_checked else ""
                        if new_team_update != current_team_update and "Team Update" in df.columns:
                            update_activity_cell(row_number, "Team Update", new_team_update, user)
                        if new_owner != current_owner:
                            update_activity_cell(row_number, "Responsible (Name)", new_owner, user)
                        if new_start and new_start.isoformat() != current_start:
                            update_activity_cell(row_number, "Start Date", new_start.isoformat(), user)
                        if new_end and new_end.isoformat() != current_end:
                            update_activity_cell(row_number, "End Date", new_end.isoformat(), user)
                        st.success("Saved ✅")
                        st.rerun()
                    except ConflictError as e:
                        st.error(str(e))
    st.divider()
