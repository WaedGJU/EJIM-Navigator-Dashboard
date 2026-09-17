"""
All Google Sheets access goes through this file only — reads, writes, and logging.
Uses a Service Account ("robot" credentials) stored in st.secrets, not any
individual team member's Google account.
"""

import datetime
import gspread
import pandas as pd
import streamlit as st
from google.oauth2.service_account import Credentials

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

    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    if "Last_Edited_By" in header:
        ws.update_cell(row_number, header.index("Last_Edited_By") + 1, user["name"])
    if "Last_Edited_At" in header:
        ws.update_cell(row_number, header.index("Last_Edited_At") + 1, now)

    append_edit_log(user, row_number, column_name, old_value, new_value)
    clear_activity_cache()


class ConflictError(Exception):
    """Raised when two people try to edit the same row at roughly the same moment."""
    pass


def append_edit_log(user: dict, row_number: int, column_name: str, old_value, new_value):
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    _ws(EDIT_LOG_SHEET).append_row(
        [now, user["email"], user["name"], row_number, column_name, str(old_value), str(new_value)],
        value_input_option="USER_ENTERED",
    )


def append_login_log(email: str, name: str, result: str):
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    _ws(LOGIN_LOG_SHEET).append_row([now, email, name, result], value_input_option="USER_ENTERED")


@st.cache_data(ttl=15, show_spinner=False)
def load_login_log() -> pd.DataFrame:
    return pd.DataFrame(_ws(LOGIN_LOG_SHEET).get_all_records())


@st.cache_data(ttl=15, show_spinner=False)
def load_edit_log() -> pd.DataFrame:
    return pd.DataFrame(_ws(EDIT_LOG_SHEET).get_all_records())
