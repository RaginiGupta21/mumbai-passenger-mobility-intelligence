import streamlit as st, pandas as pd
from .style import hero, kpi, note, pct, num
from ..config import PALETTE as C


def render(d, tt):
    hero("Mumbai Passenger Mobility Intelligence System",
         "Scheduled bus connectivity, journey options, accessibility and inclusive mobility - built only on open secondary data.")
    cells, ind, stops, dq, dg = d["cells"], d["ind"], d["stops"], d["dq"], d["diag"]
    P = cells["pop"].sum()
    cov = lambda r: cells.loc[cells.dist_nearest_m <= r, "pop"].sum() / P
    c = st.columns(5)
    kpi(c[0], "Bus stops (Greater Mumbai)", num(stops.in_greater_mumbai.sum()), f"{num(len(stops))} in the full feed")
    kpi(c[1], "Routes with scheduled trips", num(d["routes"].shape[0]), f"of {num(dq['counts']['routes'])} listed")
    kpi(c[2], "Scheduled trips / day", num(dq["counts"]["trips"]), "BEST, TMT, KDMT, VVMT")
    kpi(c[3], "Residents within 500 m of a stop", pct(cov(500)), f"{pct(cov(300))} within 300 m · {pct(cov(800))} within 800 m")
    kpi(c[4], "Priority gap", num(dg["gaps"]["pop_no_stop_500"]), "residents with no stop within 500 m")
    st.write("")
    L, R = st.columns([1.15, 1])
    with L:
        st.subheader("What the data says")
        eq, g, nw = dg["equity"], dg["gaps"], dg["network"]
        top = pd.DataFrame(dg["priority_areas"]).head(3)
        bullets = [
            f"**{pct(cov(500))}** of Greater Mumbai's {num(P)} residents live within 500 m (straight-line) of a bus stop; **{num(g['pop_no_stop_500'])}** do not.",
            f"Gaps cluster in space (Moran's I = {dg['spatial_autocorrelation']['morans_I']:.2f}, p = {dg['spatial_autocorrelation']['p_value']:.3f}): "
            + ", ".join(f"prabhag {int(r.area.split()[1])}" for r in top.itertuples()) + " have the most residents beyond reach in dense areas.",
            f"Where a stop exists, service is usually frequent - only **{num(g['pop_low_service'])}** residents are covered but receive fewer than 4 scheduled trips per peak hour.",
            f"SC / ST residents' coverage ({pct(eq['sc_cov_500'])} / {pct(eq['st_cov_500'])}) is slightly below the city ({pct(eq['city_cov_500'])}), but the prabhag-level difference is not statistically significant.",
            f"The Vasai-Virar (VVMT) network forms a **separate component** - it does not link to the BEST / TMT network within a 200 m walk.",
            f"**{dq['integrity']['routes_without_trips']}** of {dq['counts']['routes']} routes in the feed have no trips; {dq['time_logic']['timepoint_share']*100:.1f}% of stop times are official timepoints, the rest are interpolated.",
        ]
        for b in bullets:
            st.markdown("- " + b)
    with R:
        st.subheader("Data provenance - real vs derived")
        rows = [
            ("Bus timetable (GTFS)", "BEST, TMT, KDMT, VVMT scheduled stops, routes, trips (feed 19 Aug 2026 - 15 Feb 2027)", "real"),
            ("Ward boundaries & population", "BMC 227 electoral wards with 2011-Census-based population, SC / ST counts (DataMeet)", "real"),
            ("Slum clusters", "SRA slum-cluster polygons digitised by DataMeet", "real"),
            ("Colleges / universities", "OpenStreetMap contributors (HOT export) - partial coverage", "real"),
            ("Public health facilities", "MCGM open data KML - coordinates rounded (~±0.5 km)", "real"),
            ("Population grid, access, indices, clusters", "Computed by this project from the real inputs", "derived"),
            ("Walking speed, detour factor, uniform density in a ward", "Modelling assumptions - see Methods", "assump"),
        ]
        h = "".join(f'<tr><td><b>{a}</b><br><span style="color:{C["muted"]};font-size:.82rem">{b}</span></td><td><span class="chip {k}">{ {"real":"REAL","derived":"DERIVED","assump":"ASSUMPTION"}[k] }</span></td></tr>' for a, b, k in rows)
        st.markdown(f'<div class="card"><table style="width:100%">{h}</table></div>', unsafe_allow_html=True)
        st.write("")
        note("<b>No synthetic data is used anywhere.</b> There are no live bus positions, no actual arrival times and no passenger counts - "
             "all times are <i>scheduled</i> timetable values.")
    st.subheader("Modules")
    m = st.columns(4)
    for col, (t, s) in zip(m, [("Journey Explorer", "Plan scheduled trips with transfers; see where you can reach in 15-90 minutes."),
                               ("Accessibility & Inclusion", "Stop access at 300 / 500 / 800 m, service levels, SC/ST & slum equity, access to colleges and health facilities."),
                               ("Routes & Schedules", "Route profiles, timetables, stop departure boards, service availability."),
                               ("Network Intelligence", "Network centrality, clustering, connectivity gaps and recommended new stop catchments.")]):
        col.markdown(f'<div class="card"><b>{t}</b><br><span style="color:{C["muted"]};font-size:.88rem">{s}</span></div>', unsafe_allow_html=True)
