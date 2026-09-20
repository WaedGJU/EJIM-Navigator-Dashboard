"""
منطق تصنيف الأنشطة (الحالة/الأعلام) اعتماداً على أعمدة سجل الأنشطة.
هاي نقطة انطلاق منطقية — عدّليها بحرية إذا اتفق الفريق على تعريف مختلف لأي علم.
"""

import re
import pandas as pd

# Jordan wall-clock date, not the server's own clock — Streamlit Community
# Cloud runs its servers on UTC, so "today" from datetime.date.today() can
# land on the wrong calendar day near midnight in Jordan, throwing off every
# overdue/at-risk flag computed here (used across Work Packages, Team,
# Critical Follow-up, and Full Registry).
from utils.constants import now_jordan

DONE_WORDS = {"completed", "done"}
PROGRESS_WORDS = {"in progress", "ongoing"}
NEEDS_CONFIRM_WORDS = {"needs confirmation", "unconfirmed - needs update", "proposed - pending validation"}

PARTNER_PATTERNS = {
    "MODEE": re.compile(r"modee", re.I),
    "GIZ": re.compile(r"giz", re.I),
    "MoL": re.compile(r"\bmol\b", re.I),
}


def _bucket(status: str) -> str:
    s = (status or "").strip().lower()
    if s in DONE_WORDS:
        return "Completed"
    if s in PROGRESS_WORDS:
        return "In Progress"
    if s in NEEDS_CONFIRM_WORDS:
        return "Needs Confirmation"
    if s in {"not started", "pending", "on hold", ""}:
        return "Not Started"
    return "Not Started"


def enrich(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df
    df = df.copy()
    today = pd.Timestamp(now_jordan().date())

    df["Bucket"] = df["Status"].apply(_bucket)

    # The original registry has a manual "Team Update" column (dropdown: pick "Done"
    # once an activity is actually finished). If someone ticked that without also
    # changing the Status text, we still treat the activity as Completed — Team
    # Update always wins over whatever Status currently says.
    if "Team Update" in df.columns:
        done_flag = df["Team Update"].astype(str).str.strip().str.lower() == "done"
        df.loc[done_flag, "Bucket"] = "Completed"
    df["Start_dt"] = pd.to_datetime(df.get("Start Date"), errors="coerce")
    df["End_dt"] = pd.to_datetime(df.get("End Date"), errors="coerce")
    df["is_overdue"] = (df["End_dt"] < today) & (df["Bucket"] != "Completed")
    df["days_overdue"] = (today - df["End_dt"]).dt.days.where(df["is_overdue"], 0).fillna(0).astype(int)
    # Used by Critical Follow-up to compute a status label automatically from
    # dates alone (rather than a manually-picked status): not started yet if
    # the planned start date hasn't arrived and the activity isn't done.
    df["is_not_started"] = (df["Start_dt"] > today) & (df["Bucket"] != "Completed")
    df["is_unassigned"] = df["Responsible (Name)"].isna() | (df["Responsible (Name)"].astype(str).str.strip() == "")
    df["is_needs_confirmation"] = df["Status"].astype(str).str.strip().str.lower().isin(NEEDS_CONFIRM_WORDS)

    # The status shown to the team is never picked manually — it's always
    # computed from the Done flag plus the start/end dates, so it can't drift
    # from reality. Used by Work Packages, Team, and Critical Follow-up.
    def _auto_status(row):
        if row["Bucket"] == "Completed":
            return "Completed"
        if row["is_overdue"]:
            return "Delayed"
        if row["is_not_started"]:
            return "Not started"
        return "In Progress"

    df["AutoStatus"] = df.apply(_auto_status, axis=1)

    def find_partners(row):
        text = " ".join(str(row.get(c, "")) for c in ["Responsible (Role)", "Activity", "Source"])
        return [p for p, pat in PARTNER_PATTERNS.items() if pat.search(text)]

    df["partners"] = df.apply(find_partners, axis=1)
    df["is_external"] = df["partners"].apply(lambda p: len(p) > 0)

    # "في خطر": نشاط لسا ما خلص وتاريخ انتهائه المخطط قبل موعد الاجتماع القادم بأقل من 5 أيام
    # (حد بسيط قابل للتعديل حسب اتفاق الفريق على تعريف "AT RISK")
    soon = today + pd.Timedelta(days=5)
    df["is_atrisk"] = (df["Bucket"] != "Completed") & (df["End_dt"] <= soon) & (~df["is_overdue"])

    return df


def kpis(df: pd.DataFrame) -> dict:
    total = len(df)
    completed = int((df["Bucket"] == "Completed").sum())
    return {
        "total": total,
        "completed": completed,
        "completed_pct": round(100 * completed / total, 1) if total else 0,
        "in_progress": int((df["Bucket"] == "In Progress").sum()),
        "not_started": int((df["Bucket"] == "Not Started").sum()),
        "needs_confirmation": int(df["is_needs_confirmation"].sum()),
        "overdue": int(df["is_overdue"].sum()),
        "at_risk": int(df["is_atrisk"].sum()),
        "unassigned": int(df["is_unassigned"].sum()),
    }
