"""Mumbai Passenger Mobility Intelligence System - Streamlit entry point.
Run:  streamlit run app.py
"""
import streamlit as st

st.set_page_config(page_title="Mumbai Passenger Mobility Intelligence System", page_icon=":material/directions_bus:", layout="wide", initial_sidebar_state="expanded")

from src.data import get_data, get_tt
from src.ui import style, home, journey, accessibility, routes, network, about, guide

style.inject()
d = get_data(); tt = get_tt()

PAGES = {"Home": home, "Journey Explorer": journey, "Accessibility & Inclusion": accessibility,
         "Routes & Schedules": routes, "Network Intelligence": network, "How to use": guide, "Methods & Data": about}
with st.sidebar:
    st.markdown("### Mumbai Passenger Mobility Intelligence")
    page = st.radio("Navigate", list(PAGES), label_visibility="collapsed", key="nav")
    st.markdown("---")
    v0, v1 = tt.feed_validity()
    st.caption(f"Timetable feed: {v0:%d %b %Y} – {v1:%d %b %Y}\n\nScheduled data only · no synthetic data\n\nSources: GTFS (BEST/TMT/KDMT/VVMT), DataMeet wards, OSM, MCGM")
PAGES[page].render(d, tt)
