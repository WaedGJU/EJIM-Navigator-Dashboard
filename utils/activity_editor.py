"""
One shared editor for a single activity, used on every page that lists
activities, so editing works the same everywhere: work package, owner, Done
flag, start/end dates, plus delete.

Who can edit or delete: admins can touch every activity; everyone else only
the activities they own (their name appears in "Responsible (Name)").
Status itself is still never picked by hand — ticking Done is what marks an
activity Completed (update_activity_cell keeps the Status column in sync).
"""

import pandas as pd
import streamlit as st

from utils.auth import current_user, is_admin
from utils.sheets import load_users, update_activity_cell, delete_activity, ConflictError

# Saved by the Save button. The Done flag isn't here: it saves itself the
# moment it's clicked (see _save_done_now).
CORE_FIELDS = ["Original WP", "Responsible (Name)", "Start Date", "End Date"]


def can_edit(row) -> bool:
    if is_admin():
        return True
    user = current_user()
    owner = str(row.get("Responsible (Name)", "")).lower()
    return bool(user) and user["name"].lower() in owner


def _parse_date(value):
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return pd.to_datetime(text).date()
    except Exception:
        return None


def wp_options(df: pd.DataFrame) -> list:
    return sorted(df["Original WP"].dropna().astype(str).str.strip().unique()) if not df.empty else []


def team_options(df: pd.DataFrame) -> list:
    """Every active team member from the Users tab plus anyone already owning
    an activity, so reassigning to someone new works too."""
    users_df = load_users()
    names = [n for n in users_df["Name"].dropna().astype(str).str.strip().tolist() if n] \
        if not users_df.empty and "Name" in users_df.columns else []
    if not df.empty:
        for p in sorted(df["Responsible (Name)"].dropna().astype(str).str.strip().unique()):
            if p and p not in names:
                names.append(p)
    return names


def _with_current(options: list, current: str) -> list:
    return options if current in options else [current] + options


def activity_key(prefix: str, row) -> str:
    """Widget key for one activity, built from its No. — never from its sheet
    row number. Streamlit keeps a widget's value by key, so a row-number key
    would hand one activity's unsaved ticks to whichever activity slides into
    that row after a delete."""
    return f"{prefix}_{str(row.get('No.', '')).strip()}"


def _sync_widget(key: str, current):
    """Streamlit remembers a widget's value by key and ignores later defaults,
    so a box could keep showing an old value after the sheet changed. Reset
    it to the sheet's value whenever that value changes; an unsaved edit the
    user is making stays as long as the sheet hasn't moved underneath it."""
    base = f"_sheet_value_{key}"
    if base not in st.session_state or st.session_state[base] != current:
        st.session_state[key] = current
        st.session_state[base] = current


def _save_done_now(row, k: str, on_change=None):
    """Runs the moment the Done box is ticked/unticked, so Done never sits on
    screen unsaved while the status still says otherwise."""
    user = current_user()
    new = "Done" if st.session_state[f"done_{k}"] else ""
    old = str(row.get("Team Update", "") or "").strip()
    try:
        update_activity_cell(row, "Team Update", new, user)
        if on_change:
            on_change("Team Update", old or "—", new or "—")
        st.toast("Marked Done ✅ — status set to Completed" if new else "Done removed")
    except ConflictError as e:
        st.session_state[f"done_{k}"] = not st.session_state[f"done_{k}"]
        st.toast(f"⚠️ {e}")


def core_inputs(row, k: str, wps: list, team_names: list, editable: bool, on_change=None) -> dict:
    """Draws the shared fields and returns {column: new value} for each one.
    The Done box saves on its own as soon as it's clicked; the other fields
    are saved with the Save button."""
    current_wp = str(row.get("Original WP", "") or "").strip()
    current_owner = str(row.get("Responsible (Name)", "") or "").strip()
    current_done = str(row.get("Team Update", "") or "").strip().lower() == "done"

    wp_opts = _with_current(wps, current_wp)
    owner_opts = _with_current(team_names, current_owner)

    _sync_widget(f"wp_{k}", current_wp)
    _sync_widget(f"owner_{k}", current_owner)
    _sync_widget(f"done_{k}", current_done)
    _sync_widget(f"start_{k}", _parse_date(row.get("Start Date")))
    _sync_widget(f"end_{k}", _parse_date(row.get("End Date")))

    wp_col, owner_col, done_col = st.columns([2, 1.6, 0.8])
    new_wp = wp_col.selectbox("Work package", wp_opts, key=f"wp_{k}", disabled=not editable)
    new_owner = owner_col.selectbox("Owner", owner_opts, key=f"owner_{k}", disabled=not editable)
    with done_col:
        st.write("")  # lines the checkbox up with the inputs beside it
        st.checkbox("Done ✅", key=f"done_{k}", disabled=not editable,
                    on_change=_save_done_now, args=(row, k, on_change),
                    help="Saved instantly — marks the activity Completed.")

    start_col, end_col = st.columns(2)
    new_start = start_col.date_input("Start date", key=f"start_{k}", disabled=not editable)
    new_end = end_col.date_input("End date", key=f"end_{k}", disabled=not editable)

    return {
        "Original WP": new_wp,
        "Responsible (Name)": new_owner,
        "Start Date": new_start.isoformat() if new_start else str(row.get("Start Date", "") or "").strip(),
        "End Date": new_end.isoformat() if new_end else str(row.get("End Date", "") or "").strip(),
    }


def save_core_changes(row, new_values: dict, user: dict, on_change=None) -> int:
    """Writes only the fields that actually changed. `on_change(column, old, new)`
    is called for each one (Meeting Prep uses it for the minutes). Returns how
    many fields were written."""
    written = 0
    for col in CORE_FIELDS:
        if col not in new_values or col not in row.index:
            continue
        old = str(row.get(col, "") or "").strip()
        new = str(new_values[col] or "").strip()
        if new == old:
            continue
        update_activity_cell(row, col, new, user)
        if on_change:
            on_change(col, old or "—", new or "—")
        written += 1
    return written


def delete_control(row, k: str, user: dict, on_delete=None):
    """A Delete button that asks for confirmation first. Shown only to people
    allowed to edit this activity."""
    if not can_edit(row):
        return
    with st.popover("🗑 Delete", use_container_width=True):
        st.warning(f"Delete **{row['Activity']}**? It's removed from the registry and kept in the "
                   f"Deleted_Activities tab of the Google Sheet.")
        if st.button("Yes, delete it", key=f"delete_{k}", type="primary"):
            try:
                delete_activity(row, user)
                if on_delete:
                    on_delete()
                st.success("Deleted ✅")
                st.rerun()
            except ConflictError as e:
                st.error(str(e))


def activity_editor(row, k: str, wps: list, team_names: list):
    """The complete editor (fields + Save + Delete) for pages that don't add
    fields of their own."""
    user = current_user()
    editable = can_edit(row)
    new_values = core_inputs(row, k, wps, team_names, editable)

    if not editable:
        st.caption("🔒 Read-only — this activity isn't assigned to you")
        return

    save_col, delete_col = st.columns([3, 1])
    if save_col.button("💾 Save", key=f"save_{k}", use_container_width=True):
        try:
            save_core_changes(row, new_values, user)
            st.success("Saved ✅")
            st.rerun()
        except ConflictError as e:
            st.error(str(e))
    with delete_col:
        delete_control(row, k, user)


def activity_picker(view: pd.DataFrame, k: str, wps: list, team_names: list):
    """For pages that show activities as a table: pick one from the table and
    edit or delete it right there."""
    if view.empty:
        return
    with st.expander("✏️ Edit or delete an activity from this table"):
        labels = {rn: f"No. {r.get('No.', '')} — {r['Activity']}" for rn, r in view.iterrows()}
        picked = st.selectbox("Activity", list(labels), format_func=labels.get,
                              index=None, placeholder="Choose an activity…", key=f"pick_{k}")
        if picked is not None:
            row = view.loc[picked]
            activity_editor(row, activity_key(k, row), wps, team_names)
