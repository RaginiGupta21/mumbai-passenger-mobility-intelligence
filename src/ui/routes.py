import datetime as dt
import folium, numpy as np, pandas as pd, plotly.express as px, streamlit as st
from streamlit_folium import st_folium
from .style import hero, kpi, note, num
from .charts import tidy
from ..common import s_to_hm
from ..maps import base_map, fit


def _hhmm(sec):
    return s_to_hm(sec)


def render(d, tt):
    hero("Routes & Schedule Analysis", "Explore bus routes, their stops, scheduled trips and when service is available.")
    t1, t2, t3 = st.tabs(["Route explorer", "Stop departure board", "Service availability"])
    rs = d["routes"].copy()
    with t1:
        c = st.columns([1, 3])
        ag = c[0].multiselect("Operator", sorted(rs.agency_id.unique()), key="r_ag", placeholder="All operators")
        sub = rs[rs.agency_id.isin(ag)] if ag else rs
        sub = sub.assign(opt=sub.route_short_name + " · " + sub.agency_id + " · " + sub.route_long_name.str.slice(0, 70)).sort_values("route_short_name")
        sel = c[1].selectbox("Route (type a number or place name)", sub.opt.tolist(), key="r_sel")
        r = sub[sub.opt == sel].iloc[0]; ridx = int(r.route_idx)
        k = st.columns(6)
        kpi(k[0], "Trips / day", num(r.trips_day), r.route_type if isinstance(r.route_type, str) else "&nbsp;")
        kpi(k[1], "Service span", f"{_hhmm(r.first_dep)}-{_hhmm(r.last_dep)}", f"{r.span_h:.1f} h")
        kpi(k[2], "Peak headway", f"{r.headway_peak_min:.0f} min" if pd.notna(r.headway_peak_min) else "n/a", "08-10h, all directions combined")
        kpi(k[3], "Typical length", f"{r.length_km:.1f} km", f"{r.median_stops:.0f} stops")
        kpi(k[4], "Typical run time", f"{r.median_dur_min:.0f} min")
        kpi(k[5], "Scheduled speed", f"{r.sched_speed_kmh:.0f} km/h" if pd.notna(r.sched_speed_kmh) else "n/a", "⚠ unreliable" if not r.get("speed_plausible", True) else "plausible")
        trips = d["trips"][d["trips"].route_idx == ridx]
        pats = trips.trip_idx.map(lambda t: int(tt.trip_pattern[t])).value_counts()
        S = tt.stops
        def plabel(p):
            s = tt.pat_stops[p]; return f"{S.stop_name.iat[s[0]]} → {S.stop_name.iat[s[-1]]} ({pats[p]} trips, {len(s)} stops)"
        p = st.selectbox("Direction / stop pattern", pats.index.tolist(), format_func=plabel, key="r_pat")
        stops_p = tt.pat_stops[p]
        L, R = st.columns([1.2, 1])
        with L:
            m = base_map(); pts = [(float(S.stop_lat.iat[i]), float(S.stop_lon.iat[i])) for i in stops_p]
            folium.PolyLine(pts, color="#3F7C85", weight=5, opacity=.85).add_to(m)
            for n, (i, (la, lo)) in enumerate(zip(stops_p, pts)):
                folium.CircleMarker((la, lo), radius=4 if 0 < n < len(pts) - 1 else 8, color="#fff", weight=1, fill=True, fill_opacity=1,
                                    fill_color="#B8795A" if n in (0, len(pts) - 1) else "#41596E", tooltip=f"{n + 1}. {S.stop_name.iat[i]}").add_to(m)
            fit(m, pts); st_folium(m, height=430, use_container_width=True, returned_objects=[], key=f"rmap{ridx}_{p}")
            st.caption("Lines join the stops in order - the feed has no route-shape geometry.")
        with R:
            dep0 = tt.pat_dep[p][:, 0]
            tid = tt.pat_trip[p]
            trip_labels = [_hhmm(x) for x in dep0]
            ti = st.selectbox("Scheduled trip (departure from first stop)", range(len(dep0)), format_func=lambda i, tl=trip_labels: tl[i], key=f"r_trip{ridx}_{p}")
            tbl = pd.DataFrame({"#": np.arange(1, len(stops_p) + 1), "Stop": [S.stop_name.iat[i] for i in stops_p], "Arrive": [_hhmm(x) for x in tt.pat_arr[p][ti]],
                                "Depart": [_hhmm(x) for x in tt.pat_dep[p][ti]], "Official timepoint": ""})
            st.dataframe(tbl.drop(columns="Official timepoint"), hide_index=True, width="stretch", height=400)
        hf = d["trip_first"].reindex(trips.trip_idx).dropna() // 3600
        h = hf.value_counts().sort_index().reindex(range(0, 30), fill_value=0)
        f = px.bar(x=h.index, y=h.values, title="Scheduled departures by hour (all variants of this route)", color_discrete_sequence=["#3F7C85"])
        f.update_layout(xaxis_title="hour of service day (24+ = after midnight)", yaxis_title="trips"); st.plotly_chart(tidy(f, 260), width="stretch")
        st.markdown("**Timetable (departures from the first stop)**")
        by = pd.Series(dep0).map(lambda x: x // 3600)
        tt_txt = pd.DataFrame({"Hour": [f"{h:02d}:00" for h in sorted(by.unique())],
                               "Departures": [" · ".join(f"{(x % 3600) // 60:02d}" for x in sorted(dep0[by == h])) for h in sorted(by.unique())]})
        st.dataframe(tt_txt, hide_index=True, width="stretch", height=min(35 * len(tt_txt) + 40, 420))
        note("Minutes shown are the scheduled departure minute within each hour. Intermediate stop times in this feed are mostly interpolated (only ~7% are official timepoints).")

    with t2:
        pl = d["places"]; v0, v1 = tt.feed_validity()
        c = st.columns([2, 1, 1])
        place_labels = pl[pl.in_gm].label.tolist() + pl[~pl.in_gm].label.tolist()
        lab = c[0].selectbox("Stop or area", place_labels, index=place_labels.index("Dadar Station (E)") if "Dadar Station (E)" in place_labels else 0, key="b_p")
        day = c[1].date_input("Date", min(max(dt.date.today(), v0), v1), min_value=v0, max_value=v1, key="b_d")
        tm = c[2].time_input("From", dt.time(9, 0), key="b_t", step=300)
        place = pl[pl.label == lab].iloc[0]; sd = tt.service_day(day); t0 = tm.hour * 3600 + tm.minute * 60
        rows = []
        for s in place.stop_idx:
            for pidx, i in tt.stop_patterns[s]:
                if i == len(tt.pat_stops[pidx]) - 1: continue            # terminal stop: arrivals only
                v = sd.view(pidx)
                if v is None: continue
                col = v.dep[:, i]; ok = np.flatnonzero(col >= t0)[:6]
                for j in ok:
                    tr = int(v.trip[j]); rr = int(tt.trip_route[tr])
                    rows.append(dict(dep=int(col[j]), Route=str(tt.route_name[rr]), Operator=tt.route_agency[rr], Towards=str(tt.trip_head[tr]), Stop=S.stop_name.iat[int(s)]))
        if rows:
            df = pd.DataFrame(rows).sort_values("dep").head(25); df["Departs"] = df.dep.map(_hhmm); df["In (min)"] = ((df.dep - t0) / 60).round(0).astype(int)
            st.dataframe(df[["Departs", "In (min)", "Route", "Operator", "Towards", "Stop"]], hide_index=True, width="stretch", height=420)
        else:
            st.info("No scheduled departures after that time at this place on the chosen date.")
        # hourly frequency
        allrows = []
        for s in place.stop_idx:
            for pidx, i in tt.stop_patterns[s]:
                v = sd.view(pidx)
                if v is not None and i < len(tt.pat_stops[pidx]) - 1: allrows += list(v.dep[:, i] // 3600)
        if allrows:
            h = pd.Series(allrows).value_counts().sort_index(); h = h[(h >= 0)]
            f = px.bar(x=h.index, y=h.values, title=f"Scheduled departures per hour at {lab} (all {len(place.stop_idx)} stop(s))", color_discrete_sequence=["#41596E"])
            f.update_layout(xaxis_title="hour", yaxis_title="departures"); st.plotly_chart(tidy(f, 260), width="stretch")
            st.caption(f"{len(set(r['Route'] for r in rows)) if rows else 0} routes in the next-departure list · {sum(len(tt.stop_patterns[s]) for s in place.stop_idx)} route-pattern calls at this place.")

    with t3:
        v0, v1 = tt.feed_validity()
        day = st.date_input("Check a date", min(max(dt.date.today(), v0), v1), min_value=v0 - dt.timedelta(days=60), max_value=v1 + dt.timedelta(days=60), key="sa_d")
        codes = tt.active_service_codes(day)
        if len(codes):
            st.success(f"Service runs on {day:%A %d %B %Y}: {len(codes)} active service pattern(s). In this feed the same timetable applies on all 7 days.")
        else:
            st.error(f"No scheduled service in the feed for {day:%d %B %Y} (feed valid {v0:%d %b %Y} - {v1:%d %b %Y}).")
        tf = d["trip_first"]; h = (tf // 3600).value_counts().sort_index().reindex(range(0, 30), fill_value=0)
        f = px.area(x=h.index, y=h.values, title="Network-wide scheduled trip starts by hour", color_discrete_sequence=["#3F7C85"])
        f.update_layout(xaxis_title="hour of service day", yaxis_title="trips starting"); st.plotly_chart(tidy(f, 300), width="stretch")
        a = d["routes"].groupby("agency_id").agg(routes=("route_id", "size"), trips=("trips_day", "sum"), median_headway=("headway_peak_min", "median"), median_span_h=("span_h", "median")).reset_index()
        st.dataframe(a.rename(columns={"agency_id": "Operator", "routes": "Active routes", "trips": "Trips/day", "median_headway": "Median peak headway (min)", "median_span_h": "Median span (h)"})
                     .style.format({"Trips/day": "{:,.0f}", "Median peak headway (min)": "{:.0f}", "Median span (h)": "{:.1f}"}), hide_index=True, width="stretch")
        st.caption(f"{d['dq']['integrity']['routes_without_trips']} routes listed in routes.txt have no scheduled trips and are excluded here.")
