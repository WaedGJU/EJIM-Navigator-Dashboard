"""
Admin · Users — reset a team member's PIN, unlock an account after too many
failed logins, activate/deactivate an account, or add a brand-new user.
Everything here writes straight to the Users tab in Google Sheets, using the
SAME email:pin hashing the login uses, so a reset PIN is guaranteed to work.

Only admins can open this page (it's also only added to the navigation for
admins in streamlit_app.py, but we re-check here as a hard stop).
"""

import streamlit as st

from utils.auth import (
    is_admin,
    admin_reset_pin,
    admin_unlock,
    admin_set_active,
    _hash_pin,
)
from utils.sheets import load_users, append_user_row, user_exists

st.title("Admin · Users")

if not is_admin():
    st.error("🔒 This page is for admins only.")
    st.stop()

st.caption(
    "Reset a team member's PIN, unlock an account locked after too many failed "
    "logins, turn an account on/off, or add a new user. All changes are written "
    "to the Users tab in Google Sheets right away."
)


def _pin_problem(pin):
    """Return an error message string if the PIN is invalid, else None."""
    if not pin:
        return "PIN is required."
    if not pin.isdigit():
        return "PIN must be digits only."
    if not (4 <= len(pin) <= 6):
        return "PIN must be 4 to 6 digits."
    return None


def _user_options(df):
    """List of (label, email) for the selectboxes."""
    if df.empty or "Email" not in df.columns:
        return []
    opts = []
    for _, r in df.iterrows():
        name = str(r.get("Name", "")).strip()
        email = str(r.get("Email", "")).strip()
        if email:
            opts.append((f"{name} — {email}" if name else email, email))
    return opts


users = load_users()

tab_reset, tab_add, tab_manage = st.tabs(
    ["🔑 Reset PIN", "➕ Add user", "🔓 Unlock / activate"]
)

# ---------------------------------------------------------------------------
# Reset PIN
# ---------------------------------------------------------------------------
with tab_reset:
    opts = _user_options(users)
    if not opts:
        st.info("No users found in the Users tab.")
    else:
        label_to_email = {lbl: em for lbl, em in opts}
        pick = st.selectbox("User", list(label_to_email.keys()), key="reset_user")
        email = label_to_email[pick]

        with st.form("reset_pin_form"):
            new_pin = st.text_input(
                "New PIN", type="password", max_chars=6,
                help="4–6 digits. Hand this to the user; they log in with it plus their email.",
            )
            confirm = st.text_input("Confirm new PIN", type="password", max_chars=6)
            go = st.form_submit_button("Reset PIN & unlock", use_container_width=True)

        if go:
            p = new_pin.strip()
            problem = _pin_problem(p)
            if problem:
                st.error(problem)
            elif p != confirm.strip():
                st.error("The two PINs don't match.")
            else:
                try:
                    admin_reset_pin(email, p)
                    st.success(
                        f"✅ PIN reset for **{email}**. The account is active and any lock "
                        f"is cleared.\n\nNew PIN to hand to the user: **{p}**"
                    )
                except Exception as e:
                    st.error(f"Couldn't update the sheet: {e}")

# ---------------------------------------------------------------------------
# Add user
# ---------------------------------------------------------------------------
with tab_add:
    with st.form("add_user_form"):
        name = st.text_input("Name *")
        email_new = st.text_input("University email *")
        role = st.selectbox("Role *", ["User", "Admin"])
        pin_new = st.text_input("Initial PIN *", type="password", max_chars=6, help="4–6 digits.")
        add = st.form_submit_button("Add user", use_container_width=True)

    if add:
        n, em, p = name.strip(), email_new.strip(), pin_new.strip()
        errors = []
        if not n:
            errors.append("Name is required.")
        if not em:
            errors.append("Email is required.")
        elif "@" not in em:
            errors.append("That doesn't look like a valid email.")
        problem = _pin_problem(p)
        if problem:
            errors.append(problem)
        if em and not errors:
            try:
                if user_exists(em):
                    errors.append("A user with this email already exists.")
            except Exception as e:
                errors.append(f"Couldn't check existing users: {e}")

        if errors:
            for e in errors:
                st.error(e)
        else:
            try:
                append_user_row({
                    "Name": n,
                    "Email": em,
                    "PIN_Hash": _hash_pin(em, p),
                    "Role": role,
                    "Active": "TRUE",
                })
                load_users.clear()
                st.success(
                    f"✅ Added **{n}** ({em}) as **{role}**.\n\n"
                    f"Their PIN is **{p}** (used together with their email)."
                )
            except Exception as e:
                st.error(f"Couldn't write to the sheet: {e}")

# ---------------------------------------------------------------------------
# Unlock / activate
# ---------------------------------------------------------------------------
with tab_manage:
    if users.empty:
        st.info("No users found.")
    else:
        show_cols = [
            c for c in ["Name", "Email", "Role", "Active", "Failed_Attempts", "Locked_Until"]
            if c in users.columns
        ]
        st.dataframe(users[show_cols], use_container_width=True, hide_index=True)

        opts = _user_options(users)
        label_to_email = {lbl: em for lbl, em in opts}
        pick = st.selectbox("User", list(label_to_email.keys()), key="manage_user")
        email = label_to_email[pick]

        c1, c2, c3 = st.columns(3)
        if c1.button("🔓 Unlock", use_container_width=True,
                     help="Clear failed attempts and any 15-minute lock."):
            try:
                admin_unlock(email)
                st.success(f"Unlocked {email}.")
                st.rerun()
            except Exception as e:
                st.error(f"Couldn't unlock: {e}")
        if c2.button("✅ Activate", use_container_width=True):
            try:
                admin_set_active(email, True)
                st.success(f"Activated {email}.")
                st.rerun()
            except Exception as e:
                st.error(f"Couldn't activate: {e}")
        if c3.button("🚫 Deactivate", use_container_width=True):
            try:
                admin_set_active(email, False)
                st.success(f"Deactivated {email}.")
                st.rerun()
            except Exception as e:
                st.error(f"Couldn't deactivate: {e}")
