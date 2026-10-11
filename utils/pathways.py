"""
Where each of the six MASAR pathways stands in its 9-step content workflow.

Every pathway goes through the same steps, and each step is one activity in
the registry whose name holds the pathway's name in quotes, e.g.
"Translate 'Study in Germany' pathway content to Arabic". Activities are
matched to a pathway + step by those names, so nothing extra has to be
filled in on the sheet. An activity that's renamed so it no longer matches
simply drops out of the bar (the step then shows as missing).
"""

import re

import pandas as pd

PATHWAYS = [
    "Work and Vocational Training",
    "Study in Germany",
    "Qualification Recognition",
    "Visa Preparation",
    "Language Improvement",
    "Job Market Readiness",
]

# (short label for the bar, owner shown in the legend, pattern on the activity name)
STEPS = [
    ("Prepare English content", "Karma", re.compile(r"^Prepare '.+' pathway content in English", re.I)),
    ("Upload English", "Rania", re.compile(r"^Upload '.+' pathway content .*\(English\)", re.I)),
    ("Translate to Arabic", "Waed", re.compile(r"^Translate '.+' pathway content", re.I)),
    ("Upload Arabic", "Maryam", re.compile(r"^Upload '.+' pathway content .*\(Arabic\)", re.I)),
    ("Initial review with GIZ", "Karma", re.compile(r"^Initial review of '.+' pathway", re.I)),
    ("Findings to Maryam & Rania", "Karma", re.compile(r"^Deliver GIZ initial-review findings on '.+'", re.I)),
    ("Apply comments on CMS", "Maryam / Rania", re.compile(r"^Apply GIZ initial-review comments on '.+'", re.I)),
    ("Final review with GIZ", "Karma", re.compile(r"^Final review of '.+' pathway", re.I)),
    ("Final Excel to QA", "Karma", re.compile(r"^Hand over final Excel content file of '.+'", re.I)),
]

_QUOTED = re.compile(r"'([^']+)'")


def _pathway_of(activity: str):
    m = _QUOTED.search(activity or "")
    if not m:
        return None
    name = m.group(1).strip().lower()
    return next((p for p in PATHWAYS if p.lower() == name), None)


def _step_of(activity: str):
    return next((i for i, (_, _, rx) in enumerate(STEPS) if rx.search(activity or "")), None)


def pathway_progress(df: pd.DataFrame) -> list:
    """One dict per pathway, in PATHWAYS order:
      steps   — list of 9 dicts {label, owner, state, activity}; state is
                'done', 'current', 'todo' or 'missing' (no matching activity)
      current — index of the first step that isn't done (None when all done)
      done    — number of steps completed
      overdue — True if the current step's end date has passed
      due     — the current step's end date text ('' if none)
    `df` must already be enriched (needs Bucket / is_overdue)."""
    found = {}
    for _, row in df.iterrows():
        p, s = _pathway_of(row.get("Activity")), _step_of(row.get("Activity"))
        if p is not None and s is not None:
            found[(p, s)] = row

    result = []
    for p in PATHWAYS:
        steps, current = [], None
        for i, (label, owner, _) in enumerate(STEPS):
            row = found.get((p, i))
            if row is None:
                state = "missing"
            elif row["Bucket"] == "Completed":
                state = "done"
            elif current is None:
                state, current = "current", i
            else:
                state = "todo"
            steps.append({"label": label, "owner": owner, "state": state, "activity": row})

        cur_row = steps[current]["activity"] if current is not None else None
        result.append({
            "pathway": p,
            "steps": steps,
            "current": current,
            "done": sum(s["state"] == "done" for s in steps),
            "overdue": bool(cur_row is not None and cur_row.get("is_overdue")),
            "due": str(cur_row.get("End Date", "") or "") if cur_row is not None else "",
        })
    return result
