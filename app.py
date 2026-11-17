"""Public Transport Demand and Service Gap Analysis - Mumbai bus network.   Run:  python -m streamlit run app.py"""
import folium
import numpy as np
import pandas as pd
import plotly.express as px
import streamlit as st
from folium.plugins import HeatMap
from streamlit_folium import st_folium

from src.config import *
from src import gap, search

st.set_page_config(page_title="Public Transport Demand and Service Gap Analysis", layout="wide")
st.markdown("""<style>
.block-container {padding-top: 1.5rem; max-width: 1300px;}
.kpi {background:#fff; border:1px solid #E0DACB; border-radius:12px; padding:12px 16px;}
.kpi .v {font-size:1.6rem; font-weight:650; color:#3F7C85;} .kpi .l {font-size:.78rem; color:#6B7B83; text-transform:uppercase;} .kpi .s {font-size:.8rem; color:#6B7B83;}
.box {background:#FBF4E4; border:1px solid #EBDDB8; border-radius:10px; padding:10px 14px; font-size:.9rem; color:#5E4F27;}
</style>""", unsafe_allow_html=True)


@st.cache_data(show_spinner="Loading data...")
def get_data():
    return gap.load_data()


def kpi(col, label, value, sub=""):
    col.markdown(f'<div class="kpi"><div class="l">{label}</div><div class="v">{value}</div><div class="s">{sub}</div></div>', unsafe_allow_html=True)


def search_ui(d):
    """A search box above the map. Returns (pin, info): the chosen place and the bus service there (or None, None)."""
    with st.form("search_form"):
        c = st.columns([5, 1])
        q = c[0].text_input("Find an address or place", key="q", label_visibility="collapsed",
                            placeholder="Find an address or place, e.g. Malad station, Orlem church, or coordinates like 19.18, 72.84")
        go = c[1].form_submit_button("Find", width="stretch")
    if go:
        cands, msg = search.find(q, d["stops"])
        st.session_state["cands"], st.session_state["search_msg"] = cands, msg
        st.session_state.pop("cand", None)
    cands = st.session_state.get("cands", [])
    if st.session_state.get("search_msg"):
        (st.warning if not cands else st.info)(st.session_state["search_msg"])
    if not cands:
        return None, None
    i = 0
    if len(cands) > 1:
        i = st.selectbox("Matches", range(len(cands)), format_func=lambda k, c=cands: c[k]["label"], key="cand")
    pin = cands[i]
    info = search.service_at(d, pin["lat"], pin["lon"])
    if info is None:
        st.warning("That place is outside the mapped Greater Mumbai area, so there is no service information for it.")
        return pin, None
    k = st.columns(4)
    kpi(k[0], "Area", f"Prabhag {info['prabhag']}", f"{info['admin_ward']} ward")
    kpi(k[1], "Nearest bus stop", f"{info['nearest_stop_m']:.0f} m", info["nearest_stop"])
    kpi(k[2], "Peak bus trips nearby", f"{info['trips_peak_h']:.0f} per hour", f"within {NEAR_M} m, 08:00 to 10:00")
    kpi(k[3], "Verdict", info["status"], "estimate from a 100 m grid")
    if st.button("Clear search"):
        st.session_state.pop("cands", None); st.session_state.pop("search_msg", None); st.rerun()
    return pin, info


d = get_data()
label = ward_label()
w = d["wards"]; sw = w[w.is_study_ward].iloc[0]; city = d["meta"]["settings"]["city"]
city_share = city["underserved"] / city["residents"]

with st.sidebar:
    st.markdown("### Public Transport Demand and Service Gap Analysis")
    st.caption(f"Study area: {label}, Mumbai (residential)")
    page = st.radio("Page", ["Service gap map", "Where to fix it"], label_visibility="collapsed", key="page")
    st.markdown("---")
    st.caption("Scheduled bus timetable (GTFS, valid 19 Aug 2026 to 15 Feb 2027) and Census 2011 population. No live data and no passenger counts are used.")

with st.expander("How this was calculated, and its limits"):
    st.markdown(f"""
- **Demand** = residents of each small area (prabhag), from Census 2011. Real ridership counts are not available, so residents are used as a stand-in for demand.
- **Supply** = distance to the nearest bus stop and the number of scheduled bus trips per hour (08:00 to 10:00) within {NEAR_M} m.
- **Underserved** = no stop within {NEAR_M} m (straight line), or a stop but fewer than {LOW_FREQ} scheduled trips per peak hour.
- Residents are spread evenly inside each prabhag on a {GRID_M} m grid, so local numbers are estimates (parks or industry are not removed).
- Walking distance is a straight line; no road network is used. Times in the feed are partly interpolated.
- Only buses are included (no trains or Metro), so areas near stations may be better connected than shown.
""")

# =====================================================================================  PAGE 1
if page == "Service gap map":
    st.title(f"Service gap map: {label}")
    st.markdown("Where do many residents (**demand**) have too little bus service (**supply**)? Choose a measure below; the note under the map explains the colours.")
    k = st.columns(4)
    kpi(k[0], "Residents", f"{sw['pop']:,.0f}", f"{label}, Census 2011")
    kpi(k[1], "Underserved residents", f"{sw.underserved_pop:,.0f}", f"{sw.underserved_share:.1%} of the ward (city: {city_share:.1%})")
    kpi(k[2], f"No stop within {NEAR_M} m", f"{sw.no_stop_pop:,.0f}", f"{sw.no_stop_share:.1%} of residents")
    kpi(k[3], "Stop nearby, low frequency", f"{sw.low_freq_pop:,.0f}", f"fewer than {LOW_FREQ} trips per peak hour")
    st.write("")
    pin, info = search_ui(d)
    st.write("")
    c = st.columns([2, 1, 1])
    measure = c[0].selectbox("Colour the map by", list(gap.MEASURES), key="measure")
    show_stops = c[1].checkbox("Show bus stops", value=False, key="show_stops")
    show_heat = c[2].checkbox("Show residents without a stop", value=False, key="show_heat")
    centre, zoom = gap.ward_view(d)
    other_ward = bool(info) and info["admin_ward"] != STUDY_WARD            # searched place is outside the study ward: show the whole city
    if pin: centre, zoom = [pin["lat"], pin["lon"]], 16
    m = gap.base_map(centre, zoom); gap.choropleth(m, d, measure, ward_only=not other_ward)
    if pin: gap.add_pin(m, pin, info)
    if show_stops or pin: gap.stops_layer(m, d)
    u = d["cells"][d["cells"].no_stop]
    if show_heat and len(u):
        HeatMap(u[["lat", "lon", "pop"]].values.tolist(), radius=14, blur=18, min_opacity=.25, gradient={0.3: "#E3B88C", 0.6: "#C9856B", 1: "#8F4A45"}).add_to(m)
    st_folium(m, height=540, use_container_width=True, returned_objects=[], key="gapmap")
    st.caption(f"{gap.MEASURES[measure][3]} Hover over an area for details. Source: GTFS timetable and Census 2011.")

    pr = d["pr"]; s = pr[pr.admin_ward == STUDY_WARD].copy().sort_values("underserved_pop")
    long = pd.concat([s.assign(kind="No stop within 500 m", people=s.no_stop_pop), s.assign(kind="Stop nearby but low frequency", people=s.low_freq_pop)])
    long["area"] = "Prabhag " + long.prabhag.astype(int).astype(str)
    f = px.bar(long, y="area", x="people", color="kind", orientation="h", title="Underserved residents by prabhag",
               color_discrete_map={"No stop within 500 m": "#C9856B", "Stop nearby but low frequency": "#E3B88C"}, category_orders={"area": list(long.area.unique())})
    f.update_layout(height=520, margin=dict(l=8, r=8, t=40, b=8), paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(255,255,255,.6)", legend=dict(orientation="h", y=-0.12, title=""), xaxis_title="residents", yaxis_title="")
    st.plotly_chart(f, width="stretch")

    tb = s.sort_values("underserved_pop", ascending=False)[["prabhag", "pop", "density_km2", "underserved_pop", "underserved_share", "no_stop_pop", "low_freq_pop", "peak_trips_h", "area_type"]]
    tb.columns = ["Prabhag", "Residents", "Density per km2", "Underserved", "Underserved share", "No stop", "Low frequency", "Peak trips/hour", "Area type"]
    st.dataframe(tb.style.format({"Residents": "{:,.0f}", "Density per km2": "{:,.0f}", "Underserved": "{:,.0f}", "Underserved share": "{:.0%}", "No stop": "{:,.0f}", "Low frequency": "{:,.0f}", "Peak trips/hour": "{:.0f}"}),
                 hide_index=True, width="stretch")
    st.download_button("Download this table (CSV)", tb.to_csv(index=False).encode(), f"service_gap_{STUDY_WARD.replace(' ', '')}.csv", "text/csv")

# =====================================================================================  PAGE 2
else:
    st.title(f"Where to fix it: {label}")
    st.markdown("Which areas should come first, and where would a new stop help the most residents?")
    pin, info = search_ui(d)
    sites = d["sites"]
    if sites.empty:
        st.success(f"Every resident of the {label} already has a bus stop within {NEAR_M} m, so no new stop areas are needed.")
        for r in gap.recommendations(d): st.markdown("- " + r)
        wd = w.sort_values("underserved_share")
        f = px.bar(wd, x="underserved_share", y="admin_ward", orientation="h", color="is_study_ward", title="Underserved share of residents, by BMC ward",
                   color_discrete_map={True: "#C9856B", False: "#B9C9C4"})
        f.update_layout(height=520, margin=dict(l=8, r=8, t=40, b=8), showlegend=False, xaxis_tickformat=".0%", xaxis_title="", yaxis_title="")
        st.plotly_chart(f, width="stretch")
        st.stop()
    last = sites.iloc[-1]
    after = sw.no_stop_pop - last.cumulative_covered
    k = st.columns(3)
    kpi(k[0], "Residents with no stop nearby", f"{sw.no_stop_pop:,.0f}", f"{label} today")
    kpi(k[1], f"After {len(sites)} new stop areas", f"{after:,.0f}", f"{last.cumulative_covered:,.0f} fewer ({last.cumulative_share_of_no_stop:.0%})")
    kpi(k[2], "Underserved share", f"{sw.underserved_share:.1%}", f"Greater Mumbai: {city_share:.1%}")
    st.write("")
    L, R = st.columns([1.15, 1])
    with L:
        centre, zoom = gap.ward_view(d)
        if pin: centre, zoom = [pin["lat"], pin["lon"]], 16
        m = gap.base_map(centre, zoom)
        folium.GeoJson({"type": "FeatureCollection", "features": [f for f in d["geo"]["features"] if f["properties"]["admin_ward"] == STUDY_WARD]},
                       style_function=lambda f: dict(fillColor="#EFE6D8", color="#FFFFFF", weight=1, fillOpacity=.7)).add_to(m)
        u = d["cells"][d["cells"].no_stop]
        if len(u): HeatMap(u[["lat", "lon", "pop"]].values.tolist(), radius=14, blur=18, min_opacity=.2, gradient={0.3: "#E3B88C", 0.6: "#C9856B", 1: "#8F4A45"}).add_to(m)
        gap.stops_layer(m, d)
        for r in sites.itertuples():
            col = "#3F7C85" if r.area_type == "dense residential" else "#B8795A"
            folium.Circle((r.lat, r.lon), radius=NEAR_M, color=col, weight=1.5, fill=True, fill_opacity=.12).add_to(m)
            folium.Marker((r.lat, r.lon), icon=folium.DivIcon(html=f'<div style="background:{col};color:#fff;border-radius:50%;width:22px;height:22px;text-align:center;line-height:22px;font-size:11px;border:2px solid #fff">{r.rank}</div>'),
                          tooltip=f"#{r.rank}: about {r.newly_covered:,.0f} more residents covered (prabhag {r.prabhag})").add_to(m)
        if pin: gap.add_pin(m, pin, info)
        st_folium(m, height=500, use_container_width=True, returned_objects=[], key="sitemap")
        st.caption("Numbered circles = suggested new stop areas (500 m reach). Teal = dense residential prabhag; orange = lower-density prabhag (check on the ground). Brown glow = residents with no stop nearby. Dark dots = existing stops.")
    with R:
        st.subheader("Recommendations")
        for r in gap.recommendations(d): st.markdown("- " + r)

    c = st.columns(2)
    f = px.line(sites, x="rank", y="cumulative_covered", markers=True, title="Residents newly covered as new stop areas are added", color_discrete_sequence=["#3F7C85"])
    f.update_layout(height=320, margin=dict(l=8, r=8, t=40, b=8), paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(255,255,255,.6)", xaxis_title="number of new stop areas", yaxis_title="residents covered")
    c[0].plotly_chart(f, width="stretch")
    wd = w.sort_values("underserved_share")
    f = px.bar(wd, x="underserved_share", y="admin_ward", orientation="h", color="is_study_ward", title="Underserved share of residents, by BMC ward",
               color_discrete_map={True: "#C9856B", False: "#B9C9C4"})
    f.add_vline(x=city_share, line_dash="dot", line_color="#41596E", annotation_text="Greater Mumbai")
    f.update_layout(height=520, margin=dict(l=8, r=8, t=40, b=8), paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(255,255,255,.6)", showlegend=False, xaxis_tickformat=".0%", xaxis_title="", yaxis_title="")
    c[1].plotly_chart(f, width="stretch")

    tb = sites.rename(columns={"rank": "Rank", "prabhag": "Prabhag", "lat": "Latitude", "lon": "Longitude", "newly_covered": "Residents newly covered", "cumulative_covered": "Cumulative", "cumulative_share_of_no_stop": "Share of residents with no stop", "area_type": "Area type"})
    st.dataframe(tb[["Rank", "Prabhag", "Latitude", "Longitude", "Residents newly covered", "Cumulative", "Share of residents with no stop", "Area type"]]
                 .style.format({"Latitude": "{:.4f}", "Longitude": "{:.4f}", "Residents newly covered": "{:,.0f}", "Cumulative": "{:,.0f}", "Share of residents with no stop": "{:.0%}"}), hide_index=True, width="stretch")
    st.download_button("Download suggested stop areas (CSV)", tb.to_csv(index=False).encode(), "suggested_new_stop_areas.csv", "text/csv")
