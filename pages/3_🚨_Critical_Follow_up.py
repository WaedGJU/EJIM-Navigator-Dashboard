import streamlit as st

from utils.auth import current_user, is_admin
from utils.style import status_badge_html
from utils.sheets import load_activities, update_activity_cell, ConflictError
from utils.compute import enrich

st.title("Critical Follow-up")
st.caption("Direct edits write straight to Google Sheets — each member can edit only their own activities; "
           "admins can edit everything. Status here is computed automatically from the Done flag and the "
           "start/end dates — it's never picked from a dropdown.")

user = current_user()
df = enrich(load_activities())
if df.empty:
    st.stop()

ACTION_OPTIONS = [
    "— Select an action —", "Confirmed — keep as is", "Update status / date", "Reassign owner",
    "Escalate recruitment", "Follow up with external party (MODEE/GIZ/MoL)", "Re-prioritize / reduce scope",
    "Mark as not applicable", "Needs further discussion",
]


def can_edit(row) -> bool:
    if is_admin():
        return True
    owner = str(row.get("Responsible (Name)", "")).lower()
    return user["name"].lower() in owner


def render_tab(sub, key_prefix):
    if sub.empty:
        st.success("Nothing in this category right now 🎉")
        return

    for row_number, row in sub.iterrows():
        editable = can_edit(row)
        with st.container(border=True):
            c1, c2 = st.columns([2, 1])
            with c1:
                st.markdown(f"**{row['Activity']}**")
                st.caption(
                    f"{row['Original WP']} · Owner: {row.get('Responsible (Name)', '—')}  \n"
                    f"Start: {row.get('Start Date', '—')} · End: {row.get('End Date', '—')}"
                )
            with c2:
                st.markdown(status_badge_html(row["AutoStatus"]), unsafe_allow_html=True)
                if row.get("is_overdue"):
                    st.error(f"{int(row['days_overdue'])} days overdue")
                elif row.get("is_atrisk"):
                    st.warning("At risk")

            k = f"{key_prefix}_{row_number}"
            current_team_update = str(row.get("Team Update", "") or "").strip()
            done_col, note_col, action_col = st.columns([1, 1.7, 1.3])
            done_checked = done_col.checkbox(
                "Done ✅", value=current_team_update.lower() == "done",
                key=f"done_{k}", disabled=not editable,
            )
            note = note_col.text_area("Team note", value=str(row.get("Team_Notes", "") or ""),
                                       key=f"note_{k}", disabled=not editable, height=68)
            action = action_col.selectbox("Agreed action", ACTION_OPTIONS,
                                           index=0, key=f"action_{k}", disabled=not editable)

            if editable and st.button("💾 Save", key=f"save_{k}", use_container_width=True):
                try:
                    new_team_update = "Done" if done_checked else ""
                    if new_team_update != current_team_update and "Team Update" in df.columns:
                        update_activity_cell(row_number, "Team Update", new_team_update, user)
                    if note != str(row.get("Team_Notes", "") or ""):
                        update_activity_cell(row_number, "Team_Notes", note, user)
                    if action != "— Select an action —":
                        update_activity_cell(row_number, "Agreed_Action", action, user)
                    st.success("Saved ✅")
                    st.rerun()
                except ConflictError as e:
                    st.error(str(e))
            elif not editable:
                st.caption("🔒 Read-only — this activity isn't assigned to you")


tabs = st.tabs(["🔴 Delayed", "🟠 At risk", "⚪ No owner", "🟡 Needs confirmation"])

with tabs[0]:
    render_tab(df[df["is_overdue"]].sort_values("days_overdue", ascending=False), "delayed")
with tabs[1]:
    render_tab(df[df["is_atrisk"]], "risk")
with tabs[2]:
    render_tab(df[df["is_unassigned"]], "unassigned")
with tabs[3]:
    render_tab(df[df["is_needs_confirmation"]], "confirm")
