import streamlit as st

from utils.auth import current_user
from utils.style import status_badge_html
from utils.sheets import load_activities, update_activity_cell, ConflictError
from utils.compute import enrich
from utils.activity_editor import (can_edit, core_inputs, save_core_changes, delete_control,
                                   wp_options, team_options)

st.title("Critical Follow-up")
st.caption("Direct edits write straight to Google Sheets — each member can edit or delete only their own "
           "activities; admins can edit everything. Status here is computed automatically from the Done "
           "flag and the start/end dates — it's never picked from a dropdown.")

user = current_user()
df = enrich(load_activities())
if df.empty:
    st.stop()

wps = wp_options(df)
team_names = team_options(df)

ACTION_OPTIONS = [
    "— Select an action —", "Confirmed — keep as is", "Update status / date", "Reassign owner",
    "Escalate recruitment", "Follow up with external party (MODEE/GIZ/MoL)", "Re-prioritize / reduce scope",
    "Mark as not applicable", "Needs further discussion",
]


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
            new_values = core_inputs(row, k, wps, team_names, editable)
            note_col, action_col = st.columns([1.7, 1.3])
            note = note_col.text_area("Team note", value=str(row.get("Team_Notes", "") or ""),
                                       key=f"note_{k}", disabled=not editable, height=68)
            action = action_col.selectbox("Agreed action", ACTION_OPTIONS,
                                           index=0, key=f"action_{k}", disabled=not editable)

            if not editable:
                st.caption("🔒 Read-only — this activity isn't assigned to you")
                continue

            save_col, delete_col = st.columns([3, 1])
            if save_col.button("💾 Save", key=f"save_{k}", use_container_width=True):
                try:
                    save_core_changes(row, new_values, user)
                    if note != str(row.get("Team_Notes", "") or ""):
                        update_activity_cell(row, "Team_Notes", note, user)
                    if action != "— Select an action —":
                        update_activity_cell(row, "Agreed_Action", action, user)
                    st.success("Saved ✅")
                    st.rerun()
                except ConflictError as e:
                    st.error(str(e))
            with delete_col:
                delete_control(row, k, user)


tabs = st.tabs(["🔴 Delayed", "🟠 At risk", "⚪ No owner", "🟡 Needs confirmation"])

with tabs[0]:
    render_tab(df[df["is_overdue"]].sort_values("days_overdue", ascending=False), "delayed")
with tabs[1]:
    render_tab(df[df["is_atrisk"]], "risk")
with tabs[2]:
    render_tab(df[df["is_unassigned"]], "unassigned")
with tabs[3]:
    render_tab(df[df["is_needs_confirmation"]], "confirm")
