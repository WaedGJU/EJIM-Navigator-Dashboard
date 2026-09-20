# Navigator (MASAR) Dashboard

A live Streamlit dashboard for the Labour Mobility Navigator (MASAR) project at CeLAPI, German
Jordanian University. Reads and writes directly to a Google Sheet, so the team's Sunday/Tuesday
meetings can update the project record in real time from any device.

## What's in this project

```
streamlit_app.py                 Router only: page config, styling, login gate, then the top tab bar
pages/0_🏠_Overview.py           "Project Overview" tab — hero (logo + project name), end-date countdown, KPIs, charts
pages/1_📊_Work_Packages.py       Every WP as a progress card; open one to see its activities (admin edits due date)
pages/2_👥_Team.py                Per-person completion; open editing of dates/owner/Done for everyone
pages/3_🚨_Critical_Follow_up.py  Delayed / at risk / no owner / needs confirmation — auto-computed status
pages/4_🤝_External_Partners.py   MODEE / GIZ / MoL activities
pages/5_📋_Full_Registry.py       Filterable table of all activities, CSV export
pages/6_🗓️_Meeting_Prep.py        Meeting countdown, attendance checklist, live agenda editing, PDF minutes export
pages/7_🔐_Admin_Reports.py       Admin-only: login history and edit history
pages/8_➕_Add_Activity.py        Add a brand-new activity to the registry, with validation, from the app
utils/sheets.py                  All Google Sheets reads/writes (incl. appending new activities)
utils/auth.py                    Email + PIN login, lockout, roles
utils/compute.py                 Status bucketing, delayed/at-risk/not-started/unassigned + AutoStatus
utils/style.py                   Brand colors/theme, top-left logo (st.logo), status badges, shared top user bar
utils/constants.py               Project name, end date, internal deadline — shared by the Overview page and the PDF
utils/meeting_pdf.py             Builds the "Minutes of Meeting" PDF (reportlab, no external service)
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

- **Work Packages page**: admins can edit an activity's due date from the WP card; team members see
  the same card but the activity list is read-only. Status is shown as a badge, never edited here.
- **Team page**: open to everyone — any logged-in user can edit any activity's start/end dates,
  owner, or "Done" flag. There's no ownership/admin check here on purpose, because every change is
  written to `Edit_Log` anyway.
- **Critical Follow-up / Meeting Prep**: a team member can only edit activities where they are the
  listed owner (`Responsible (Name)`); admins can edit everything.
- **Add Activity**: open to everyone — anything a logged-in user adds is stamped and logged the same
  way as any other edit. There's no "Responsible (Role)" field here anymore — only the owner (name)
  is picked; that column is simply left blank for activities added through the app.
- **Status, everywhere**: never picked from a dropdown. `utils/compute.py` computes it automatically
  as Completed / Delayed / Not started / In Progress from the Done flag plus the start/end dates —
  see the `AutoStatus` column and `utils/style.py`'s `status_badge_html()`.
- Every login (success or failure) is written to `Login_Log`.
- Every saved edit (and every new activity) is written to `Edit_Log` with who changed what, from
  what, to what, and when.
- After 5 failed login attempts on the same email, that email is locked for 15 minutes.

## Navigation

- There is no left sidebar anywhere in this app anymore. `streamlit_app.py` (the router) is the only
  file that calls `st.set_page_config()`, `inject_base_style()`, and `login_gate()`; once someone is
  logged in, it builds the page list and hands it to `st.navigation(PAGES, position="top")`, which
  draws every page as a horizontal tab across the top of the app (styled as raised, rounded boxes in
  `utils/style.py`, with the active tab picked out in brand orange). "Admin Reports" only appears as a
  tab for admins. Every other page file assumes login/config/styling is already done and just renders
  its own content — don't add `st.set_page_config()` or `login_gate()` calls back into them.
- `utils/style.py`'s `top_user_bar()` (called once, from the router, right under the tabs) replaces
  the old sidebar box: who's logged in, their role, the data-source note, and Log out, all in one
  slim strip at the top of the page.

## Brand styling

- Colors come straight from the MASAR/EJIM logo: navy `#355265`, orange `#f7a831`, teal `#2b8782`.
  `utils/style.py` defines these once as `COLORS` and every page/chart reuses them — no other blue
  or generic Streamlit accent color is used anywhere, including `.streamlit/config.toml`'s theme,
  which recolors Streamlit's own default widget/link accents so nothing reverts to blue.
- The logo is shown pinned to the top-left corner of the app via `st.logo()` (Streamlit ≥ 1.37) on
  every page including the login screen. The Project Overview tab additionally shows a large logo +
  large project-name hero at the top of the page content.

## Meeting Prep and the minutes PDF

- The agenda cards let anyone with edit rights update owner, start/end dates, the Done flag, a team
  note, and the agreed action — every saved change is written straight to Google Sheets and also
  recorded in that browser session's in-memory change log (`st.session_state["meeting_changes"]`).
- The attendance checklist is a fixed roster — Ziad, Feras, Waed, Omar, Heba, Karma, Rania — every
  box starts unchecked, and a "Select all" checkbox flips all seven at once. Anyone not on that list
  (a guest, a stand-in) can still be added: type their name(s), comma-separated, into the text box
  under the roster and they're added as present. External partners like MODEE/GIZ/MoL are never on
  this list.
- "Download meeting minutes (PDF)" (`utils/meeting_pdf.py`) builds a one-off PDF — title, meeting
  date, the attendance checklist, a before/after table of this session's changes, and a footer
  crediting the Evaluation and Monitoring Officer — entirely in English, using `reportlab` with no
  external service calls. The change log is cleared with the "Clear changes log" button and starts
  empty again for the next meeting.

## Notes on the status/flag logic

`utils/compute.py` currently classifies "at risk" as: not completed and due within 5 days
(and not already overdue), and "not started" as: start date still in the future and not completed.
Adjust these rules, or the status-bucket keyword matching, once the team agrees on exact
definitions — it's meant as a working starting point, not a final spec.

## Project timeline

`utils/constants.py` holds `PROJECT_NAME`, `PROJECT_END_DATE` (31 Oct 2026) and `INTERNAL_DEADLINE`
(17 Oct 2026, a 2-week buffer) — both the home-page countdown and the meeting-minutes PDF read from
here, so update this one file if the project's dates ever change.
