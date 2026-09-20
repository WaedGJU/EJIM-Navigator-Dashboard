import datetime
import streamlit as st

from utils.auth import login_gate, current_user, is_admin
from utils.style import inject_base_style, sidebar_user_box, COLORS
from utils.sheets import load_activities, update_activity_cell, ConflictError
from utils.compute import enrich

st.set_page_config(page_title="Meeting Prep", page_icon="🗓️", layout="wide")
inject_base_style()
login_gate()
sidebar_user_box()

# Team meetings happen every Sunday and Tuesday.
MEETING_WEEKDAYS = {6: "Sunday", 1: "Tuesday"}  # Python: Monday=0 ... Sunday=6


def next_meetings(n=2):
    today = datetime.date.today()
    found = []
    d = today
    while len(found) < n:
        if d.weekday() in MEETING_WEEKDAYS and d >= today:
            found.append((d, MEETING_WEEKDAYS[d.weekday()]))
        d += datetime.timedelta(days=1)
    return found


st.title("Meeting Prep")
st.caption("Everything the team needs ahead of the Sunday / Tuesday meeting, in one place.")

meetings = next_meetings(2)
c1, c2 = st.columns(2)
for col, (date_, label), badge in zip([c1, c2], meetings, ["Next meeting", "Following meeting"]):
    days_away = (date_ - datetime.date.today()).days
    with col:
        st.markdown(
            f"""
            <div style="background:linear-gradient(135deg,{COLORS['navy']},{COLORS['navy_dark']});
                        border-radius:14px;padding:16px 20px;color:#fff;">
              <div style="font-size:11.5px;opacity:.85;font-weight:700;">{badge}</div>
              <div style="font-size:18px;font-weight:800;margin-top:2px;">{label} — {date_.strftime('%d %b %Y')}</div>
              <div style="margin-top:8px;background:rgba(255,255,255,.2);display:inline-block;
                          border-radius:999px;padding:6px 16px;font-weight:800;">
                in {days_away} day{'s' if days_away != 1 else ''}
              </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

st.write("")

user = current_user()
df = enrich(load_activities())
if df.empty:
    st.stop()

agenda = df[df["is_overdue"] | df["is_atrisk"] | df["is_unassigned"] | df["is_needs_confirmation"]]

b1, b2 = st.columns(2)
with b1:
    st.download_button(
        "⬇ Export meeting agenda (CSV)",
        agenda.to_csv(index=False).encode("utf-8-sig"),
        file_name=f"navigator_meeting_agenda_{datetime.date.today()}.csv",
        use_container_width=True,
    )
with b2:
    st.caption(f"{len(agenda)} items need a decision at the next meeting "
               f"(delayed, at risk, no owner, or needs confirmation).")

st.divider()

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


tab_labels = ["🔴 Delayed", "🟠 At risk", "⚪ No owner", "🟡 Needs confirmation"]
tabs = st.tabs(tab_labels)
subsets = [
    df[df["is_overdue"]].sort_values("days_overdue", ascending=False),
    df[df["is_atrisk"]],
    df[df["is_unassigned"]],
    df[df["is_needs_confirmation"]],
]

for tab, sub, prefix in zip(tabs, subsets, ["mp_delayed", "mp_risk", "mp_unassigned", "mp_confirm"]):
    with tab:
        if sub.empty:
            st.success("Nothing here 🎉")
            continue
        for row_number, row in sub.iterrows():
            editable = can_edit(row)
            with st.container(border=True):
                st.markdown(f"**{row['Activity']}**  \n"
                            f"<span style='color:{COLORS['ink']};font-size:12.5px;'>"
                            f"{row['Original WP']} · Owner: {row.get('Responsible (Name)', '—')} · "
                            f"Status: {row['Status']} · Due: {row.get('End Date', '—')}</span>",
                            unsafe_allow_html=True)
                k = f"{prefix}_{row_number}"
                nc, ac = st.columns([2, 1.3])
                note = nc.text_area("Note for this meeting", value=str(row.get("Team_Notes", "") or ""),
                                     key=f"note_{k}", disabled=not editable, height=64)
                action = ac.selectbox("Agreed action", ACTION_OPTIONS, key=f"action_{k}", disabled=not editable)
                if editable and st.button("💾 Save", key=f"save_{k}"):
                    try:
                        if note != str(row.get("Team_Notes", "") or ""):
                            update_activity_cell(row_number, "Team_Notes", note, user)
                        if action != "— Select an action —":
                            update_activity_cell(row_number, "Agreed_Action", action, user)
                        st.success("Saved ✅")
                        st.rerun()
                    except ConflictError as e:
                        st.error(str(e))
