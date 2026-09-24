import datetime
import pandas as pd
import streamlit as st

from utils.auth import current_user, is_admin
from utils.style import COLORS, status_badge_html
from utils.sheets import load_activities, load_users, update_activity_cell, ConflictError
from utils.compute import enrich
from utils.constants import PROJECT_NAME, now_jordan
from utils.meeting_pdf import build_meeting_minutes_pdf

# Team meetings happen every Sunday and Tuesday.
FIXED_ATTENDANCE_ROSTER = ["Ziad", "Feras", "Waed", "Omar", "Heba", "Karma", "Rania", "Mohammad", "Maryam"]
MEETING_WEEKDAYS = {6: "Sunday", 1: "Tuesday"}  # Python: Monday=0 ... Sunday=6

FIELD_LABELS = {
    "Responsible (Name)": "Owner",
    "Start Date": "Start date",
    "End Date": "End date",
    "Team Update": "Done flag",
    "Team_Notes": "Team note",
    "Agreed_Action": "Agreed action",
}


def next_meetings(n=2):
    today = now_jordan().date()
    found = []
    d = today
    while len(found) < n:
        if d.weekday() in MEETING_WEEKDAYS and d >= today:
            found.append((d, MEETING_WEEKDAYS[d.weekday()]))
        d += datetime.timedelta(days=1)
    return found


def _parse_date(value):
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return pd.to_datetime(text).date()
    except Exception:
        return None


def record_change(activity: str, wp: str, field: str, old_value, new_value):
    """Keeps a running, in-session log of what got edited during this
    meeting — this is what feeds the 'Changes made' section of the PDF."""
    st.session_state.setdefault("meeting_changes", [])
    st.session_state["meeting_changes"].append({
        "activity": activity,
        "wp": wp,
        "field": FIELD_LABELS.get(field, field),
        "old": old_value,
        "new": new_value,
    })


# ---- Keep attendance + general notes alive across page switches ----
# Streamlit deletes a widget's session_state entry as soon as a run happens
# where that widget isn't drawn (i.e. the user opens another page tab). So
# each value is mirrored into a plain "_keep_" key that Streamlit never
# touches, and restored into the widget key before the widget is drawn.
ATTEND_KEYS = ["attend_select_all", "attend_extra_names"] + [f"attend_{n}" for n in FIXED_ATTENDANCE_ROSTER]
NOTES_KEY = "mp_general_notes"
PERSISTED_KEYS = ATTEND_KEYS + [NOTES_KEY]


def _restore_persisted():
    for k in PERSISTED_KEYS:
        keep = f"_keep_{k}"
        if k not in st.session_state and keep in st.session_state:
            st.session_state[k] = st.session_state[keep]


def _remember(keys):
    for k in keys:
        if k in st.session_state:
            st.session_state[f"_keep_{k}"] = st.session_state[k]


def _clear_attendance():
    for k in ATTEND_KEYS:
        st.session_state[k] = "" if k == "attend_extra_names" else False
    _remember(ATTEND_KEYS)


def _clear_general_notes():
    st.session_state[NOTES_KEY] = ""
    _remember([NOTES_KEY])


_restore_persisted()

st.title("Meeting Prep")
st.caption("Everything the team needs ahead of the Sunday / Tuesday meeting — review, edit straight "
           "onto Google Sheets, take attendance, and export the signed minutes as a PDF.")

meetings = next_meetings(2)
c1, c2 = st.columns(2)
for col, (date_, label), badge in zip([c1, c2], meetings, ["Next meeting", "Following meeting"]):
    days_away = (date_ - now_jordan().date()).days
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

users_df = load_users()
team_names = [n for n in users_df["Name"].dropna().astype(str).str.strip().tolist() if n] \
    if not users_df.empty and "Name" in users_df.columns else []
people_in_registry = sorted(df["Responsible (Name)"].dropna().astype(str).str.strip().unique())
for p in people_in_registry:
    if p and p not in team_names:
        team_names.append(p)

agenda = df[df["is_overdue"] | df["is_atrisk"] | df["is_unassigned"] | df["is_needs_confirmation"]]

b1, b2 = st.columns(2)
with b1:
    st.download_button(
        "⬇ Export meeting agenda (CSV)",
        agenda.to_csv(index=False).encode("utf-8-sig"),
        file_name=f"navigator_meeting_agenda_{now_jordan().date()}.csv",
        use_container_width=True,
    )
with b2:
    st.caption(f"{len(agenda)} items need a decision at the next meeting "
               f"(delayed, at risk, no owner, or needs confirmation).")

st.divider()

# ---------------- Attendance ----------------
st.subheader("Attendance")
st.caption("Fixed team roster — unchecked by default. Anyone not on this list can be added below.")


def _select_all_attendance_changed():
    new_val = st.session_state["attend_select_all"]
    for _name in FIXED_ATTENDANCE_ROSTER:
        st.session_state[f"attend_{_name}"] = new_val


st.checkbox("Select all", key="attend_select_all", on_change=_select_all_attendance_changed)

attendance = []
att_cols = st.columns(4)
for i, name in enumerate(FIXED_ATTENDANCE_ROSTER):
    with att_cols[i % 4]:
        present = st.checkbox(name, key=f"attend_{name}")
        attendance.append((name, present))

extra_names_raw = st.text_input(
    "Add anyone not on the list above (comma-separated names)",
    key="attend_extra_names",
    placeholder="e.g. Ahmad Nasser, Lina Qasem",
)
for extra_name in [n.strip() for n in extra_names_raw.split(",") if n.strip()]:
    attendance.append((extra_name, True))

_remember(ATTEND_KEYS)
st.button("🗑 Clear attendance", key="mp_clear_attendance", on_click=_clear_attendance)

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


st.subheader("Agenda")
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
                h1, h2 = st.columns([3, 1])
                h1.markdown(f"**{row['Activity']}**  \n"
                            f"<span style='color:{COLORS['ink']};font-size:12.5px;'>{row['Original WP']}</span>",
                            unsafe_allow_html=True)
                h2.markdown(status_badge_html(row["AutoStatus"]), unsafe_allow_html=True)

                k = f"{prefix}_{row_number}"
                current_owner = str(row.get("Responsible (Name)", "")).strip()
                owner_options = team_names if current_owner in team_names else [current_owner] + team_names

                owner_col, done_col = st.columns([2, 1])
                new_owner = owner_col.selectbox(
                    "Owner", owner_options,
                    index=owner_options.index(current_owner) if current_owner in owner_options else 0,
                    key=f"owner_{k}", disabled=not editable,
                )
                current_team_update = str(row.get("Team Update", "") or "").strip()
                done_checked = done_col.checkbox(
                    "Done ✅", value=current_team_update.lower() == "done",
                    key=f"done_{k}", disabled=not editable,
                )

                start_col, end_col = st.columns(2)
                current_start = str(row.get("Start Date", "") or "").strip()
                current_end = str(row.get("End Date", "") or "").strip()
                new_start = start_col.date_input("Start date", value=_parse_date(current_start),
                                                  key=f"start_{k}", disabled=not editable)
                new_end = end_col.date_input("End date", value=_parse_date(current_end),
                                              key=f"end_{k}", disabled=not editable)

                nc, ac = st.columns([2, 1.3])
                note = nc.text_area("Note for this meeting", value=str(row.get("Team_Notes", "") or ""),
                                     key=f"note_{k}", disabled=not editable, height=64)
                action = ac.selectbox("Agreed action", ACTION_OPTIONS, key=f"action_{k}", disabled=not editable)

                if editable and st.button("💾 Save", key=f"save_{k}"):
                    try:
                        if new_owner != current_owner:
                            update_activity_cell(row_number, "Responsible (Name)", new_owner, user)
                            record_change(row["Activity"], row["Original WP"], "Responsible (Name)",
                                          current_owner, new_owner)
                        new_team_update = "Done" if done_checked else ""
                        if new_team_update != current_team_update and "Team Update" in df.columns:
                            update_activity_cell(row_number, "Team Update", new_team_update, user)
                            record_change(row["Activity"], row["Original WP"], "Team Update",
                                          current_team_update or "—", new_team_update or "—")
                        if new_start and new_start.isoformat() != current_start:
                            update_activity_cell(row_number, "Start Date", new_start.isoformat(), user)
                            record_change(row["Activity"], row["Original WP"], "Start Date",
                                          current_start, new_start.isoformat())
                        if new_end and new_end.isoformat() != current_end:
                            update_activity_cell(row_number, "End Date", new_end.isoformat(), user)
                            record_change(row["Activity"], row["Original WP"], "End Date",
                                          current_end, new_end.isoformat())
                        if note != str(row.get("Team_Notes", "") or ""):
                            update_activity_cell(row_number, "Team_Notes", note, user)
                            record_change(row["Activity"], row["Original WP"], "Team_Notes",
                                          str(row.get("Team_Notes", "") or "—"), note or "—")
                        if action != "— Select an action —":
                            update_activity_cell(row_number, "Agreed_Action", action, user)
                            record_change(row["Activity"], row["Original WP"], "Agreed_Action", "—", action)
                        st.success("Saved ✅")
                        st.rerun()
                    except ConflictError as e:
                        st.error(str(e))
                elif not editable:
                    st.caption("🔒 Read-only — this activity isn't assigned to you")

st.divider()

# ---------------- Minutes of meeting (PDF) ----------------
st.subheader("Minutes of meeting")
changes_this_session = st.session_state.get("meeting_changes", [])
if changes_this_session:
    with st.expander(f"📝 {len(changes_this_session)} change(s) recorded this session"):
        st.dataframe(pd.DataFrame(changes_this_session), use_container_width=True, hide_index=True)
    if st.button("Clear changes log"):
        st.session_state["meeting_changes"] = []
        st.rerun()
else:
    st.caption("No changes saved yet this session — the PDF will note that until something is edited above.")

st.markdown("**General notes**")
st.caption("Anything discussed that isn't tied to one specific activity — goes into its own section "
           "in the minutes PDF below. Click \"Save notes\" before downloading, or the box's latest "
           "edit may not have registered yet.")

# A plain st.text_area only commits its edit to Streamlit on blur (clicking
# away) or Ctrl+Enter — typing a note and then clicking straight through to
# "Download meeting minutes" can fire that click before the edit lands,
# silently downloading a PDF with the notes box still empty. Wrapping it in
# a form makes the commit explicit and atomic: nothing below sees the new
# text until "Save notes" is clicked, so there's no race to lose.
with st.form("mp_general_notes_form", border=False):
    st.text_area(
        "General notes for this meeting",
        key="mp_general_notes",
        height=100,
        label_visibility="collapsed",
        placeholder="e.g. Budget update from finance, new external partner introduced, next milestone review date...",
    )
    st.form_submit_button("💾 Save notes", use_container_width=False)

general_notes = st.session_state.get("mp_general_notes", "")
_remember([NOTES_KEY])
if general_notes:
    st.button("🗑 Clear general notes", key="mp_clear_notes", on_click=_clear_general_notes)

# Jordan time specifically, not the server's own clock — Streamlit Community
# Cloud runs its servers on UTC, which would otherwise stamp the minutes
# 2-3 hours off from what the team actually sees on their own clocks.
generated_at = now_jordan()

pdf_bytes = build_meeting_minutes_pdf(
    project_name=PROJECT_NAME,
    meeting_date=generated_at.date(),
    attendance=attendance,
    changes=changes_this_session,
    general_notes=general_notes,
    generated_at=generated_at,
)
st.download_button(
    "⬇ Download meeting minutes (PDF)",
    data=pdf_bytes,
    file_name=f"navigator_meeting_minutes_{generated_at.strftime('%Y-%m-%d_%H%M')}.pdf",
    mime="application/pdf",
    use_container_width=True,
)
