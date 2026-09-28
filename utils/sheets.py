"""
All Google Sheets access goes through this file only — reads, writes, and logging.
Uses a Service Account ("robot" credentials) stored in st.secrets, not any
individual team member's Google account.
"""

import gspread
import pandas as pd
import streamlit as st
from google.oauth2.service_account import Credentials

# Jordan wall-clock time, not the server's own clock — Streamlit Community
# Cloud runs its servers on UTC, which would otherwise stamp every
# Last_Edited_At / Edit_Log / Login_Log entry 2-3 hours off from what the
# team actually sees on their own clocks.
from utils.constants import now_jordan

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

ACTIVITY_SHEET = "Activity_Registry"
USERS_SHEET = "Users"
LOGIN_LOG_SHEET = "Login_Log"
EDIT_LOG_SHEET = "Edit_Log"


@st.cache_resource(show_spinner=False)
def _client() -> gspread.Client:
    """One connection reused for the app's lifetime (never opens a new one per call)."""
    creds_dict = dict(st.secrets["gcp_service_account"])
    creds = Credentials.from_service_account_info(creds_dict, scopes=SCOPES)
    return gspread.authorize(creds)


@st.cache_resource(show_spinner=False)
def _spreadsheet():
    gc = _client()
    return gc.open_by_key(st.secrets["sheet"]["spreadsheet_id"])


def _ws(name: str):
    return _spreadsheet().worksheet(name)


# ---------------------------------------------------------------------------
# Reads (short cache TTL so we don't burn the Google API quota and stay fast)
# ---------------------------------------------------------------------------

@st.cache_data(ttl=20, show_spinner=False)
def load_activities() -> pd.DataFrame:
    records = _ws(ACTIVITY_SHEET).get_all_records()
    df = pd.DataFrame(records)
    if not df.empty:
        df.index = df.index + 2  # the real row number inside the Google Sheet (1 = header)
    return df


@st.cache_data(ttl=60, show_spinner=False)
def load_users() -> pd.DataFrame:
    records = _ws(USERS_SHEET).get_all_records()
    return pd.DataFrame(records)


def clear_activity_cache():
    load_activities.clear()


def clear_users_cache():
    load_users.clear()


# ---------------------------------------------------------------------------
# Writes — one cell at a time, never overwrite the whole sheet (avoids
# clobbering someone else's concurrent edit)
# ---------------------------------------------------------------------------

def update_activity_cell(row_number: int, column_name: str, new_value, user: dict):
    """Updates a single activity cell, stamps Last_Edited_By / Last_Edited_At, and logs it."""
    ws = _ws(ACTIVITY_SHEET)
    header = ws.row_values(1)

    if column_name not in header:
        raise ValueError(f"Column not found in the sheet: {column_name}")

    col_idx = header.index(column_name) + 1
    old_value = ws.cell(row_number, col_idx).value

    # Simple conflict guard: make sure nobody else edited this row in the meantime
    if "Last_Edited_At" in header:
        stamp_col = header.index("Last_Edited_At") + 1
        current_stamp = ws.cell(row_number, stamp_col).value
        expected_stamp = st.session_state.get("row_stamps", {}).get(row_number)
        if expected_stamp is not None and current_stamp != expected_stamp:
            raise ConflictError(
                "This row was just edited by someone else. Refresh the page and try again."
            )

    ws.update_cell(row_number, col_idx, new_value)

    now = now_jordan().strftime("%Y-%m-%d %H:%M:%S")
    if "Last_Edited_By" in header:
        ws.update_cell(row_number, header.index("Last_Edited_By") + 1, user["name"])
    if "Last_Edited_At" in header:
        ws.update_cell(row_number, header.index("Last_Edited_At") + 1, now)

    append_edit_log(user, row_number, column_name, old_value, new_value)
    clear_activity_cache()


def get_next_activity_number() -> int:
    """The next 'No.' value for a brand-new activity — one past the highest
    number currently in the sheet (falls back to the row count if that
    column is missing or non-numeric)."""
    df = load_activities()
    if df.empty or "No." not in df.columns:
        return 1
    nums = pd.to_numeric(df["No."], errors="coerce").dropna()
    return int(nums.max()) + 1 if not nums.empty else len(df) + 1


def append_activity_row(values: dict, user: dict) -> int:
    """Appends a brand-new activity row. `values` is matched against the
    sheet's own header so nothing lands in the wrong column regardless of
    field order, and any column not passed in is left blank. Stamps who
    added it and logs the addition to Edit_Log — same accountability as any
    other edit. Returns the new row's row number inside the sheet."""
    ws = _ws(ACTIVITY_SHEET)
    header = ws.row_values(1)
    now = now_jordan().strftime("%Y-%m-%d %H:%M:%S")

    row_values = dict(values)
    if "Last_Edited_By" in header:
        row_values.setdefault("Last_Edited_By", user["name"])
    if "Last_Edited_At" in header:
        row_values.setdefault("Last_Edited_At", now)

    row = [row_values.get(col, "") for col in header]
    ws.append_row(row, value_input_option="USER_ENTERED")
    new_row_number = len(ws.get_all_values())  # the row we just appended lands last

    append_edit_log(user, new_row_number, "New Activity", "—", row_values.get("Activity", ""))
    clear_activity_cache()
    return new_row_number


class ConflictError(Exception):
    """Raised when two people try to edit the same row at roughly the same moment."""
    pass


# ---------------------------------------------------------------------------
# Users tab — writes for the Admin · Users page (reset PIN, add user,
# unlock/activate). Kept here so ALL Google Sheets access still lives in this
# one file. Any column that doesn't exist yet (e.g. the lockout columns
# Failed_Attempts / Locked_Until) is created automatically the first time it
# is written, so nothing has to be added to the sheet by hand.
# ---------------------------------------------------------------------------

def _ensure_columns(ws, needed) -> list:
    """Make sure each column name in `needed` exists in the header row (row 1);
    append any that are missing to the end. Returns the up-to-date header list.
    Uses update_cell only, so it works the same across gspread versions."""
    header = ws.row_values(1)
    for col in needed:
        if col not in header:
            header.append(col)
            ws.update_cell(1, len(header), col)  # write the new header cell at the end
    return header


def _find_user_row(ws, email: str):
    """(row_number, header) for the user whose Email matches (case-insensitive),
    or (None, header) if there's no such user. row_number is the real 1-based
    row inside the Google Sheet."""
    values = ws.get_all_values()
    if not values:
        return None, []
    header = values[0]
    if "Email" not in header:
        return None, header
    ecol = header.index("Email")
    target = str(email).strip().lower()
    for i, row in enumerate(values[1:], start=2):
        if len(row) > ecol and str(row[ecol]).strip().lower() == target:
            return i, header
    return None, header


def user_exists(email: str) -> bool:
    ws = _ws(USERS_SHEET)
    row, _ = _find_user_row(ws, email)
    return row is not None


def update_user_cell(email: str, column: str, value):
    """Set a single cell for the user with this email. Creates the column if it
    doesn't exist yet. Raises ValueError if there's no matching user."""
    ws = _ws(USERS_SHEET)
    row, header = _find_user_row(ws, email)
    if row is None:
        raise ValueError(f"No user found with email: {email}")
    if column not in header:
        header = _ensure_columns(ws, [column])
    col_idx = header.index(column) + 1
    ws.update_cell(row, col_idx, value)
    clear_users_cache()


def append_user_row(values: dict):
    """Append a brand-new user row, matched to the sheet's own header so each
    value lands in the right column regardless of order. Any key not already a
    column is added to the header first."""
    ws = _ws(USERS_SHEET)
    header = ws.row_values(1)
    missing = [k for k in values if k not in header]
    if missing:
        header = _ensure_columns(ws, missing)
    row = [values.get(col, "") for col in header]
    ws.append_row(row, value_input_option="USER_ENTERED")
    clear_users_cache()


# ---------------------------------------------------------------------------
# Logs
# ---------------------------------------------------------------------------

def append_edit_log(user: dict, row_number: int, column_name: str, old_value, new_value):
    now = now_jordan().strftime("%Y-%m-%d %H:%M:%S")
    _ws(EDIT_LOG_SHEET).append_row(
        [now, user["email"], user["name"], row_number, column_name, str(old_value), str(new_value)],
        value_input_option="USER_ENTERED",
    )


def append_login_log(email: str, name: str, result: str):
    now = now_jordan().strftime("%Y-%m-%d %H:%M:%S")
    _ws(LOGIN_LOG_SHEET).append_row([now, email, name, result], value_input_option="USER_ENTERED")


@st.cache_data(ttl=15, show_spinner=False)
def load_login_log() -> pd.DataFrame:
    return pd.DataFrame(_ws(LOGIN_LOG_SHEET).get_all_records())


@st.cache_data(ttl=15, show_spinner=False)
def load_edit_log() -> pd.DataFrame:
    return pd.DataFrame(_ws(EDIT_LOG_SHEET).get_all_records())


# ---------------------------------------------------------------------------
# Bugs Log — the team reports problems they hit in the app. Two tabs, both
# created automatically the first time they're needed (nothing to set up by
# hand in the Google Sheet):
#   Bugs_Log   → one row per bug (who / when / page / description / status)
#   Bug_Images → the optional screenshot, stored as compressed JPEG text split
#                across rows (a single Google Sheets cell holds max 50,000
#                characters). Kept inside the same Google Sheet on purpose, so
#                no extra Google Drive folder, permission or quota is needed.
# ---------------------------------------------------------------------------

BUGS_SHEET = "Bugs_Log"
BUG_IMAGES_SHEET = "Bug_Images"

BUG_COLUMNS = [
    "Bug_ID", "Reported_At", "Reported_By", "Reported_By_Email", "Page",
    "Description", "Status", "Has_Screenshot", "Solved_By", "Solved_At",
    "Last_Updated_By", "Last_Updated_At",
]
BUG_IMAGE_COLUMNS = ["Bug_ID", "Part", "Data"]
_IMAGE_CHUNK = 45_000  # safely under the 50,000-character cell limit


def _ws_or_create(name: str, columns: list):
    """Open a worksheet, creating it (with its header row) if it doesn't exist yet.
    Also adds any header columns that are missing from an existing tab."""
    ss = _spreadsheet()
    try:
        ws = ss.worksheet(name)
    except gspread.exceptions.WorksheetNotFound:
        ws = ss.add_worksheet(title=name, rows=200, cols=max(len(columns), 5))
        ws.update_cell(1, 1, columns[0])
        for i, col in enumerate(columns[1:], start=2):
            ws.update_cell(1, i, col)
        return ws
    _ensure_columns(ws, columns)
    return ws


@st.cache_data(ttl=15, show_spinner=False)
def load_bugs() -> pd.DataFrame:
    ws = _ws_or_create(BUGS_SHEET, BUG_COLUMNS)
    df = pd.DataFrame(ws.get_all_records())
    if df.empty:
        return pd.DataFrame(columns=BUG_COLUMNS)
    return df


def clear_bugs_cache():
    load_bugs.clear()
    load_bug_image.clear()


def get_next_bug_id() -> str:
    df = load_bugs()
    nums = pd.to_numeric(
        df["Bug_ID"].astype(str).str.extract(r"(\d+)")[0], errors="coerce"
    ).dropna() if not df.empty else pd.Series(dtype=float)
    n = int(nums.max()) + 1 if not nums.empty else 1
    return f"BUG-{n:03d}"


def append_bug(page: str, description: str, user: dict, image_b64: str = "") -> str:
    """Adds a new bug (status Open) and, if given, its screenshot. Returns the Bug_ID."""
    ws = _ws_or_create(BUGS_SHEET, BUG_COLUMNS)
    header = ws.row_values(1)
    bug_id = get_next_bug_id()
    now = now_jordan().strftime("%Y-%m-%d %H:%M:%S")
    values = {
        "Bug_ID": bug_id,
        "Reported_At": now,
        "Reported_By": user["name"],
        "Reported_By_Email": user["email"],
        "Page": page,
        "Description": description,
        "Status": "Open",
        "Has_Screenshot": "Yes" if image_b64 else "No",
        "Last_Updated_By": user["name"],
        "Last_Updated_At": now,
    }
    ws.append_row([values.get(c, "") for c in header], value_input_option="RAW")

    if image_b64:
        img_ws = _ws_or_create(BUG_IMAGES_SHEET, BUG_IMAGE_COLUMNS)
        chunks = [image_b64[i:i + _IMAGE_CHUNK] for i in range(0, len(image_b64), _IMAGE_CHUNK)]
        img_ws.append_rows([[bug_id, i + 1, c] for i, c in enumerate(chunks)],
                           value_input_option="RAW")

    clear_bugs_cache()
    return bug_id


def update_bug_status(bug_id: str, new_status: str, user: dict):
    """Changes a bug's status; stamps Solved_By/Solved_At when it becomes Solved
    (and clears them if it's re-opened)."""
    ws = _ws_or_create(BUGS_SHEET, BUG_COLUMNS)
    values = ws.get_all_values()
    header = values[0]
    id_col = header.index("Bug_ID")
    row = next((i for i, r in enumerate(values[1:], start=2)
                if len(r) > id_col and r[id_col] == bug_id), None)
    if row is None:
        raise ValueError(f"Bug not found: {bug_id}")

    now = now_jordan().strftime("%Y-%m-%d %H:%M:%S")
    solved = new_status == "Solved"
    updates = {
        "Status": new_status,
        "Solved_By": user["name"] if solved else "",
        "Solved_At": now if solved else "",
        "Last_Updated_By": user["name"],
        "Last_Updated_At": now,
    }
    for col, val in updates.items():
        ws.update_cell(row, header.index(col) + 1, val)
    clear_bugs_cache()


@st.cache_data(ttl=300, show_spinner=False)
def load_bug_image(bug_id: str) -> str:
    """The screenshot for one bug as a base64 JPEG string ('' if none)."""
    try:
        ws = _spreadsheet().worksheet(BUG_IMAGES_SHEET)
    except gspread.exceptions.WorksheetNotFound:
        return ""
    parts = [(int(r[1]), r[2]) for r in ws.get_all_values()[1:]
             if len(r) >= 3 and r[0] == bug_id]
    return "".join(p for _, p in sorted(parts))
