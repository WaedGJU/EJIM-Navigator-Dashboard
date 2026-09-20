"""
Entry point and router. This is the ONLY file that calls st.set_page_config(),
inject_base_style() and login_gate() — every other page file assumes that's
already done and just renders its own content.

Navigation is a horizontal top tab bar (st.navigation(..., position="top")),
drawn just below the fixed brand bar (logo + project name) that
inject_base_style() adds at the very top of the app — see utils/style.py.
There is no st.sidebar anywhere in this app anymore.
"""

import streamlit as st

from utils.auth import login_gate, is_admin
from utils.style import inject_base_style, top_user_bar

st.set_page_config(page_title="Project Overview — Navigator (MASAR)", page_icon="🧭", layout="wide")
inject_base_style()
login_gate()  # stops here if nobody is logged in

PAGES = [
    st.Page("pages/0_🏠_Overview.py", title="Project Overview", icon="🏠", default=True),
    st.Page("pages/1_📊_Work_Packages.py", title="Work Packages", icon="📊"),
    st.Page("pages/2_👥_Team.py", title="Team", icon="👥"),
    st.Page("pages/3_🚨_Critical_Follow_up.py", title="Critical Follow-up", icon="🚨"),
    st.Page("pages/4_🤝_External_Partners.py", title="External Partners", icon="🤝"),
    st.Page("pages/5_📋_Full_Registry.py", title="Full Registry", icon="📋"),
    st.Page("pages/6_🗓️_Meeting_Prep.py", title="Meeting Prep", icon="🗓️"),
    st.Page("pages/8_➕_Add_Activity.py", title="Add Activity", icon="➕"),
]
if is_admin():
    PAGES.append(st.Page("pages/7_🔐_Admin_Reports.py", title="Admin Reports", icon="🔐"))

nav = st.navigation(PAGES, position="top")
top_user_bar()
nav.run()
