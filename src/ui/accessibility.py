import folium, numpy as np, pandas as pd, plotly.express as px, plotly.graph_objects as go, streamlit as st
from folium.plugins import HeatMap
from streamlit_folium import st_folium
from .style import hero, kpi, note, pct, num
from .charts import tidy, SEQ, CAT
from ..config import *
from ..maps import base_map, ramp, points_layer

FAC_COL = {"Education": "#41596E", "Public hospital": "#B5707A", "Maternity home": "#C9A25B"}


def _agg(cells, eff):
    c = cells.assign(is_cov=cells.dist_nearest_m <= eff)
    g = c.groupby("prabhag")
    out = pd.DataFrame({"pop": g["pop"].sum(), "covered": c["pop"].where(c.is_cov, 0).groupby(c.prabhag).sum()})
    out["cov"] = out.covered / out["pop"]; out["uncovered"] = out["pop"] - out.covered
    return out.reset_index()


def _choropleth(m, d, agg, col="cov", vmin=0, vmax=1, fmt="{:.0%}"):
    geo = {"type": "FeatureCollection", "features": []}
    ind = d["ind"].set_index("prabhag"); a = agg.set_index("prabhag")
    for f in d["prabhag_geo"]["features"]:
        pr = f["properties"]["prabhag"]
        if pr not in a.index: continue
        p = dict(f["properties"]); p.update(label=f"Prabhag {pr} (ward {ind.admin_ward[pr]})", pop=f"{int(a['pop'][pr]):,}", value=fmt.format(a[col][pr]),
                                            density=f"{ind.pop_density_km2[pr]:,.0f} /km²", v=float(a[col][pr]))
        geo["features"].append({"type": "Feature", "geometry": f["geometry"], "properties": p})
    folium.GeoJson(geo, name="Prabhags", style_function=lambda f: dict(fillColor=ramp(f["properties"]["v"], vmin, vmax), color="#FFFFFF", weight=.7, fillOpacity=.72),
                   highlight_function=lambda f: dict(weight=2, color="#2F3E46"),
                   tooltip=folium.GeoJsonTooltip(fields=["label", "pop", "value", "density"], aliases=["", "Population", "Value", "Density"], sticky=True)).add_to(m)


def render(d, tt):
    hero("Accessibility & Inclusive Mobility", "Who can walk to a bus stop, how good is the service they get, and can they reach colleges and health care?")
    cells, ind, fac, stops, sites = d["cells"], d["ind"], d["fac"], d["stops"], d["sites"]
    c = st.columns([1, 1, 2])
    radius = c[0].radio("Walking distance to a stop", ACCESS_RADII_M, index=1, horizontal=True, format_func=lambda r: f"{r} m", key="a_r")
    adj = c[1].toggle("Street-detour adjusted", value=False, help=f"Divides the distance by {DETOUR_FACTOR} to approximate real walking paths (no OSM road network offline).", key="a_adj")
    wards = c[2].multiselect("Filter by BMC ward", sorted(ind.admin_ward.unique()), key="a_w", placeholder="All wards")
    eff = radius / (DETOUR_FACTOR if adj else 1)
    cf = cells[cells.admin_ward.isin(wards)] if wards else cells
    P = cf["pop"].sum(); covm = cf.dist_nearest_m <= eff
    k = st.columns(5)
    kpi(k[0], f"Population ≤ {radius} m", pct(cf.loc[covm, "pop"].sum() / P), f"{num(P)} residents in selection")
    kpi(k[1], "Without a stop", num(cf.loc[~covm, "pop"].sum()), f"beyond {eff:.0f} m straight-line")
    sc = cf.loc[covm, "sc_pop"].sum() / cf.sc_pop.sum(); stp = cf.loc[covm, "st_pop"].sum() / cf.st_pop.sum()
    kpi(k[2], "SC / ST coverage", f"{pct(sc, 0)} / {pct(stp, 0)}", "Scheduled Castes / Tribes")
    sl = cf[cf.is_slum]; kpi(k[3], "Slum-cluster area covered", pct((sl.dist_nearest_m <= eff).mean()) if len(sl) else "-", f"{len(sl):,} grid cells of 100 m")
    kpi(k[4], "Median peak service nearby", f"{np.median(cf.trips_peak_h_500[covm]) if covm.any() else 0:.0f} trips/h", "unique trips within 500 m, 08-10h")
    st.write("")
    TABS = ["Coverage map", "Service quality", "Inclusion & equity", "Colleges & health facilities", "Reach by transit"]
    view = st.radio("Section", TABS, horizontal=True, key="a_tab", label_visibility="collapsed")   # lazy: only the selected section is computed

    if view == TABS[0]:
        agg = _agg(cf, eff)
        layers = st.multiselect("Map layers", ["Bus stops", "Residents without a stop (heat)", "Colleges & universities", "Health facilities", "Suggested new stop catchments"],
                                default=["Bus stops"], key="a_layers")
        m = base_map(zoom=11); _choropleth(m, d, agg)
        if "Bus stops" in layers:
            points_layer(m, stops[stops.in_greater_mumbai], "stop_lat", "stop_lon", ["stop_name", "n_routes", "departures_day"], ["Stop", "Routes", "Departures/day"], color="#2F4F63", radius=2.2, opacity=.7, name="Bus stops")
        if "Residents without a stop (heat)" in layers:
            u = cf[~covm]; u = u.sample(min(len(u), 6000), random_state=1) if len(u) else u
            HeatMap(u[["lat", "lon", "pop"]].values.tolist(), radius=14, blur=18, min_opacity=.25, gradient={0.3: "#E3B88C", 0.6: "#C9856B", 1: "#8F4A45"}).add_to(m)
        for lab, sel, grp in [("Colleges & universities", fac.group == "Education", None), ("Health facilities", (fac.group == "Health") & fac.usable, None)]:
            if lab in layers:
                for r in fac[sel].itertuples():
                    col = FAC_COL.get(r.category, FAC_COL["Education"] if r.group == "Education" else "#7FA38F")
                    if r.precision != "precise":
                        folium.Circle((r.lat, r.lon), radius=550, color=col, weight=1, fill=True, fill_opacity=.07).add_to(m)
                    folium.CircleMarker((r.lat, r.lon), radius=5, color="#fff", weight=1, fill=True, fill_color=col, fill_opacity=1,
                                        tooltip=f"{r.name} ({r.category}) · nearest stop ~{r.dist_stop_center_m:.0f} m · {r.precision}").add_to(m)
        if "Suggested new stop catchments" in layers:
            for r in sites.itertuples():
                folium.Circle((r.lat, r.lon), radius=500, color="#B8795A", weight=1.5, fill=True, fill_opacity=.12).add_to(m)
                folium.Marker((r.lat, r.lon), icon=folium.DivIcon(html=f'<div style="background:#B8795A;color:#fff;border-radius:50%;width:22px;height:22px;text-align:center;line-height:22px;font-size:11px;border:2px solid #fff">{r.rank}</div>'),
                              tooltip=f"#{r.rank}: +{r.newly_covered_pop:,.0f} residents covered · prabhag {r.prabhag}").add_to(m)
        st_folium(m, height=580, use_container_width=True, returned_objects=[], key="covmap")
        st.caption(f"Shading = share of each prabhag's residents within {eff:.0f} m of a stop (straight line). Darker teal = better. Population is spread evenly inside each prabhag (see Methods).")
        L, R = st.columns(2)
        with L:
            wc = cf.assign(is_cov=covm).groupby("admin_ward").apply(lambda g: pd.Series({"coverage": g["pop"][g.is_cov].sum() / g["pop"].sum(), "unserved": g["pop"][~g.is_cov].sum()}), include_groups=False).reset_index().sort_values("coverage")
            f = px.bar(wc, x="coverage", y="admin_ward", orientation="h", title=f"Population coverage within {radius} m by ward", color="coverage", color_continuous_scale=SEQ[::1], range_color=(0, 1))
            f.update_xaxes(tickformat=".0%", range=[0, 1]); f.update_coloraxes(showscale=False); st.plotly_chart(tidy(f, 520), width="stretch")
        with R:
            dist = np.arange(0, 2001, 50); w = cf["pop"].to_numpy(); dd = cf.dist_nearest_m.to_numpy()
            cum = [w[dd <= x].sum() / w.sum() for x in dist]
            f = go.Figure(go.Scatter(x=dist, y=cum, mode="lines", fill="tozeroy", line=dict(color="#3F7C85", width=3), fillcolor="rgba(63,124,133,.18)"))
            for r_ in ACCESS_RADII_M: f.add_vline(x=r_, line_dash="dot", line_color="#B8795A", annotation_text=f"{r_} m")
            f.update_layout(title="Cumulative share of residents by distance to nearest stop", xaxis_title="metres (straight line)", yaxis_tickformat=".0%")
            st.plotly_chart(tidy(f, 520), width="stretch")
        st.subheader("Where the gaps are largest")
        top = agg.merge(ind[["prabhag", "admin_ward", "pop_density_km2"]], on="prabhag").sort_values("uncovered", ascending=False).head(15)
        top["Area type"] = np.where(top.pop_density_km2 >= 5000, "dense urban", "low density*")
        tb = top.rename(columns={"prabhag": "Prabhag", "admin_ward": "Ward", "pop": "Population", "cov": "Coverage", "uncovered": "Residents without stop", "pop_density_km2": "Density /km²"})
        st.dataframe(tb[["Prabhag", "Ward", "Population", "Coverage", "Residents without stop", "Density /km²", "Area type"]].style.format({"Population": "{:,.0f}", "Coverage": "{:.0%}", "Residents without stop": "{:,.0f}", "Density /km²": "{:,.0f}"}), hide_index=True, width="stretch")
        st.caption("*Low-density prabhags may include parks, port or industrial land, so the uniform-density assumption overstates unserved residents there.")
        st.download_button("Download this table (CSV)", tb.to_csv(index=False).encode(), "coverage_gaps.csv", "text/csv")

    if view == TABS[1]:
        pk = cf.trips_peak_h_500.to_numpy(); w = cf["pop"].to_numpy()
        bands = np.select([pk == 0, pk < 4, pk < 10], [LOS_BANDS[0][1], LOS_BANDS[1][1], LOS_BANDS[2][1]], LOS_BANDS[3][1])
        los = pd.Series(w).groupby(bands).sum().reindex([b[1] for b in LOS_BANDS]).fillna(0)
        L, R = st.columns(2)
        with L:
            f = px.bar(x=los.index, y=los.values / los.sum(), title="Residents by peak-hour service level (unique scheduled trips / hour within 500 m)", color=los.index,
                       color_discrete_sequence=["#B5707A", "#D9A86B", "#8FB3A5", "#3F7C85"]); f.update_layout(showlegend=False, yaxis_tickformat=".0%", xaxis_title="", yaxis_title="share of residents")
            st.plotly_chart(tidy(f), width="stretch")
        with R:
            f = px.histogram(cf[cf["pop"] > 0], x="n_routes_500", y="pop", histfunc="sum", nbins=40, title="Route choice: distinct routes within 500 m", color_discrete_sequence=["#3F7C85"])
            f.update_layout(xaxis_title="routes", yaxis_title="residents"); st.plotly_chart(tidy(f), width="stretch")
        m = base_map(); a = ind.set_index("prabhag").rename(columns={"trips_peak_h_500_popw": "v"})[["v", "pop"]].reset_index()
        _choropleth(m, d, a.assign(cov=a.v), "cov", 0, float(a.v.quantile(.95)), "{:.0f} trips/h")
        st.markdown("**Average peak-hour service in the 500 m catchment (population-weighted)**")
        st_folium(m, height=470, use_container_width=True, returned_objects=[], key="svcmap")
        note("Service level counts each scheduled trip once even if it passes several nearby stops. It measures scheduled supply, not crowding - passenger counts are not available in open data.")

    if view == TABS[2]:
        eq = d["diag"]["equity"]
        L, R = st.columns(2)
        with L:
            vals = pd.DataFrame({"Group": ["All residents", "Scheduled Castes", "Scheduled Tribes", "Slum clusters (area)"],
                                 "Coverage": [eq["city_cov_500"], eq["sc_cov_500"], eq["st_cov_500"], eq["slum_area_cov_500"]]})
            f = px.bar(vals, x="Group", y="Coverage", title="Share within 500 m of a stop (city-wide)", color="Group", color_discrete_sequence=[C_ for C_ in CAT])
            f.update_layout(showlegend=False, yaxis_tickformat=".0%", yaxis_range=[0, 1], xaxis_title=""); st.plotly_chart(tidy(f), width="stretch")
        with R:
            st.markdown("**Reading the result**")
            st.markdown(f"- SC residents: **{pct(eq['sc_cov_500'])}**, ST residents: **{pct(eq['st_cov_500'])}**, all residents: **{pct(eq['city_cov_500'])}**.\n"
                        f"- A paired Wilcoxon test across {eq['n_sc']} prabhags finds the differences are **not statistically significant** (SC p = {eq['wilcoxon_sc_p']:.2f}, ST p = {eq['wilcoxon_st_p']:.2f}).\n"
                        f"- {pct(eq['slum_area_cov_500'])} of mapped slum-cluster area lies within 500 m of a stop - slum clusters sit mostly in dense, well-served parts of the city.\n"
                        "- Slum polygons carry **no population counts**, so this is an area measure only.")
            note("SC/ST counts are from the 2011-Census-based prabhag delimitation (2017). They are shares of a ward's population, spread evenly across it - not household locations.")
        a = ind[["prabhag", "admin_ward", "pop", "sc_pop", "st_pop", "sc_cov_500", "st_cov_500", "cov_500", "slum_cov_500"]].dropna(subset=["sc_cov_500"])
        a["gap_sc_pp"] = (a.sc_cov_500 - a.cov_500) * 100
        w = a.sort_values("gap_sc_pp").head(10)
        st.markdown("**Prabhags where SC residents are least well covered relative to the prabhag average**")
        st.dataframe(w.rename(columns={"prabhag": "Prabhag", "admin_ward": "Ward", "pop": "Population", "sc_pop": "SC pop.", "sc_cov_500": "SC coverage", "cov_500": "Coverage", "gap_sc_pp": "Gap (pp)"})[["Prabhag", "Ward", "Population", "SC pop.", "SC coverage", "Coverage", "Gap (pp)"]]
                     .style.format({"Population": "{:,.0f}", "SC pop.": "{:,.0f}", "SC coverage": "{:.0%}", "Coverage": "{:.0%}", "Gap (pp)": "{:.1f}"}), hide_index=True, width="stretch")

    if view == TABS[3]:
        grp = st.radio("Facility type", ["College / university", "Public hospital", "Maternity home", "UPHC", "Dispensary"], horizontal=True, key="f_g")
        mp = {"College / university": fac.group == "Education", "Public hospital": fac.category == "Public hospital", "Maternity home": fac.category == "Maternity home",
              "UPHC": fac.category.str.startswith("UPHC"), "Dispensary": fac.category == "Dispensary"}
        fs = fac[mp[grp] & fac.usable].copy()
        r_ = st.radio("Access radius", ACCESS_RADII_M, index=1, horizontal=True, format_func=lambda x: f"{x} m", key="f_r")
        cert, poss = fs[f"certain_{r_}"].sum(), fs[f"possible_{r_}"].sum()
        k = st.columns(4)
        kpi(k[0], "Facilities analysed", len(fs), "precision-screened records")
        kpi(k[1], f"Certainly ≤ {r_} m of a stop", f"{cert} ({cert / max(len(fs), 1):.0%})", "even in worst case of rounding")
        kpi(k[2], f"Possibly ≤ {r_} m", f"{poss} ({poss / max(len(fs), 1):.0%})", "best case of rounding")
        kpi(k[3], "Median routes within 500 m", f"{fs.n_routes_500.median():.0f}" if len(fs) else "-", f"median {fs.trips_day_500.median():.0f} trips/day" if len(fs) else "")
        def status(r):
            return "Within" if r[f"certain_{r_}"] else ("Possibly within" if r[f"possible_{r_}"] else "Beyond")
        fs["Access"] = fs.apply(status, axis=1)
        tb = fs.sort_values("dist_stop_center_m", ascending=False)[["name", "category", "ward", "dist_stop_center_m", "Access", "n_routes_500", "trips_day_500", "precision"]]
        tb.columns = ["Facility", "Type", "Ward", "Distance to nearest stop (m)", "Access", "Routes ≤500 m", "Trips/day ≤500 m", "Location precision"]
        st.dataframe(tb.style.format({"Distance to nearest stop (m)": "{:.0f}", "Trips/day ≤500 m": "{:,.0f}"}), hide_index=True, width="stretch", height=380)
        st.download_button("Download facility access table (CSV)", tb.to_csv(index=False).encode(), "facility_access.csv", "text/csv")
        note("<b>Coverage caveats.</b> Colleges/universities come from OpenStreetMap and are <i>incomplete</i> (44 mapped in Greater Mumbai). Health facilities come from MCGM's public layers "
             "(private hospitals are not included) and most have coordinates rounded to ~1 km, so each is tested with a ±0.005° uncertainty box: <i>certainly</i> within = even the farthest "
             "corner is within range; <i>possibly</i> = the nearest corner is. 31 records with ~±5 km precision are excluded.")

    if view == TABS[4]:
        st.markdown("**Travel-time access from each prabhag's population centre (weekday 09:00 departure, scheduled buses, ≤3 transfers, ≤75 min)**")
        meas = st.radio("Measure", ["Colleges / universities", "Public hospitals", "Primary health (UPHC + dispensary)"], horizontal=True, key="t_m")
        key = {"Colleges / universities": "college", "Public hospitals": "public_hospital", "Primary health (UPHC + dispensary)": "primary_health"}[meas]
        mode = st.radio("Show", ["Minutes to the nearest", "Number reachable within 45 min", "Number reachable within 60 min"], horizontal=True, key="t_mode")
        col = f"{key}_nearest_min" if mode.startswith("Minutes") else f"{key}_n_{45 if '45' in mode else 60}"
        a = ind[["prabhag", "pop", col]].rename(columns={col: "cov"}); a["cov"] = a["cov"].fillna(75 if mode.startswith("Minutes") else 0)
        vmax = 75 if mode.startswith("Minutes") else float(a.cov.quantile(.95)) or 1
        m = base_map()
        _choropleth(m, d, a, "cov", 0, vmax, "{:.0f} min" if mode.startswith("Minutes") else "{:.0f} facilities")
        if mode.startswith("Minutes"):
            st.caption("Lighter = quicker. Prabhags shown at 75 min have no facility reachable within 75 minutes.")
        else:
            st.caption("Darker = more facilities reachable.")
        st_folium(m, height=500, use_container_width=True, returned_objects=[], key="tmap")
        w = ind.assign(v=ind[f"{key}_nearest_min"].fillna(999)).sort_values("v", ascending=False).head(10)
        w["Nearest (min)"] = w[f"{key}_nearest_min"].map(lambda x: "none ≤ 75" if pd.isna(x) else f"{x:.0f}")
        st.markdown("**Slowest-access prabhags**")
        st.dataframe(w[["prabhag", "admin_ward", "pop", "Nearest (min)", f"{key}_n_60"]].rename(columns={"prabhag": "Prabhag", "admin_ward": "Ward", "pop": "Population", f"{key}_n_60": "Reachable ≤60 min"})
                     .style.format({"Population": "{:,.0f}"}), hide_index=True, width="stretch")
