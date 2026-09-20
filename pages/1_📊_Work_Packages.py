import pandas as pd
import streamlit as st
import plotly.express as px

from utils.auth import login_gate, current_user, is_admin
from utils.style import inject_base_style, sidebar_user_box, COLORS
from utils.sheets import load_activities, update_activity_cell, ConflictError
from utils.compute import enrich

st.set_page_config(page_title="Work Packages", page_icon="📊", layout="wide")
inject_base_style()
login_gate()
sidebar_user_box()

st.title("Work Packages (WP1–WP9)")
st.caption("Every work package as a progress card — open one to see its activities. "
           "Admins can update an activity's status and due date right here; it's saved to Google Sheets instantly.")

user = current_user()
admin = is_admin()

STATUS_OPTIONS = ["Not started", "In Progress", "Completed", "On Hold",
                   "Unconfirmed - needs update", "Proposed - Pending Validation"]

df = enrich(load_activities())
if df.empty:
    st.stop()

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

            if not admin:
                st.dataframe(
                    sub[["No.", "Activity", "Responsible (Name)", "Status", "End Date"]],
                    use_container_width=True, hide_index=True, height=260,
                )
            else:
                for row_number, row in sub.iterrows():
                    with st.container(border=True):
                        st.markdown(f"**{row['Activity']}**")
                        st.caption(f"Owner: {row.get('Responsible (Name)', '—')}")

                        k = f"wp_{row_number}"
                        status_col, due_col, save_col = st.columns([1.5, 1.2, 0.8])
                        new_status = status_col.selectbox(
                            "Status", STATUS_OPTIONS,
                            index=STATUS_OPTIONS.index(row["Status"]) if row["Status"] in STATUS_OPTIONS else 0,
                            key=f"status_{k}",
                        )
                        current_end = str(row.get("End Date", "") or "").strip()
                        try:
                            end_default = pd.to_datetime(current_end).date() if current_end else None
                        except Exception:
                            end_default = None
                        new_end = due_col.date_input("Due date", value=end_default, key=f"end_{k}")

                        with save_col:
                            st.write("")  # vertical spacer so the button lines up with the inputs
                            if st.button("💾 Save", key=f"save_{k}", use_container_width=True):
                                try:
                                    if new_status != row["Status"]:
                                        update_activity_cell(row_number, "Status", new_status, user)
                                    if new_end and new_end.isoformat() != current_end:
                                        update_activity_cell(row_number, "End Date", new_end.isoformat(), user)
                                    st.success("Saved ✅")
                                    st.rerun()
                                except ConflictError as e:
                                    st.error(str(e))
