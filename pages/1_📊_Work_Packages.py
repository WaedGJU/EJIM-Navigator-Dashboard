from html import escape

import streamlit as st
import plotly.express as px

from utils.style import COLORS, status_badge_html
from utils.sheets import load_activities
from utils.compute import enrich
from utils.activity_editor import activity_editor, activity_key, can_edit, wp_options, team_options
from utils.pathways import STEPS, pathway_progress, chatbot_progress

st.title("Work Packages (WP1–WP9)")
st.caption("Every work package as a progress card — open one to see its activities. "
           "Admins can edit or delete any activity right here, and everyone else their own (work package, "
           "owner, dates, Done); it's saved to Google Sheets instantly. "
           "Status is never picked manually — it's computed automatically from the Done flag and dates.")

df = enrich(load_activities())
if df.empty:
    st.stop()

wps = wp_options(df)
team_names = team_options(df)

# ---------- Content progress: which step each pathway / chatbot set is on ----------
STEP_COLORS = {"done": COLORS["good"], "current": COLORS["progress"], "todo": "#eef0f3"}


def _progress_bar_html(p: dict) -> str:
    segments = ""
    for i, s in enumerate(p["steps"], start=1):
        state = s["state"]
        if state == "current" and p["overdue"]:
            bg, fg = COLORS["critical"], "#fff"
        elif state == "missing":
            bg, fg = "transparent", COLORS["ink"]
        else:
            bg, fg = STEP_COLORS[state], "#fff" if state in ("done", "current") else COLORS["ink"]
        border = f"1.5px dashed {COLORS['neutral']}" if state == "missing" else "none"
        tip = escape(f"{i}. {s['label']}" + (" (no activity in the registry)" if state == "missing" else ""))
        segments += (f'<div title="{tip}" style="flex:1;height:22px;border-radius:5px;background:{bg};'
                     f'border:{border};color:{fg};font-size:11px;font-weight:700;display:flex;'
                     f'align-items:center;justify-content:center;">{i}</div>')

    if p["current"] is None:
        stage = f'<span style="color:{COLORS["good"]};font-weight:800;">All {p["total"]} steps done ✓</span>'
    else:
        cur = p["steps"][p["current"]]
        stage = (f'Step {p["current"] + 1} of {p["total"]} · <b>{escape(cur["label"])}</b> · {escape(cur["owner"])}'
                 + (f' · due {escape(p["due"])}' if p["due"] else ""))
        if p["overdue"]:
            stage += (f' <span class="nav-pill" style="background:#fbe7e7;color:{COLORS["critical"]};">'
                      f'Delayed</span>')

    return f"""
    <div class="nav-card" style="margin-bottom:10px;">
      <div style="display:flex;justify-content:space-between;align-items:baseline;gap:8px;flex-wrap:wrap;">
        <div style="font-weight:800;color:{COLORS['navy']};font-size:15px;">{escape(p['name'])}</div>
        <div style="font-weight:800;color:{COLORS['teal']};font-size:13px;">{p['done']}/{p['total']} steps</div>
      </div>
      <div style="display:flex;gap:4px;margin:10px 0 8px;">{segments}</div>
      <div style="font-size:12.5px;color:{COLORS['ink']};">{stage}</div>
    </div>
    """


def _show_bars(items: list):
    bar_cols = st.columns(2)
    for i, p in enumerate(items):
        with bar_cols[i % 2]:
            st.markdown(_progress_bar_html(p), unsafe_allow_html=True)


st.caption("Green = done, blue = the step it's on now (red if that step is past its end date), "
           "grey = still to come. Hover a step to see its name.")

st.subheader("Pathway progress")
_show_bars(pathway_progress(df))
st.caption("Steps: " + " · ".join(f"{i}. {label} ({owner})" for i, (label, owner, _) in enumerate(STEPS, start=1)))

st.subheader("Chatbot content progress")
chatbot = chatbot_progress(df)
_show_bars(chatbot)
for p in chatbot:
    st.caption(f"{p['name']}: " + " · ".join(f"{i}. {s['label']} ({s['owner']})"
                                              for i, s in enumerate(p["steps"], start=1)))

st.divider()
st.subheader("Work packages")

wp_list = sorted(df["Original WP"].dropna().unique())
cols = st.columns(3)

for i, wp in enumerate(wp_list):
    sub = df[df["Original WP"] == wp]
    total = len(sub)
    done = int((sub["Bucket"] == "Completed").sum())
    pct = round(100 * done / total, 1) if total else 0
    delayed = int(sub["is_overdue"].sum())
    at_risk = int(sub["is_atrisk"].sum())

    with cols[i % 3]:
        badges = ""
        if delayed:
            badges += f'<span class="nav-pill" style="background:#fbe7e7;color:{COLORS["critical"]};margin-right:6px;">{delayed} delayed</span>'
        if at_risk:
            badges += f'<span class="nav-pill" style="background:#fdeed2;color:{COLORS["warning"]};">{at_risk} at risk</span>'

        # The rectangular progress card — always visible, one per work package.
        st.markdown(
            f"""
            <div class="nav-card" style="margin-bottom:8px;">
              <div style="display:flex;justify-content:space-between;align-items:baseline;">
                <div style="font-weight:800;color:{COLORS['navy']};font-size:15px;">{wp}</div>
                <div style="font-weight:800;color:{COLORS['teal']};font-size:15px;">{pct}%</div>
              </div>
              <div class="nav-progress-track"><div class="nav-progress-fill" style="width:{pct}%;"></div></div>
              <div style="margin-top:8px;font-size:12px;color:{COLORS['ink']};">{done}/{total} completed</div>
              <div style="margin-top:6px;">{badges or '&nbsp;'}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        # Clicking the card opens this: every activity in the work package.
        with st.expander(f"View {total} activities"):
            fig = px.pie(sub, names="Bucket", hole=0.55,
                         color="Bucket",
                         color_discrete_map={
                             "Completed": COLORS["good"], "In Progress": COLORS["navy"],
                             "Needs Confirmation": COLORS["warning"], "Not Started": COLORS["neutral"],
                         })
            fig.update_traces(textposition="inside", textinfo="percent+label")
            fig.update_layout(height=220, margin=dict(l=0, r=0, t=0, b=0), showlegend=False)
            st.plotly_chart(fig, use_container_width=True, key=f"wp_pie_{i}")

            for _, row in sub.iterrows():
                with st.container(border=True):
                    h1, h2 = st.columns([3, 1])
                    h1.markdown(f"**{row['Activity']}**")
                    h2.markdown(status_badge_html(row["AutoStatus"]), unsafe_allow_html=True)
                    if can_edit(row):
                        activity_editor(row, activity_key("wp", row), wps, team_names)
                    else:
                        st.caption(f"Owner: {row.get('Responsible (Name)', '—')} · "
                                   f"Start: {row.get('Start Date', '—')} · End: {row.get('End Date', '—')}")
