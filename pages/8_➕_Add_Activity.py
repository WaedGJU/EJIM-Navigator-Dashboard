import datetime
import streamlit as st

from utils.auth import current_user
from utils.sheets import load_activities, load_users, append_activity_row, get_next_activity_number
from utils.compute import enrich

st.title("Add Activity")
st.caption("For anything new that comes up and isn't in the registry yet. This writes a brand-new row "
           "straight to the Activity_Registry Google Sheet — every field below is checked before it's sent.")

user = current_user()
df = enrich(load_activities())

users_df = load_users()
team_names = [n for n in users_df["Name"].dropna().astype(str).str.strip().tolist() if n] \
    if not users_df.empty and "Name" in users_df.columns else []
if not df.empty:
    for p in sorted(df["Responsible (Name)"].dropna().astype(str).str.strip().unique()):
        if p and p not in team_names:
            team_names.append(p)

existing_wps = sorted(df["Original WP"].dropna().astype(str).str.strip().unique()) if not df.empty else []

OTHER_WP = "➕ Other — type a new work package"

next_no = get_next_activity_number() if not df.empty else 1
st.info(f"This will be activity **No. {next_no}**.")

# The work-package choice needs to react immediately (to reveal the "type a
# new WP" box), so it lives outside the form — Streamlit forms only rerun on
# submit, and everything else below doesn't need that kind of live reveal.
st.subheader("Work package")
wp_choice = st.selectbox("Work package *", existing_wps + [OTHER_WP], key="add_wp_choice")
if wp_choice == OTHER_WP:
    wp_final = st.text_input("New work package name *", key="add_wp_custom",
                              placeholder="e.g. WP10 Something New")
else:
    wp_final = wp_choice

with st.form("add_activity_form"):
    st.subheader("Activity details")
    activity_name = st.text_input("Activity name *")
    description = st.text_area("Description / Indicator", height=80)

    owner = st.selectbox("Responsible (Name) — Owner *", team_names if team_names else ["—"])

    c3, c4 = st.columns(2)
    start_date = c3.date_input("Start date *", value=datetime.date.today())
    end_date = c4.date_input("End date *", value=datetime.date.today() + datetime.timedelta(days=7))

    source = st.text_input("Source", value="Team-reported (added via app)")

    st.caption("Status isn't set here — it starts as \"Not started\" and, from then on, the app computes "
               "it automatically from the Done flag and these dates, on every page.")

    submitted = st.form_submit_button("➕ Add activity", use_container_width=True)

if submitted:
    errors = []
    activity_name_clean = activity_name.strip()
    wp_clean = (wp_final or "").strip()

    if not activity_name_clean:
        errors.append("Activity name is required.")
    if not wp_clean:
        errors.append("Work package is required.")
    if not team_names or owner == "—":
        errors.append("Owner is required — no team members were found in the Users tab.")
    if end_date < start_date:
        errors.append("End date can't be before the start date.")
    if not df.empty and activity_name_clean and wp_clean:
        dup = df[
            (df["Activity"].astype(str).str.strip().str.lower() == activity_name_clean.lower())
            & (df["Original WP"].astype(str).str.strip().str.lower() == wp_clean.lower())
        ]
        if not dup.empty:
            errors.append("An activity with this exact name already exists in this work package.")

    if errors:
        for e in errors:
            st.error(e)
    else:
        values = {
            "No.": next_no,
            "Original WP": wp_clean,
            "Activity": activity_name_clean,
            "Description / Indicator": description.strip(),
            "Responsible (Name)": owner,
            "Status": "Not started",
            "Start Date": start_date.isoformat(),
            "End Date": end_date.isoformat(),
            "Source": source.strip() or "Team-reported (added via app)",
        }
        try:
            append_activity_row(values, user)
            st.success(f"Added activity No. {next_no}: {activity_name_clean} ✅")
            st.rerun()
        except Exception as e:
            st.error(f"Couldn't write to Google Sheets: {e}")
