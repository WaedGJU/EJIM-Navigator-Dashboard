import streamlit as st

from utils.auth import login_gate
from utils.style import inject_base_style, sidebar_user_box
from utils.sheets import load_activities
from utils.compute import enrich

st.set_page_config(page_title="Full Registry", page_icon="📋", layout="wide")
inject_base_style()
login_gate()
sidebar_user_box()

st.title("Full Activity Registry")

df = enrich(load_activities())
if df.empty:
    st.stop()

c1, c2, c3, c4 = st.columns(4)
wp = c1.multiselect("Work package", sorted(df["Original WP"].dropna().unique()))
status = c2.multiselect("Status bucket", sorted(df["Bucket"].dropna().unique()))
owner = c3.multiselect("Owner", sorted(df["Responsible (Name)"].dropna().astype(str).unique()))
search = c4.text_input("Search activity / owner / remarks")

view = df.copy()
if wp:
    view = view[view["Original WP"].isin(wp)]
if status:
    view = view[view["Bucket"].isin(status)]
if owner:
    view = view[view["Responsible (Name)"].isin(owner)]
if search:
    mask = view.apply(lambda r: search.lower() in " ".join(str(v) for v in r.values).lower(), axis=1)
    view = view[mask]

st.caption(f"{len(view)} of {len(df)} activities")
st.dataframe(
    view[["No.", "Original WP", "Activity", "Responsible (Name)", "Status", "End Date",
          "is_overdue", "is_atrisk", "is_unassigned"]],
    use_container_width=True, hide_index=True,
)

st.download_button(
    "⬇ Export filtered view as CSV",
    view.to_csv(index=False).encode("utf-8-sig"),
    file_name="navigator_registry_filtered.csv",
    use_container_width=False,
)
