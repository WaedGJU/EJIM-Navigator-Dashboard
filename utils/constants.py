"""Small shared project-level facts — kept in one place so the home-page
hero and the meeting-minutes PDF always agree on the project's name and
timeline."""

import datetime
from zoneinfo import ZoneInfo

PROJECT_NAME = "Labour Mobility Navigator (MASAR)"
PROJECT_END_DATE = datetime.date(2026, 10, 31)   # official project window: 1 Jun – 31 Oct 2026
INTERNAL_DEADLINE = datetime.date(2026, 10, 17)  # 2-week buffer before the project end date

# Where the team actually is — used to stamp reports with Jordan's own wall
# clock time regardless of what timezone the app happens to be hosted in
# (Streamlit Community Cloud's servers run on UTC, not Jordan time).
JORDAN_TZ = ZoneInfo("Asia/Amman")


def now_jordan() -> datetime.datetime:
    """Current date & time in Jordan (Asia/Amman) — use this instead of
    datetime.datetime.now() for anything stamped on a report a person will
    read, so the "generated at" time always matches their own clock."""
    return datetime.datetime.now(JORDAN_TZ)
