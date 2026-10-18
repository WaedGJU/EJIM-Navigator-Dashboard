"""
Step-by-step progress for the MASAR content: the six pathways and the two
sets of chatbot questions. Each step is one activity in the registry; a
bar shows which steps are done and which one the work is on now.

Pathway steps are matched by activity name (the pathway's name in quotes
plus the step's wording), e.g. "Translate 'Study in Germany' pathway content
to Arabic". Chatbot steps are listed by activity No., since their names
don't follow one pattern. Either way, an activity that can't be found shows
as a dashed "missing" step instead of breaking the bar.
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
]

# The chatbot workflow, shared by both question sets:
# (short label for the bar, owner shown in the legend)
CHATBOT_STEPS = [
    ("Prepare English questions", "Karma"),
    ("GIZ review", "GIZ"),
    ("Apply GIZ comments & send to Maryam and Rania", "Karma"),
    ("Translate to Arabic & check links", "Waed"),
    ("Upload Arabic", "Maryam"),
    ("Upload English", "Rania"),
    ("Final check", "Karma"),
]

# (bar title, activity No. of each CHATBOT_STEPS step). None means no activity
# exists for that step yet, so it shows as "missing" until one is added here.
CHATBOT_SETS = [
    ("Chatbot questions: first set", ["201", "238", "239", None, "199", "200", None]),
    ("Chatbot questions: second set", ["202", "243", "244", None, "205", "204", None]),
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


def _no(value) -> str:
    text = str(value if value is not None else "").strip()
    return text[:-2] if text.endswith(".0") else text


def _progress(name: str, steps: list) -> dict:
    """`steps` is [(label, owner, row or None), ...] in workflow order. Returns
      name, total, done
      steps   — [{label, owner, state, activity}]; state is 'done', 'current',
                'todo' or 'missing' (no matching activity in the registry)
      current — index of the first step that isn't done (None when all done)
      overdue — True if the current step's end date has passed
      due     — the current step's end date text ('' if none)
    Rows must come from an enriched frame (needs Bucket / is_overdue)."""
    out, current = [], None
    for label, owner, row in steps:
        if row is None:
            state = "missing"
        elif row["Bucket"] == "Completed":
            state = "done"
        elif current is None:
            state, current = "current", len(out)
        else:
            state = "todo"
        if row is not None:
            owner = str(row.get("Responsible (Name)", "") or "").strip() or owner
        out.append({"label": label, "owner": owner, "state": state, "activity": row})

    cur_row = out[current]["activity"] if current is not None else None
    return {
        "name": name,
        "total": len(out),
        "done": sum(s["state"] == "done" for s in out),
        "steps": out,
        "current": current,
        "overdue": bool(cur_row is not None and cur_row.get("is_overdue")),
        "due": str(cur_row.get("End Date", "") or "") if cur_row is not None else "",
    }


def pathway_progress(df: pd.DataFrame) -> list:
    """One progress dict (see _progress) per pathway, in PATHWAYS order."""
    found = {}
    for _, row in df.iterrows():
        p, s = _pathway_of(row.get("Activity")), _step_of(row.get("Activity"))
        if p is not None and s is not None:
            found[(p, s)] = row
    return [
        _progress(p, [(label, owner, found.get((p, i))) for i, (label, owner, _) in enumerate(STEPS)])
        for p in PATHWAYS
    ]


def chatbot_progress(df: pd.DataFrame) -> list:
    """One progress dict (see _progress) per chatbot question set."""
    by_no = {_no(row.get("No.")): row for _, row in df.iterrows()}
    return [
        _progress(title, [(label, owner, by_no.get(no)) for (label, owner), no in zip(CHATBOT_STEPS, nos)])
        for title, nos in CHATBOT_SETS
    ]
