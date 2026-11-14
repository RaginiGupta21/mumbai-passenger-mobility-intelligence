import datetime as dt
import folium, pandas as pd, plotly.graph_objects as go, streamlit as st
from streamlit_folium import st_folium
from .charts import tidy
from .. import fares
from ..nearest import nearest_stops
from .style import hero, kpi, note
from ..config import *
from ..common import s_to_hm, fmt_dur
from ..journey import endpoint_from_place, endpoint_from_point, plan, reachable, time_breakdown
from ..maps import base_map, fit, LEG_COLORS, ramp, points_layer


def _picker(prefix, title, d, tt, default_label):
    st.markdown(f"**{title}**")
    kind = st.radio("Type", ["Bus stop / place", "College or university", "Public health facility"], key=f"{prefix}_kind", horizontal=True, label_visibility="collapsed")
    pl, fac = d["places"], d["fac"]
    if kind == "Bus stop / place":
        labels = pl[pl.in_gm].label.tolist() + pl[~pl.in_gm].label.tolist()
        idx = labels.index(default_label) if default_label in labels else 0
        lab = st.selectbox("Search a stop or area", labels, index=idx, key=f"{prefix}_place", help="Type to search. Stops with the same name within 600 m are grouped as one place.")
        return endpoint_from_place(tt, pl[pl.label == lab].iloc[0])
    sub = fac[(fac.group == "Education")] if kind.startswith("College") else fac[(fac.group == "Health") & fac.usable & (fac.category != "Dispensary")]
    sub = sub.sort_values("name"); sub = sub.assign(opt=sub.name + " (" + sub.category + ")")
    lab = st.selectbox("Search a facility", sub.opt.tolist(), key=f"{prefix}_fac")
    r = sub[sub.opt == lab].iloc[0]
    if r.precision != "precise":
        st.caption("Location in the source data is rounded (~±0.5 km): walking time to the nearest stop is approximate.")
    return endpoint_from_point(tt, r["name"], r.lat, r.lon, r.x, r.y)


def _timeline(j):
    for l in j["legs"]:
        if l["kind"] == "walk":
            st.markdown(f'<div class="leg walk">🚶 <div><b>Walk {l["mins"]:.0f} min</b> (~{l["metres"]:.0f} m)<br><span style="color:#6B7B83">{l["from_name"]} → {l["to_name"]}</span></div></div>', unsafe_allow_html=True)
        else:
            st.markdown(f'<div class="leg">🚌 <div><b>Bus {l["route"]}</b> <span class="chip">{l["agency"]}</span> towards <i>{l["headsign"]}</i><br>'
                        f'<b>{s_to_hm(l["dep"])}</b> {l["board"]}<br><b>{s_to_hm(l["arr"])}</b> {l["alight"]} · {l["n_stops"]} stops · ~{l["mins"]:.0f} min on board</div></div>', unsafe_allow_html=True)


def _map(j, o, dst):
    m = base_map()
    pts = []; ci = 0
    for l in j["legs"]:
        pts += l["coords"]
        if l["kind"] == "walk":
            folium.PolyLine(l["coords"], color="#B9A67C", weight=4, dash_array="6 8", tooltip=f"Walk {l['mins']:.0f} min").add_to(m)
        else:
            col = LEG_COLORS[ci % len(LEG_COLORS)]; ci += 1
            folium.PolyLine(l["coords"], color=col, weight=6, opacity=.85, tooltip=f"Bus {l['route']} ({s_to_hm(l['dep'])}-{s_to_hm(l['arr'])})").add_to(m)
            for k, (la, lo) in enumerate(l["coords"]):
                folium.CircleMarker((la, lo), radius=2.5, color=col, fill=True, fill_opacity=1, weight=1).add_to(m)
            folium.CircleMarker(l["coords"][0], radius=7, color="#fff", weight=2, fill=True, fill_color=col, fill_opacity=1, tooltip=f"Board {l['board']} {s_to_hm(l['dep'])}").add_to(m)
            folium.CircleMarker(l["coords"][-1], radius=7, color="#fff", weight=2, fill=True, fill_color=col, fill_opacity=1, tooltip=f"Alight {l['alight']} {s_to_hm(l['arr'])}").add_to(m)
    folium.Marker((o.lat, o.lon), tooltip="Origin: " + o.label, icon=folium.Icon(color="green", icon="play", prefix="fa")).add_to(m)
    folium.Marker((dst.lat, dst.lon), tooltip="Destination: " + dst.label, icon=folium.Icon(color="red", icon="flag", prefix="fa")).add_to(m)
    fit(m, pts)
    return m


def _summary(j, r):
    bd = time_breakdown(j, r["t0"])
    st.markdown("##### Time summary (door to door)")
    L, R = st.columns([1.5, 1])
    parts = [("Walk to first stop", bd["access_walk"], "#D9C7A3"), ("On board", bd["onboard"], "#3F7C85"), ("Waiting between buses", bd["transfer_wait"], "#B8795A"),
             ("Walking between stops", bd["transfer_walk"], "#C9A25B"), ("Walk to destination", bd["egress_walk"], "#8FB3A5")]
    fig = go.Figure()
    for name, v, col in parts:
        if v >= 0.5:
            fig.add_trace(go.Bar(y=[""], x=[v], orientation="h", name=f"{name}: {v:.0f} min", marker_color=col, text=f"{v:.0f}", textposition="inside"))
    fig.update_layout(barmode="stack", xaxis_title="minutes", yaxis_visible=False, legend=dict(orientation="h", y=-0.45))
    with L: st.plotly_chart(tidy(fig, 190), width="stretch")
    with R:
        st.markdown(f"**Leave by {s_to_hm(j['leave'])}** ({bd['leave_after_min']:.0f} min after your chosen time)  \n"
                    f"**Arrive {s_to_hm(j['arrive'])}**  \n**Door to door: {fmt_dur(j['duration_s'])}**  \n"
                    f"Walking {bd['access_walk'] + bd['transfer_walk'] + bd['egress_walk']:.0f} min · riding {bd['onboard']:.0f} min · waiting {bd['transfer_wait']:.0f} min")
    f = fares.estimate(j["legs"])
    with st.expander("Indicative fare (BEST legs only) - read the caveats"):
        if f["best_legs"] == 0:
            st.write("No BEST legs in this journey. " + (f"Operators {', '.join(f['other_operators'])} use fares that are not modelled." if f["other_operators"] else ""))
        else:
            c = st.columns(2)
            c[0].metric("Non-AC buses", fares.fmt_range(f["non_ac"])); c[1].metric("AC buses", fares.fmt_range(f["ac"]))
            if f["other_legs"]: st.caption(f"{f['other_legs']} leg(s) by {', '.join(f['other_operators'])} are not included.")
        t = fares.table()
        st.markdown(f"**Not an official fare.** {t['status']}  \n{t['as_of']}  \n" + "  \n".join("• " + n for n in t["notes"]))


def render(d, tt):
    hero("Passenger Journey Explorer", "Pick where you are going and when - see scheduled bus connections, transfers, stops and journey time.")
    v0, v1 = tt.feed_validity()
    tab1, tab2, tab3 = st.tabs(["Plan a journey", "Where can I reach?", "Nearest bus stops"])
    today = dt.date.today(); default_date = min(max(today, v0), v1)
    with tab1:
        c1, c2 = st.columns(2)
        with c1: o = _picker("o", "From", d, tt, "Mumbai Central Station")
        with c2: dst = _picker("d", "To", d, tt, "Malad Station (W)")
        c3, c4, c5, c6 = st.columns([1, 1, 1, 1])
        date = c3.date_input("Date", default_date, min_value=v0, max_value=v1, key="j_date", help=f"Timetable feed valid {v0:%d %b %Y} - {v1:%d %b %Y}")
        tm = c4.time_input("Leave after", dt.time(9, 0), key="j_time", step=300)
        nopt = c5.slider("Options", 2, 6, 4, key="j_n")
        maxtr = c6.slider("Max transfers", 0, 4, 3, key="j_tr")
        go = st.button("Find scheduled journeys", type="primary", width="content")
        if go:
            with st.spinner("Searching the timetable..."):
                js, warns = plan(tt, o, dst, date, tm.hour * 3600 + tm.minute * 60, n_options=nopt, max_rounds=maxtr + 1)
            st.session_state["jr"] = dict(js=js, warns=warns, o=o, d=dst, date=date, t0=tm.hour * 3600 + tm.minute * 60)
        r = st.session_state.get("jr")
        if r:
            for w in r["warns"]: st.warning(w)
            js = r["js"]
            if js:
                st.markdown(f"##### {r['o'].label} → {r['d'].label} · {r['date']:%a %d %b %Y}")
                sel = st.radio("Journey options", range(len(js)), horizontal=True, key="j_sel",
                               format_func=lambda i, js=js: f"{s_to_hm(js[i]['leave'])} → {s_to_hm(js[i]['arrive'])} · {fmt_dur(js[i]['duration_s'])} · {js[i]['transfers']} transfer{'s' if js[i]['transfers'] != 1 else ''}")
                sel = min(sel, len(js) - 1); j = js[sel]
                k = st.columns(5)
                kpi(k[0], "Total time", fmt_dur(j["duration_s"]), " ".join(j.get("tags", [])) or "&nbsp;")
                kpi(k[1], "Transfers", j["transfers"]); kpi(k[2], "On board", f"{j['bus_min']:.0f} min")
                kpi(k[3], "Walking", f"{j['walk_min']:.0f} min", "estimated, straight-line × 1.3"); kpi(k[4], "Waiting", f"{j['wait_min']:.0f} min", "between buses")
                st.write("")
                _summary(j, r)
                a, b = st.columns([1, 1.25])
                with a: _timeline(j)
                with b: st_folium(_map(j, r["o"], r["d"]), height=470, use_container_width=True, returned_objects=[], key=f"jmap{sel}")
        note("<b>Scheduled, not live.</b> Times come from the published timetable; buses may run late. In this feed only ~7% of stop times are official "
             "timepoints - intermediate times are interpolated, so treat them as ±5 min. Walking uses a 1.2 m/s pace and a 1.3 street-detour factor; no road network is used. "
             "Lines join stops in order (the feed has no route shapes).")
    with tab2:
        st.markdown("**How far can I get from a single starting point?**")
        o2 = _picker("r", "Start from", d, tt, "Dadar Station (E)")
        c = st.columns(3)
        dd = c[0].date_input("Date", default_date, min_value=v0, max_value=v1, key="r_date")
        tt0 = c[1].time_input("Depart at", dt.time(9, 0), key="r_time", step=300)
        mins = c[2].select_slider("Travel time budget (min)", [15, 30, 45, 60, 75, 90], 45, key="r_min")
        if st.button("Show reachable stops", type="primary"):
            with st.spinner("Computing earliest arrival to every stop..."):
                df = reachable(tt, o2, dd, tt0.hour * 3600 + tt0.minute * 60, mins)
            st.session_state["reach"] = dict(df=df, o=o2, mins=mins)
        rr = st.session_state.get("reach")
        if rr is not None:
            df = rr["df"]; gmstops = d["stops"][d["stops"].in_greater_mumbai]
            k = st.columns(3)
            kpi(k[0], "Stops reachable", f"{len(df):,}", f"within {rr['mins']} min (incl. walking to first stop)")
            kpi(k[1], "…inside Greater Mumbai", f"{df.stop_idx.isin(gmstops.stop_idx).sum():,}", f"{df.stop_idx.isin(gmstops.stop_idx).sum() / len(gmstops):.0%} of its stops")
            kpi(k[2], "Median travel time", f"{df.minutes.median():.0f} min" if len(df) else "-")
            m = base_map()
            df = df.assign(col=[ramp(v, 0, rr["mins"], ("#2F4F63", "#3F7C85", "#8FB3A5", "#D9C7A3", "#E3B88C")) for v in df.minutes], min_txt=df.minutes.round(0).astype(int))
            points_layer(m, df, "stop_lat", "stop_lon", ["stop_name", "min_txt"], ["Stop", "Minutes"], color_col="col", radius=3.5, opacity=.85)
            folium.Marker((rr["o"].lat, rr["o"].lon), icon=folium.Icon(color="green", icon="play", prefix="fa"), tooltip=rr["o"].label).add_to(m)
            m.location = [rr["o"].lat, rr["o"].lon]; m.options["zoom"] = 11
            st_folium(m, height=520, use_container_width=True, returned_objects=[], key="reachmap")
            st.caption("Darker = quicker to reach. Up to 3 transfers; scheduled times only.")

    with tab3:
        st.markdown("**Which bus stops are near me - and how far is the walk?**")
        mode = st.radio("Where are you?", ["Click on the map", "Type coordinates", "Pick a place or facility"], horizontal=True, key="nn_mode")
        c = st.columns(3)
        nd = c[0].date_input("Date", default_date, min_value=v0, max_value=v1, key="nn_date"); ntm = c[1].time_input("Time", dt.time(9, 0), key="nn_time", step=300)
        kk = c[2].slider("How many stops", 3, 10, 5, key="nn_k")
        pt = None; res = None
        if mode == "Type coordinates":
            cc = st.columns(2)
            la = cc[0].number_input("Latitude", 18.5, 19.8, 19.0760, format="%.5f", key="nn_lat"); lo = cc[1].number_input("Longitude", 72.5, 73.3, 72.8777, format="%.5f", key="nn_lon")
            st.caption("Tip: in Google Maps, right-click a spot and click the coordinates to copy them.")
            pt = (la, lo)
        elif mode == "Pick a place or facility":
            e = _picker("n", "Pick", d, tt, "Dadar Station (E)"); pt = (e.lat, e.lon)
        else:
            pt = st.session_state.get("nn_pt")
            if pt is None: st.info("Click anywhere on the map to drop a pin.")
        if pt is not None:
            if not (18.5 <= pt[0] <= 19.8 and 72.5 <= pt[1] <= 73.3):
                st.warning("That point is outside the Mumbai region covered by the timetable feed.")
            else:
                sd = tt.service_day(nd)
                res = nearest_stops(tt, pt[0], pt[1], kk, sd, ntm.hour * 3600 + ntm.minute * 60)
                n0 = res.iloc[0]
                k = st.columns(4)
                kpi(k[0], "Nearest stop", f"{n0.distance_m:.0f} m", n0.stop); kpi(k[1], "Walking time", f"{n0.walk_min:.0f} min", "straight line × 1.3 at 1.2 m/s")
                kpi(k[2], "Routes at that stop", int(n0.n_routes)); kpi(k[3], f"Stops within 500 m", int((res.distance_m <= 500).sum()), f"of the {kk} nearest")
                if n0.distance_m > 800:
                    st.warning("No bus stop within 800 m of this spot - this is a coverage gap (see Accessibility & Inclusion).")
                elif n0.distance_m > 500:
                    st.info("The nearest stop is more than 500 m away - beyond the usual comfortable walking distance.")
        if mode == "Click on the map" or pt is not None:
            m = base_map(center=list(pt) if pt else None, zoom=15 if pt else 11)
            if pt is not None and res is not None:
                folium.Marker(pt, icon=folium.Icon(color="green", icon="user", prefix="fa"), tooltip="You are here").add_to(m)
                for i, r_ in enumerate(res.itertuples()):
                    folium.PolyLine([pt, (r_.lat, r_.lon)], color="#B9A67C", weight=3, dash_array="5 7").add_to(m)
                    folium.CircleMarker((r_.lat, r_.lon), radius=9, color="#fff", weight=2, fill=True, fill_color="#3F7C85" if i == 0 else "#41596E", fill_opacity=1,
                                        tooltip=f"{i + 1}. {r_.stop} · {r_.distance_m:.0f} m · {r_.walk_min:.0f} min walk").add_to(m)
            out = st_folium(m, height=430, use_container_width=True, returned_objects=["last_clicked"] if mode == "Click on the map" else [], key=f"nnmap_{mode}")
            if mode == "Click on the map" and out and out.get("last_clicked"):
                new = (round(out["last_clicked"]["lat"], 6), round(out["last_clicked"]["lng"], 6))
                if new != st.session_state.get("nn_pt"):
                    st.session_state["nn_pt"] = new; st.rerun()
        if res is not None:
            tb = res.rename(columns={"stop": "Stop", "operator": "Operator", "distance_m": "Distance (m)", "walk_min": "Walk (min)", "n_routes": "Routes", "routes": "Route numbers", "next_departures": "Next scheduled departures"})
            st.dataframe(tb[["Stop", "Operator", "Distance (m)", "Walk (min)", "Routes", "Route numbers", "Next scheduled departures"]].style.format({"Distance (m)": "{:.0f}", "Walk (min)": "{:.0f}"}), hide_index=True, width="stretch")
            st.caption("Distances are straight-line from the pin; the walking time uses a 1.3 street-detour factor. Departures are scheduled, not live.")
