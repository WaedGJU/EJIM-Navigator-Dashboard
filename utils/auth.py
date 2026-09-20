"""
Login by email + PIN, and role check (Admin / User).
No team member needs a Google account — credentials are checked only against
the Users tab in the spreadsheet.
"""

import hashlib
import time
import streamlit as st
from utils.sheets import load_users, append_login_log

MAX_ATTEMPTS = 5
LOCKOUT_SECONDS = 15 * 60  # 15 minutes


def _hash_pin(email: str, pin: str) -> str:
    return hashlib.sha256(f"{email.strip().lower()}:{pin}".encode()).hexdigest()


def _is_locked_out(email: str) -> int:
    """Returns seconds remaining on the lockout, or 0 if not locked."""
    lock = st.session_state.get("lockouts", {}).get(email.strip().lower())
    if not lock:
        return 0
    remaining = LOCKOUT_SECONDS - (time.time() - lock)
    return max(0, int(remaining))


def _register_failed_attempt(email: str):
    key = email.strip().lower()
    attempts = st.session_state.setdefault("failed_attempts", {})
    attempts[key] = attempts.get(key, 0) + 1
    if attempts[key] >= MAX_ATTEMPTS:
        st.session_state.setdefault("lockouts", {})[key] = time.time()
        attempts[key] = 0


def _clear_failed_attempts(email: str):
    key = email.strip().lower()
    st.session_state.get("failed_attempts", {}).pop(key, None)
    st.session_state.get("lockouts", {}).pop(key, None)


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

    # The brand logo itself is pinned to the top-left corner by st.logo()
    # (called from inject_base_style(), which every page runs before this
    # gate) — this screen only needs the heading, not a second logo.
    st.markdown(
        "<h3 style='text-align:center; margin-top:50px;'>Project Dashboard — Log in</h3>",
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
            remaining = _is_locked_out(email_clean)
            if remaining:
                st.error(f"⛔ This account is temporarily locked after too many failed attempts. Try again in {remaining // 60 + 1} min.")
            else:
                users = load_users()
                if users.empty:
                    st.error("Could not reach the user list — check the Google Sheets connection.")
                else:
                    users["Email_norm"] = users["Email"].astype(str).str.strip().str.lower()
                    match = users[users["Email_norm"] == email_clean]

                    if match.empty or not pin:
                        _register_failed_attempt(email_clean)
                        append_login_log(email, "-", "failed")
                        st.error("Incorrect email or PIN.")
                    else:
                        row = match.iloc[0]
                        expected_hash = str(row["PIN_Hash"]).strip()
                        given_hash = _hash_pin(email_clean, pin.strip())

                        if given_hash != expected_hash or str(row.get("Active", "TRUE")).upper() != "TRUE":
                            _register_failed_attempt(email_clean)
                            append_login_log(email, row["Name"], "failed")
                            st.error("Incorrect email or PIN.")
                        else:
                            _clear_failed_attempts(email_clean)
                            st.session_state["user"] = {
                                "name": row["Name"],
                                "email": email_clean,
                                "role": row["Role"],
                            }
                            append_login_log(email_clean, row["Name"], "success")
                            st.rerun()

    # Critical: always stop here so nothing below login_gate() in the calling
    # page renders unless login just succeeded above (st.rerun() already
    # restarted the script in that case, so this line is never reached then).
    st.stop()
