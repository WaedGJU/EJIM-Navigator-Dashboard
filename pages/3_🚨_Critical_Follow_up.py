import streamlit as st

from utils.auth import login_gate, current_user, is_admin
from utils.style import inject_base_style, sidebar_user_box
from utils.sheets import load_activities, update_activity_cell, ConflictError
from utils.compute import enrich

st.set_page_config(page_title="Critical Follow-up", page_icon="🚨", layout="wide")
inject_base_style()
login_gate()
sidebar_user_box()

st.title("Critical Follow-up")
st.caption("Direct edits write straight to Google Sheets — each member can edit only their own activities; admins can edit everything.")

user = current_user()
df = enrich(load_activities())
if df.empty:
    st.stop()

ACTION_OPTIONS = [
    "— Select an action —", "Confirmed — keep as is", "Update status / date", "Reassign owner",
    "Escalate recruitment", "Follow up with external party (MODEE/GIZ/MoL)", "Re-prioritize / reduce scope",
    "Mark as not applicable", "Needs further discussion",
]
STATUS_OPTIONS = ["Not started", "In Progress", "Completed", "On Hold",
                   "Unconfirmed - needs update", "Proposed - Pending Validation"]


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
                st.caption(f"{row['Original WP']} · Owner: {row.get('Responsible (Name)', '—')} · "
                           f"Status: {row['Status']} · Due: {row.get('End Date', '—')}")
            with c2:
                if row.get("is_overdue"):
                    st.error(f"{int(row['days_overdue'])} days overdue")
                elif row.get("is_atrisk"):
                    st.warning("At risk")

            k = f"{key_prefix}_{row_number}"
            note_col, action_col, status_col = st.columns([2, 1.3, 1.3])
            note = note_col.text_area("Team note", value=str(row.get("Team_Notes", "") or ""),
                                       key=f"note_{k}", disabled=not editable, height=68)
            action = action_col.selectbox("Agreed action", ACTION_OPTIONS,
                                           index=0, key=f"action_{k}", disabled=not editable)
            new_status = status_col.selectbox("Update status", STATUS_OPTIONS,
                                               index=STATUS_OPTIONS.index(row["Status"]) if row["Status"] in STATUS_OPTIONS else 0,
                                               key=f"status_{k}", disabled=not editable)

            if editable and status_col.button("💾 Save", key=f"save_{k}", use_container_width=True):
                try:
                    if note != str(row.get("Team_Notes", "") or ""):
                        update_activity_cell(row_number, "Team_Notes", note, user)
                    if action != "— Select an action —":
                        update_activity_cell(row_number, "Agreed_Action", action, user)
                    if new_status != row["Status"]:
                        update_activity_cell(row_number, "Status", new_status, user)
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
