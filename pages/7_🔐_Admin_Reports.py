import streamlit as st

from utils.auth import is_admin
from utils.sheets import load_login_log, load_edit_log

st.title("Admin Reports")

if not is_admin():
    st.error("🔒 This page is for admins only.")
    st.stop()

tab1, tab2 = st.tabs(["Login history", "Edit history"])

with tab1:
    logins = load_login_log()
    if logins.empty:
        st.info("No logins recorded yet.")
    else:
        c1, c2 = st.columns(2)
        who = c1.multiselect("Filter by email", sorted(logins["Email"].unique()))
        result = c2.multiselect("Result", sorted(logins["Result"].unique()))
        view = logins.copy()
        if who:
            view = view[view["Email"].isin(who)]
        if result:
            view = view[view["Result"].isin(result)]
        st.dataframe(view.sort_values("Timestamp", ascending=False), use_container_width=True, hide_index=True)

        failed = int((logins["Result"] == "failed").sum())
        st.caption(f"{len(logins)} total login attempts · {failed} failed")

with tab2:
    edits = load_edit_log()
    if edits.empty:
        st.info("No edits recorded yet.")
    else:
        c1, c2 = st.columns(2)
        who = c1.multiselect("Filter by name", sorted(edits["Name"].unique()))
        col = c2.multiselect("Column changed", sorted(edits["Column_Changed"].unique()))
        view = edits.copy()
        if who:
            view = view[view["Name"].isin(who)]
        if col:
            view = view[view["Column_Changed"].isin(col)]
        st.dataframe(view.sort_values("Timestamp", ascending=False), use_container_width=True, hide_index=True)
        st.caption(f"{len(edits)} total edits logged")
