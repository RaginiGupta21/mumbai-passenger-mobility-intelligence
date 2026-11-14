import folium, numpy as np, pandas as pd, plotly.express as px, plotly.graph_objects as go, streamlit as st
from streamlit_folium import st_folium
from .style import hero, kpi, note, pct, num
from .charts import tidy, CAT
from .accessibility import _choropleth
from ..config import PALETTE as C
from ..maps import base_map, ramp, points_layer

ARCH_COL = {"Highly connected core": "#2F6F7A", "Well connected": "#8FB3A5", "Partially covered": "#D9A86B", "Underserved periphery": "#B5707A"}
STOP_COL = {"Major hubs": "#B5707A", "Trunk-corridor stops": "#D9A86B", "Local stops": "#8FB3A5"}


def render(d, tt):
    hero("Transport Network Intelligence", "Connectivity gaps, critical stops, typologies and recommendations from graph analysis and clustering.")
    dg, ind, stops, rs, sites = d["diag"], d["ind"], d["stops"], d["routes"], d["sites"]
    TABS = ["Network structure", "Stop typology", "Route typology", "Connectivity index & archetypes", "Gaps & recommendations"]
    view = st.radio("Section", TABS, horizontal=True, key="n_tab", label_visibility="collapsed")   # lazy: only the selected section is computed
    if view == TABS[0]:
        n = dg["network"]; k = st.columns(5)
        kpi(k[0], "Stops (nodes)", num(n["nodes"])); kpi(k[1], "Links between stops", num(n["edges"]), "consecutive-stop pairs + walkable interchanges")
        kpi(k[2], "Connected components", n["components_with_interchange"], f"{n['largest_component_share']:.1%} of stops in the main one")
        kpi(k[3], "Cut-vertex stops", n["cut_vertices"], "removal splits the network")
        kpi(k[4], "Thin-service stops", num(dg["thin_stops"]["n"]), dg["thin_stops"]["rule"])
        st.write("")
        iso = n.get("isolated_component_agencies", {})
        note(f"The only detached sub-network is <b>{', '.join(f'{a} ({c} stops)' for a, c in iso.items())}</b>: it does not connect to the BEST/TMT network within a 200 m walk. "
             "Passengers cannot make a scheduled bus-to-bus transfer between them with this feed.")
        c = stops[stops.in_greater_mumbai].sort_values("betweenness", ascending=False).head(25)
        L, R = st.columns([1, 1.2])
        with L:
            st.markdown("**Most critical stops (betweenness centrality)**")
            tb = c[["stop_name", "admin_ward", "n_routes", "departures_day", "betweenness", "is_cut_vertex"]].rename(columns={"stop_name": "Stop", "admin_ward": "Ward", "n_routes": "Routes", "departures_day": "Departures/day", "betweenness": "Betweenness", "is_cut_vertex": "Cut vertex"})
            st.dataframe(tb.style.format({"Departures/day": "{:,.0f}", "Betweenness": "{:.3f}"}), hide_index=True, width="stretch", height=470)
            st.caption("Betweenness approximated with 600 sampled sources (travel-time weights). High values = many shortest paths pass through the stop; disruption there hurts most.")
        with R:
            m = base_map(zoom=11)
            for r in c.itertuples():
                folium.CircleMarker((r.stop_lat, r.stop_lon), radius=5 + 120 * r.betweenness, color="#fff", weight=1, fill=True, fill_color="#B5707A", fill_opacity=.75, tooltip=f"{r.stop_name} · betweenness {r.betweenness:.3f}").add_to(m)
            st_folium(m, height=470, use_container_width=True, returned_objects=[], key="critmap")
    if view == TABS[1]:
        sc = dg["stop_clustering"]
        L, R = st.columns([1.5, 1])
        with L:
            m = base_map(zoom=11); sf = stops[stops.in_greater_mumbai & stops.stop_type.notna()]
            sf = sf.assign(col=sf.stop_type.map(STOP_COL).fillna("#41596E"), rad=np.where(sf.stop_type == "Local stops", 2.5, 5.0))
            points_layer(m, sf, "stop_lat", "stop_lon", ["stop_name", "stop_type", "n_routes", "departures_day"], ["Stop", "Type", "Routes", "Departures/day"], color_col="col", radius_col="rad", opacity=.8)
            st_folium(m, height=520, use_container_width=True, returned_objects=[], key="stypemap")
            st.markdown(" ".join(f'<span class="chip" style="background:{v}33">{k}</span>' for k, v in STOP_COL.items()), unsafe_allow_html=True)
        with R:
            pr = pd.DataFrame(sc["profile"]).T.reindex(["Major hubs", "Trunk-corridor stops", "Local stops"]).dropna(how="all")
            pr["stops"] = pd.Series(sc["sizes"])
            st.markdown("**Typology profile (averages)**"); st.dataframe(pr.rename(columns={"n_routes": "Routes", "departures_day": "Departures/day", "degree": "Links", "betweenness": "Betweenness", "stops": "Stops"})
                                                                        .style.format({"Routes": "{:.1f}", "Departures/day": "{:,.0f}", "Links": "{:.1f}", "Betweenness": "{:.3f}", "Stops": "{:,.0f}"}), width="stretch")
            sel = pd.DataFrame(sc["selection"]).T.reset_index().rename(columns={"index": "k"}); f = px.line(sel, x="k", y="silhouette", markers=True, title="Choosing k: silhouette score", color_discrete_sequence=["#3F7C85"])
            f.update_xaxes(dtick=1); st.plotly_chart(tidy(f, 250), width="stretch")
            note(f"K-means on log-scaled routes, departures, links, betweenness and local stop density (k = {sc['k']}, best silhouette {sc['selection'][str(sc['k'])]['silhouette']}). "
                 "Silhouette < 0.5 means a *continuum* rather than sharply separated groups - treat tiers as a descriptive typology.")
    if view == TABS[2]:
        rc = dg["route_clustering"]
        a = rs.dropna(subset=["route_type"]); f = px.scatter(a, x="length_km", y="trips_day", color="route_type", hover_data=["route_short_name", "agency_id", "span_h", "peak_trips_h"], log_x=True, log_y=True,
                                                             title="Routes: scheduled trips per day vs typical length", color_discrete_sequence=CAT, labels={"length_km": "typical length (km)", "trips_day": "trips per day"})
        L, R = st.columns([1.5, 1])
        with L: st.plotly_chart(tidy(f, 440), width="stretch")
        with R:
            st.markdown("**Route types (median values)**")
            pr = pd.DataFrame(rc["profile"]).T; pr["routes"] = pd.Series(rc["sizes"]); st.dataframe(pr.rename(columns={"trips_day": "Trips/day", "length_km": "Length km", "span_h": "Span h", "peak_trips_h": "Peak trips/h", "routes": "Routes"}).sort_values("Trips/day", ascending=False)
                                                                                                    .style.format("{:.1f}"), width="stretch")
            sq = rc["speed_quality"]
            note(f"Scheduled speeds were <b>excluded</b> from clustering: {sq['implausible_speed_routes']} of {sq['routes_with_speed']} routes show speeds outside 5-60 km/h (interpolated stop times).")
        low = a[a.route_type.isin(["Marginal routes", "Sparse / limited-span routes"])].sort_values("trips_day")
        st.markdown("**Routes with very limited service (review candidates)**")
        st.dataframe(low[["route_short_name", "agency_id", "route_long_name", "trips_day", "span_h", "peak_trips_h", "route_type"]].rename(columns={"route_short_name": "Route", "agency_id": "Operator", "route_long_name": "Description", "trips_day": "Trips/day", "span_h": "Span h", "peak_trips_h": "Peak trips/h", "route_type": "Type"})
                     .style.format({"Trips/day": "{:.0f}", "Span h": "{:.1f}", "Peak trips/h": "{:.1f}"}), hide_index=True, width="stretch", height=300)
    if view == TABS[3]:
        L, R = st.columns([1.35, 1])
        with L:
            view = st.radio("Colour prabhags by", ["Connectivity index (0-100)", "Archetype"], horizontal=True, key="n_view")
            m = base_map()
            if view.startswith("Connectivity"):
                _choropleth(m, d, ind[["prabhag", "pop", "connectivity_index"]].rename(columns={"connectivity_index": "cov"}), "cov", 0, 100, "{:.0f}/100")
            else:
                geo = {"type": "FeatureCollection", "features": []}; a = ind.set_index("prabhag")
                for f_ in d["prabhag_geo"]["features"]:
                    pr_ = f_["properties"]["prabhag"]; p = dict(f_["properties"]); p.update(label=f"Prabhag {pr_} ({a.admin_ward[pr_]})", arch=a.archetype[pr_], ci=f"{a.connectivity_index[pr_]:.0f}/100")
                    geo["features"].append({"type": "Feature", "geometry": f_["geometry"], "properties": p})
                folium.GeoJson(geo, style_function=lambda f: dict(fillColor=ARCH_COL.get(f["properties"]["arch"], "#999"), color="#fff", weight=.7, fillOpacity=.75),
                               tooltip=folium.GeoJsonTooltip(fields=["label", "arch", "ci"], aliases=["", "Archetype", "Index"], sticky=True)).add_to(m)
            for r in ind[ind.low_connectivity_hotspot].itertuples():
                folium.CircleMarker((r.lat, r.lon), radius=4, color="#8F4A45", weight=2, fill=False, tooltip=f"Hotspot: prabhag {r.prabhag}").add_to(m)
            st_folium(m, height=520, use_container_width=True, returned_objects=[], key="idxmap")
            st.caption("Red rings = low-connectivity hotspots (bottom-quartile prabhag whose neighbours are also low).")
        with R:
            sp = dg["spatial_autocorrelation"]; sn = dg["index_sensitivity"]
            st.markdown(f"**Spatial clustering:** Moran's I = **{sp['morans_I']:.2f}** (p = {sp['p_value']:.3f}) - weak-connectivity prabhags are geographically clustered, not scattered.")
            st.markdown(f"**Index robustness:** across 1,000 random weightings the ranking keeps a median Spearman ρ of **{sn['spearman_median']:.2f}** (5th percentile {sn['spearman_p5']:.2f}) against the equal-weight index.")
            pc = pd.DataFrame(dg["prabhag_clustering"]["profile"]).T; pc["prabhags"] = pd.Series(dg["prabhag_clustering"]["sizes"])
            st.markdown("**Archetypes**"); st.dataframe(pc.reindex(list(ARCH_COL)).rename(columns={"pop": "Avg pop.", "cov_500": "Coverage 500 m", "trips_peak_h_500_popw": "Peak trips/h", "connectivity_index": "Index", "pop_density_km2": "Density /km²", "prabhags": "Prabhags"})
                                                       .style.format({"Avg pop.": "{:,.0f}", "Coverage 500 m": "{:.0%}", "Peak trips/h": "{:.0f}", "Index": "{:.0f}", "Density /km²": "{:,.0f}", "Prabhags": "{:.0f}"}), width="stretch")
            st.caption(f"K-means (k = {dg['prabhag_clustering']['k']}, k ≥ 4 imposed for a usable typology), run-to-run stability ARI = {dg['prabhag_clustering']['stability_ari_mean']:.2f}; silhouette {dg['prabhag_clustering']['selection'][str(dg['prabhag_clustering']['k'])]['silhouette']}.")
        st.markdown("**Inspect a prabhag**")
        opts = ind.sort_values("prabhag"); pick = st.selectbox("Prabhag", opts.prabhag.tolist(), format_func=lambda p: f"Prabhag {p} · ward {opts[opts.prabhag == p].admin_ward.iat[0]}", key="n_pick")
        r = ind[ind.prabhag == pick].iloc[0]
        cols = [c for c in ind.columns if c.startswith("ci_")]
        labs = {"ci_stop_coverage": "Stop coverage", "ci_walk_distance": "Walk distance", "ci_peak_service": "Peak service", "ci_route_choice": "Route choice", "ci_network_reach": "Network reach (45 min)", "ci_essential-facility_reach": "Facility reach", "ci_essential_facility_reach": "Facility reach"}
        a, b = st.columns([1, 1.2])
        with a:
            kk = st.columns(2); kpi(kk[0], "Connectivity index", f"{r.connectivity_index:.0f}/100", r.archetype); kpi(kk[1], "Coverage ≤ 500 m", pct(r.cov_500), f"{num(r['pop'])} residents")
            st.markdown(f"<span class='chip'>{r.urban_density_flag}</span>", unsafe_allow_html=True)
            st.caption(f"Nearest college by 09:00 bus: {'none within 75 min' if pd.isna(r.college_nearest_min) else f'{r.college_nearest_min:.0f} min'} · nearest public hospital: {'none within 75 min' if pd.isna(r.public_hospital_nearest_min) else f'{r.public_hospital_nearest_min:.0f} min'}.")
        with b:
            vals = pd.DataFrame({"Component (percentile among 227 prabhags)": [labs.get(c, c) for c in cols], "Percentile": [r[c] for c in cols]})
            f = px.bar(vals, x="Percentile", y="Component (percentile among 227 prabhags)", orientation="h", range_x=[0, 100], color_discrete_sequence=["#3F7C85"]); st.plotly_chart(tidy(f, 270), width="stretch")
    if view == TABS[4]:
        g = dg["gaps"]; k = st.columns(4)
        kpi(k[0], "No stop within 500 m", num(g["pop_no_stop_500"]), pct(g["pop_no_stop_500"] / g["pop_total"]) + " of residents")
        kpi(k[1], "No stop within 800 m", num(g["pop_no_stop_800"]), pct(g["pop_no_stop_800"] / g["pop_total"]) + " of residents")
        kpi(k[2], "Covered but low peak service", num(g["pop_low_service"]), "< 4 trips per hour in AM peak")
        kpi(k[3], "25 new catchments would reach", num(g["top25_sites_cover_pop"]), pct(g["top25_sites_cover_pop"] / g["pop_no_stop_500"]) + " of the unserved")
        st.write("")
        L, R = st.columns([1, 1.2])
        with L:
            st.subheader("Recommendations")
            pri = pd.DataFrame(dg["priority_areas"])
            st.markdown(f"1. **Fill the largest coverage holes first.** The five highest-ranked new stop catchments alone would bring {num(sites.newly_covered_pop.head(5).sum())} residents within 500 m of a stop (map →).")
            st.markdown("2. **Prioritise dense prabhags with the most unserved residents:** " + ", ".join(f"{r.area} (~{num(r.uncovered_500)})" for r in pri.head(4).itertuples()) + ".")
            st.markdown(f"3. **Target hotspots, not single prabhags.** {int(ind.low_connectivity_hotspot.sum())} prabhags form low-connectivity clusters (Moran's I = {dg['spatial_autocorrelation']['morans_I']:.2f}); coordinated route extensions along these corridors will help more than isolated stops.")
            st.markdown(f"4. **Check the {dg['thin_stops']['n']} thin-service stops** (one route, fewer than 20 departures a day) and the {int((rs.route_type == 'Marginal routes').sum())} marginal routes for consolidation or frequency upgrades.")
            st.markdown("5. **Protect critical interchanges** - the top betweenness stops carry disproportionate shortest paths; disruption plans should start there.")
            st.markdown("6. **Link Vasai-Virar to the main network** by a physical interchange - today no scheduled transfer exists in the feed.")
            note("Suggested catchments come from a greedy maximum-coverage search over a 100 m population grid. They are <b>planning prompts</b>, not engineered stop locations - road access and land use must be checked on site.")
        with R:
            m = base_map(zoom=11)
            for r in ind.itertuples():
                pass
            u = d["cells"][~d["cells"].covered_500]
            folium.GeoJson(d["prabhag_geo"], style_function=lambda f: dict(fillColor="#E9E4D8", color="#FFFFFF", weight=.6, fillOpacity=.5)).add_to(m)
            for r in sites.itertuples():
                folium.Circle((r.lat, r.lon), radius=500, color="#B8795A", weight=1.5, fill=True, fill_opacity=.18).add_to(m)
                folium.Marker((r.lat, r.lon), icon=folium.DivIcon(html=f'<div style="background:#B8795A;color:#fff;border-radius:50%;width:22px;height:22px;text-align:center;line-height:22px;font-size:11px;border:2px solid #fff">{r.rank}</div>'),
                              tooltip=f"#{r.rank} · +{r.newly_covered_pop:,.0f} residents · prabhag {r.prabhag} (ward {r.admin_ward})").add_to(m)
            st_folium(m, height=470, use_container_width=True, returned_objects=[], key="sitemap")
        tb = sites.rename(columns={"rank": "Rank", "lat": "Latitude", "lon": "Longitude", "newly_covered_pop": "Residents newly covered", "prabhag": "Prabhag", "admin_ward": "Ward", "cum_share_of_uncovered": "Cumulative share of unserved"})
        st.dataframe(tb[["Rank", "Prabhag", "Ward", "Latitude", "Longitude", "Residents newly covered", "Cumulative share of unserved"]].style.format({"Latitude": "{:.4f}", "Longitude": "{:.4f}", "Residents newly covered": "{:,.0f}", "Cumulative share of unserved": "{:.1%}"}), hide_index=True, width="stretch", height=300)
        st.download_button("Download suggested catchments (CSV)", tb.to_csv(index=False).encode(), "suggested_new_stop_catchments.csv", "text/csv")
        pri = ind.sort_values("pop_uncovered_500", ascending=False)[["prabhag", "admin_ward", "pop", "cov_500", "pop_uncovered_500", "connectivity_index", "archetype", "urban_density_flag"]]
        st.download_button("Download full prabhag priority table (CSV)", pri.to_csv(index=False).encode(), "prabhag_priority.csv", "text/csv")
