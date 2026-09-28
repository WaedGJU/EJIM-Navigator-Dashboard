"""Bugs Log — anyone on the team can report a problem they hit in the app,
attach a screenshot, and mark it Solved once it's fixed. Everything is saved
to the Bugs_Log / Bug_Images tabs of the same Google Sheet (see utils/sheets.py)."""

import base64
import io

import streamlit as st
from PIL import Image

from utils.auth import current_user
from utils.sheets import load_bugs, append_bug, update_bug_status, load_bug_image

STATUSES = ["Open", "Solved"]  # "Open" = the problem still exists
STATUS_ICON = {"Open": "🔴", "Solved": "🟢"}
PAGES = [
    "Project Overview", "Work Packages", "Team", "Critical Follow-up", "External Partners",
    "Full Registry", "Meeting Prep", "Add Activity", "Admin Reports", "Admin · Users",
    "Login", "Other",
]
MAX_B64_CHARS = 400_000  # ~300 KB image once compressed — keeps the sheet light


def compress_screenshot(uploaded) -> str:
    """Shrinks the upload to a JPEG small enough to live inside the Google Sheet
    and returns it as base64 text."""
    img = Image.open(uploaded)
    img = img.convert("RGB")
    max_side, quality = 1600, 80
    while True:
        work = img.copy()
        work.thumbnail((max_side, max_side))
        buf = io.BytesIO()
        work.save(buf, format="JPEG", quality=quality, optimize=True)
        b64 = base64.b64encode(buf.getvalue()).decode("ascii")
        if len(b64) <= MAX_B64_CHARS or max_side <= 500:
            return b64
        max_side = int(max_side * 0.8)
        quality = max(50, quality - 8)


st.title("Bugs Log")
st.caption("Hit a problem in the app? Log it here so it gets fixed. It's saved straight to the "
           "Google Sheet (Bugs_Log tab). Set the status to **Solved** once it's fixed.")

user = current_user()

# --------------------------------------------------------------------------- report
with st.expander("➕ Report a new bug", expanded=False):
    with st.form("new_bug_form", clear_on_submit=True):
        page = st.selectbox("Where did it happen? *", PAGES)
        description = st.text_area(
            "Describe the problem *", height=120,
            placeholder="What did you do, what did you expect, and what happened instead?",
        )
        shot = st.file_uploader("Screenshot of the error (optional)", type=["png", "jpg", "jpeg", "webp"])
        submitted = st.form_submit_button("🐞 Submit bug", use_container_width=True)

    if submitted:
        if not description.strip():
            st.error("Please describe the problem.")
        else:
            try:
                image_b64 = compress_screenshot(shot) if shot is not None else ""
            except Exception:
                image_b64 = ""
                st.warning("The screenshot couldn't be read, so the bug was saved without it.")
            try:
                with st.spinner("Saving…"):
                    bug_id = append_bug(page, description.strip(), user, image_b64)
                st.success(f"Logged as **{bug_id}** ✅ Thank you!")
            except Exception as e:
                st.error(f"Couldn't write to Google Sheets: {e}")

# --------------------------------------------------------------------------- list
df = load_bugs()
if df.empty:
    st.info("No bugs reported yet 🎉")
    st.stop()

df["Status"] = df["Status"].replace("", "Open")
open_n = int((df["Status"] != "Solved").sum())
solved_n = int((df["Status"] == "Solved").sum())
k1, k2, k3 = st.columns(3)
k1.metric("Total reported", len(df))
k2.metric("🔴 Still open", open_n)
k3.metric("🟢 Solved", solved_n)

c1, c2, c3 = st.columns([1, 1, 2])
f_status = c1.multiselect("Status", STATUSES, default=["Open"])
f_page = c2.multiselect("Page", sorted(df["Page"].astype(str).unique()))
search = c3.text_input("Search description / reporter")

view = df.copy()
if f_status:
    view = view[view["Status"].isin(f_status)]
if f_page:
    view = view[view["Page"].astype(str).isin(f_page)]
if search:
    s = search.lower()
    view = view[view.apply(lambda r: s in f"{r['Description']} {r['Reported_By']}".lower(), axis=1)]

view = view.sort_values("Reported_At", ascending=False)
st.caption(f"{len(view)} of {len(df)} bugs")

for _, bug in view.iterrows():
    bug_id = str(bug["Bug_ID"])
    status = bug["Status"] if bug["Status"] in STATUSES else "Open"
    first_line = str(bug["Description"]).splitlines()[0][:90] if str(bug["Description"]) else ""
    label = f"{STATUS_ICON[status]} {bug_id} · {bug['Page']} · {first_line}"
    with st.expander(label):
        st.markdown(f"**Reported by** {bug['Reported_By']} · {bug['Reported_At']}")
        st.write(bug["Description"])
        if status == "Solved" and str(bug.get("Solved_By", "")):
            st.caption(f"Solved by {bug['Solved_By']} · {bug['Solved_At']}")

        if str(bug.get("Has_Screenshot", "")) == "Yes":
            b64 = load_bug_image(bug_id)
            if b64:
                st.image(base64.b64decode(b64), caption="Screenshot", use_container_width=True)
            else:
                st.caption("Screenshot not found.")

        s1, s2 = st.columns([2, 1])
        new_status = s1.selectbox("Status", STATUSES, index=STATUSES.index(status),
                                  key=f"status_{bug_id}")
        s2.write("")
        if s2.button("💾 Save", key=f"save_{bug_id}", disabled=new_status == status,
                     use_container_width=True):
            try:
                update_bug_status(bug_id, new_status, user)
                st.success(f"{bug_id} → {new_status}")
                st.rerun()
            except Exception as e:
                st.error(f"Couldn't update Google Sheets: {e}")

st.download_button(
    "⬇ Export bugs as CSV",
    view.to_csv(index=False).encode("utf-8-sig"),
    file_name="navigator_bugs_log.csv",
)
