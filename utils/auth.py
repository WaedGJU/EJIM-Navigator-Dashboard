"""
Login by email + PIN, and role check (Admin / User).
No team member needs a Google account — credentials are checked only against
the Users tab in the spreadsheet.

Lockout state (failed-attempt count + a temporary lock after too many) is
stored in the Users tab itself — columns Failed_Attempts and Locked_Until —
so it is shared across sessions and devices, and an admin can clear it from
the Admin · Users page. (It used to live only in st.session_state, which
meant a lock existed only inside one person's own browser session, so no
admin could ever clear it for someone else.) Those two columns are created
automatically the first time they're written, so nothing has to be added to
the sheet by hand.

A session-only fallback still rate-limits attempts against emails that aren't
in the Users tab at all, so probing random addresses can't be used to hammer
the login without us writing junk rows to the sheet.
"""

import datetime
import hashlib
import time

import pandas as pd
import streamlit as st

from utils.sheets import load_users, append_login_log, update_user_cell
from utils.constants import PROJECT_NAME, now_jordan

MAX_ATTEMPTS = 5
LOCKOUT_SECONDS = 15 * 60  # 15 minutes

FAILED_COL = "Failed_Attempts"
LOCKED_COL = "Locked_Until"
_LOCK_FMT = "%Y-%m-%d %H:%M:%S"


def _hash_pin(email: str, pin: str) -> str:
    return hashlib.sha256(f"{email.strip().lower()}:{pin}".encode()).hexdigest()


def _now_naive() -> datetime.datetime:
    """Jordan wall-clock time without tzinfo, to match how Locked_Until is
    stored in the sheet (plain 'YYYY-MM-DD HH:MM:SS' strings)."""
    return now_jordan().replace(tzinfo=None, microsecond=0)


# ---------------------------------------------------------------------------
# Sheet-backed lockout (for users that exist in the Users tab)
# ---------------------------------------------------------------------------

def _as_int(value) -> int:
    n = pd.to_numeric(value, errors="coerce")
    return 0 if pd.isna(n) else int(n)


def _lock_remaining_from_row(row) -> int:
    """Seconds left on a sheet-stored lock for this user row, else 0. Safe when
    the Locked_Until column doesn't exist yet (returns 0)."""
    raw = row.get(LOCKED_COL, "") if hasattr(row, "get") else ""
    if raw is None or str(raw).strip() == "":
        return 0
    try:
        locked_until = datetime.datetime.strptime(str(raw).strip(), _LOCK_FMT)
    except ValueError:
        return 0
    remaining = (locked_until - _now_naive()).total_seconds()
    return max(0, int(remaining))


def _register_failed_sheet(email: str, row):
    """Bump this user's failed-attempt count in the sheet; once it hits the
    limit, stamp a 15-minute lock and reset the counter."""
    attempts = _as_int(row.get(FAILED_COL, 0)) + 1
    if attempts >= MAX_ATTEMPTS:
        locked_until = (_now_naive() + datetime.timedelta(seconds=LOCKOUT_SECONDS)).strftime(_LOCK_FMT)
        update_user_cell(email, LOCKED_COL, locked_until)
        update_user_cell(email, FAILED_COL, 0)
    else:
        update_user_cell(email, FAILED_COL, attempts)


def _clear_lock_sheet(email: str):
    """Reset a user's failed-attempt count and remove any temporary lock."""
    update_user_cell(email, FAILED_COL, 0)
    update_user_cell(email, LOCKED_COL, "")


# ---------------------------------------------------------------------------
# Session-only fallback (for emails that aren't in the Users tab)
# ---------------------------------------------------------------------------

def _is_locked_out_session(email: str) -> int:
    lock = st.session_state.get("lockouts", {}).get(email.strip().lower())
    if not lock:
        return 0
    remaining = LOCKOUT_SECONDS - (time.time() - lock)
    return max(0, int(remaining))


def _register_failed_session(email: str):
    key = email.strip().lower()
    attempts = st.session_state.setdefault("failed_attempts", {})
    attempts[key] = attempts.get(key, 0) + 1
    if attempts[key] >= MAX_ATTEMPTS:
        st.session_state.setdefault("lockouts", {})[key] = time.time()
        attempts[key] = 0


# ---------------------------------------------------------------------------
# Admin actions — called from the Admin · Users page
# ---------------------------------------------------------------------------

def admin_reset_pin(email: str, new_pin: str):
    """Set a user's PIN (stored as the correct email:pin hash), make sure the
    account is active, and clear any lockout. Raises on failure."""
    email = str(email).strip()
    update_user_cell(email, "PIN_Hash", _hash_pin(email, str(new_pin).strip()))
    update_user_cell(email, "Active", "TRUE")
    _clear_lock_sheet(email)


def admin_unlock(email: str):
    """Clear a user's failed-attempt count and any temporary lock, without
    touching their PIN."""
    _clear_lock_sheet(str(email).strip())


def admin_set_active(email: str, active: bool):
    """Enable or disable an account (Active = TRUE / FALSE)."""
    update_user_cell(str(email).strip(), "Active", "TRUE" if active else "FALSE")


# ---------------------------------------------------------------------------
# Session helpers
# ---------------------------------------------------------------------------

def current_user():
    return st.session_state.get("user")


def is_admin() -> bool:
    user = current_user()
    return bool(user and user.get("role", "").lower() == "admin")


def logout():
    st.session_state.pop("user", None)
    st.rerun()


def login_gate():
    """Blocks the page until someone is logged in, and renders the login form."""
    if current_user():
        return

    # Local import to dodge a circular import — utils.style itself imports
    # from this module (current_user/logout/is_admin), so this can't be a
    # module-level import here; by the time login_gate() actually runs both
    # modules are already fully loaded.
    from utils.style import MASAR_LOGO_PATH, _b64

    # Rendered as a plain <img> inside a text-align:center div rather than
    # st.image() inside a column — st.image() left-aligns itself within
    # whatever column holds it, so with a fixed width it sat off-center,
    # not lined up above the form/box below it. This centers it exactly the
    # same way the heading/subtext right below it are already centered.
    st.markdown(
        f"""
        <div style="text-align:center;">
            <img src="data:image/png;base64,{_b64(MASAR_LOGO_PATH)}" style="width:110px;">
        </div>
        <h3 style='text-align:center; margin-top:10px;'>{PROJECT_NAME}</h3>
        <p style='text-align:center; color:#4D4D4D; margin-top:-6px;'>Log in to continue</p>
        """,
        unsafe_allow_html=True,
    )
    col1, col2, col3 = st.columns([1, 1.2, 1])
    with col2:
        with st.form("login_form"):
            email = st.text_input("University email")
            pin = st.text_input("PIN code", type="password", max_chars=6)
            submitted = st.form_submit_button("Log in", use_container_width=True)

        if submitted:
            email_clean = email.strip().lower()
            users = load_users()
            if users.empty:
                st.error("Could not reach the user list — check the Google Sheets connection.")
            else:
                users["Email_norm"] = users["Email"].astype(str).str.strip().str.lower()
                match = users[users["Email_norm"] == email_clean]

                # Lockout: sheet-backed for known users, session-only otherwise.
                if not match.empty:
                    remaining = _lock_remaining_from_row(match.iloc[0])
                else:
                    remaining = _is_locked_out_session(email_clean)

                if remaining:
                    st.error(
                        "⛔ This account is temporarily locked after too many failed "
                        f"attempts. Try again in {remaining // 60 + 1} min."
                    )
                elif match.empty or not pin:
                    if match.empty:
                        _register_failed_session(email_clean)
                    append_login_log(email, "-", "failed")
                    st.error("Incorrect email or PIN.")
                else:
                    row = match.iloc[0]
                    expected_hash = str(row["PIN_Hash"]).strip()
                    given_hash = _hash_pin(email_clean, pin.strip())

                    if given_hash != expected_hash or str(row.get("Active", "TRUE")).upper() != "TRUE":
                        _register_failed_sheet(email_clean, row)
                        append_login_log(email, row["Name"], "failed")
                        st.error("Incorrect email or PIN.")
                    else:
                        _clear_lock_sheet(email_clean)
                        st.session_state["user"] = {
                            "name": row["Name"],
                            "email": email_clean,
                            "role": row["Role"],
                        }
                        append_login_log(email_clean, row["Name"], "success")
                        st.rerun()

    st.markdown(
        "<p style='text-align:center; color:#8a8f96; font-size:12.5px; margin-top:40px;'>"
        "Designed by Eng. Waed Alswaeer — waed.alswaer@gju.edu.jo</p>",
        unsafe_allow_html=True,
    )

    # Critical: always stop here so nothing below login_gate() in the calling
    # page renders unless login just succeeded above (st.rerun() already
    # restarted the script in that case, so this line is never reached then).
    st.stop()
