# Navigator (MASAR) Dashboard

A live Streamlit dashboard for the Labour Mobility Navigator (MASAR) project at CeLAPI, German
Jordanian University. Reads and writes directly to a Google Sheet, so the team's Sunday/Tuesday
meetings can update the project record in real time from any device.

## What's in this project

```
streamlit_app.py                 Home page — KPIs, work-package chart, status donut, team chart
pages/1_📊_Work_Packages.py       Every WP as a progress card; open one to see/edit its activities (admin)
pages/2_👥_Team.py                Per-person completion; open editing of dates/status/owner for everyone
pages/3_🚨_Critical_Follow_up.py  Delayed / at risk / no owner / needs confirmation — auto-computed status
pages/4_🤝_External_Partners.py   MODEE / GIZ / MoL activities
pages/5_📋_Full_Registry.py       Filterable table of all 187 activities, CSV export
pages/6_🗓️_Meeting_Prep.py        Sunday/Tuesday countdown + meeting agenda + editable follow-up
pages/7_🔐_Admin_Reports.py       Admin-only: login history and edit history
utils/sheets.py                  All Google Sheets reads/writes
utils/auth.py                    Email + PIN login, lockout, roles
utils/compute.py                 Status bucketing, delayed/at-risk/not-started/unassigned logic
utils/style.py                   Brand colors/theme, top-left logo (st.logo), shared sidebar
.streamlit/config.toml           Brand theme (navy/orange/teal) so no default Streamlit blue shows
data/Navigator_GoogleSheet_Template.xlsx   Import this into a new Google Sheet to get started
data/temporary_pins.txt          Auto-generated PINs — distribute privately, then delete this file
```

## One-time setup

### 1. Create the Google Sheet
Create a new Google Sheet, then **File → Import → Upload** and pick
`data/Navigator_GoogleSheet_Template.xlsx` (choose "Replace spreadsheet" or import as new sheets —
either way you need the four tabs: `Activity_Registry`, `Users`, `Login_Log`, `Edit_Log`).

### 2. Create a Google Cloud service account
1. In the [Google Cloud Console](https://console.cloud.google.com/), create a project (or reuse one).
2. Enable the **Google Sheets API** and **Google Drive API**.
3. Create a **Service Account**, then create a JSON key for it and download it.
4. Open the Google Sheet, click **Share**, and give the service account's email
   (looks like `xxx@xxx.iam.gserviceaccount.com`, found in the JSON key) **Editor** access.

### 3. Configure secrets
Copy `.streamlit/secrets.toml.example` to `.streamlit/secrets.toml` for local testing (this file
is gitignored — never commit it), fill in the `spreadsheet_id` (from the sheet's URL) and the
service account JSON fields. On Streamlit Community Cloud, paste the same content into
**App settings → Secrets** instead.

### 4. Distribute PINs
Open `data/temporary_pins.txt`, send each person their own PIN privately (not in a group chat),
then delete the file. Everyone logs in with their university email + their PIN — no Google
account needed.

### 5. Run locally (optional, before deploying)
```bash
pip install -r requirements.txt
streamlit run streamlit_app.py
```

### 6. Deploy
Push this folder to a GitHub repository, then on [share.streamlit.io](https://share.streamlit.io)
click **New app**, pick the repo and `streamlit_app.py`, and add the secrets from step 3.

## How permissions work

- **Work Packages page**: admins can edit an activity's status and due date from the WP card; team
  members see the same card but the activity list is read-only.
- **Team page**: open to everyone — any logged-in user can edit any activity's start/end dates,
  status, "Done" flag, or reassign its owner. There's no ownership/admin check here on purpose,
  because every change is written to `Edit_Log` anyway.
- **Critical Follow-up / Meeting Prep**: a team member can only edit activities where they are the
  listed owner (`Responsible (Name)`); admins can edit everything. Status on Critical Follow-up is
  never picked manually — it's computed from the Done flag plus the start/end dates.
- Every login (success or failure) is written to `Login_Log`.
- Every saved edit is written to `Edit_Log` with who changed what, from what, to what, and when.
- After 5 failed login attempts on the same email, that email is locked for 15 minutes.

## Brand styling

- Colors come straight from the MASAR/EJIM logo: navy `#355265`, orange `#f7a831`, teal `#2b8782`.
  `utils/style.py` defines these once as `COLORS` and every page/chart reuses them — no other blue
  or generic Streamlit accent color is used anywhere, including `.streamlit/config.toml`'s theme,
  which recolors Streamlit's own default widget/link accents so nothing reverts to blue.
- The logo is shown once, pinned to the top-left corner of the app via `st.logo()` (Streamlit
  ≥ 1.37), on every page including the login screen — it's never repeated as a big card elsewhere.

## Notes on the status/flag logic

`utils/compute.py` currently classifies "at risk" as: not completed and due within 5 days
(and not already overdue), and "not started" as: start date still in the future and not completed.
Adjust these rules, or the status-bucket keyword matching, once the team agrees on exact
definitions — it's meant as a working starting point, not a final spec.
