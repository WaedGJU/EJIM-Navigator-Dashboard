import streamlit as st

from utils.auth import login_gate, current_user, is_admin
from utils.style import inject_base_style, sidebar_user_box, COLORS
from utils.sheets import load_activities, update_activity_cell, ConflictError
from utils.compute import enrich

st.set_page_config(page_title="Team", page_icon="👥", layout="wide")
inject_base_style()
login_gate()
sidebar_user_box()

st.title("Team")
st.caption("Progress per person. Each member can mark their own activities as done directly here — "
           "admins can update anyone's.")

user = current_user()
df = enrich(load_activities())
if df.empty:
    st.stop()

STATUS_OPTIONS = ["Not started", "In Progress", "Completed", "On Hold",
                   "Unconfirmed - needs update", "Proposed - Pending Validation"]

people = sorted(df["Responsible (Name)"].dropna().astype(str).str.strip().unique())
people = [p for p in people if p]


def can_edit(person: str) -> bool:
    if is_admin():
        return True
    return user["name"].strip().lower() == person.strip().lower()


for person in people:
    sub = df[df["Responsible (Name)"].astype(str).str.strip() == person]
    total = len(sub)
    done = int((sub["Bucket"] == "Completed").sum())
    overdue = int(sub["is_overdue"].sum())
    pct = round(100 * done / total, 1) if total else 0
    editable_person = can_edit(person)

    st.markdown(
        f"""
        <div class="nav-card" style="margin-bottom:10px;">
          <div style="display:flex;justify-content:space-between;align-items:baseline;">
            <div style="font-weight:800;color:{COLORS['navy']};font-size:15px;">
              {person}{' 🔓' if editable_person else ''}
            </div>
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

    label = "✏️ Update my activities" if (editable_person and not is_admin()) else \
            ("✏️ Update this person's activities (admin)" if editable_person else "View activities")
    with st.expander(label):
        if not editable_person:
            st.dataframe(
                sub[["No.", "Original WP", "Activity", "Status", "End Date"]],
                use_container_width=True, hide_index=True,
            )
        else:
            for row_number, row in sub.iterrows():
                with st.container(border=True):
                    c1, c2 = st.columns([2, 1])
                    with c1:
                        st.markdown(f"**{row['Activity']}**")
                        st.caption(f"{row['Original WP']} · Due: {row.get('End Date', '—')} · "
                                   f"Current status: {row['Status']}")
                    with c2:
                        if row.get("is_overdue"):
                            st.error(f"{int(row['days_overdue'])} days overdue")
                        elif row.get("is_atrisk"):
                            st.warning("At risk")

                    k = f"team_{row_number}"
                    status_col, done_col = st.columns([1.5, 1])
                    new_status = status_col.selectbox(
                        "Status", STATUS_OPTIONS,
                        index=STATUS_OPTIONS.index(row["Status"]) if row["Status"] in STATUS_OPTIONS else 0,
                        key=f"status_{k}",
                    )
                    current_team_update = str(row.get("Team Update", "") or "").strip()
                    done_checked = done_col.checkbox(
                        "Mark as Done ✅", value=current_team_update.lower() == "done", key=f"done_{k}",
                    )

                    if st.button("💾 Save", key=f"save_{k}"):
                        try:
                            if new_status != row["Status"]:
                                update_activity_cell(row_number, "Status", new_status, user)
                            new_team_update = "Done" if done_checked else ""
                            if new_team_update != current_team_update and "Team Update" in df.columns:
                                update_activity_cell(row_number, "Team Update", new_team_update, user)
                            st.success("Saved ✅")
                            st.rerun()
                        except ConflictError as e:
                            st.error(str(e))
    st.divider()
