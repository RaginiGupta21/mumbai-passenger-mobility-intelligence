"""Passenger journey planning API on top of RAPTOR. Scheduled timetable only - no live data."""
from __future__ import annotations
import datetime as dt
from dataclasses import dataclass, field
import numpy as np, pandas as pd
from .config import *
from .raptor import raptor, pareto_journeys, INF
from .common import s_to_hm, fmt_dur


@dataclass
class Endpoint:
    label: str; lat: float; lon: float; stops: dict          # stop_idx -> (walk_seconds, straight_m)


def endpoint_from_place(tt, place, extra_m=250) -> Endpoint:
    links = tt.walk_links(place.x, place.y, max_m=extra_m, max_n=14)
    for s in place.stop_idx:                       # the place's own stops are zero-walk
        links[int(s)] = (0.0, 0.0)
    return Endpoint(place.label, float(place.lat), float(place.lon), links)


def endpoint_from_point(tt, label, lat, lon, x, y, max_m=700) -> Endpoint:
    return Endpoint(label, lat, lon, tt.walk_links(x, y, max_m=max_m, max_n=10))


def _coords(tt, stops_idx):
    S = tt.stops
    return [(float(S.stop_lat.iat[i]), float(S.stop_lon.iat[i])) for i in stops_idx]


def _build(tt, sd, o: Endpoint, d: Endpoint, j, t0: int):
    S = tt.stops; name = lambda i: S.stop_name.iat[int(i)]
    legs = []
    first_trip = next(l for l in j["legs"] if l["kind"] == "trip")
    acc_w = o.stops[j["source_stop"]][0] if j["source_stop"] in o.stops else 0
    first_stop = j["legs"][0]["board_stop"] if j["legs"][0]["kind"] == "trip" else j["legs"][0]["from_stop"]
    acc_m = o.stops.get(j["source_stop"], (0, 0))[1]
    if acc_w > 5:
        legs.append(dict(kind="walk", role="access", mins=acc_w / 60, metres=acc_m, from_name=o.label, to_name=name(j["source_stop"]),
                         coords=[(o.lat, o.lon)] + _coords(tt, [j["source_stop"]])))
    for l in j["legs"]:
        if l["kind"] == "walk":
            legs.append(dict(kind="walk", role="transfer", mins=l["secs"] / 60, metres=l["secs"] * WALK_SPEED_MS / DETOUR_FACTOR, from_name=name(l["from_stop"]),
                             to_name=name(l["to_stop"]), coords=_coords(tt, [l["from_stop"], l["to_stop"]])))
        else:
            p = l["pattern"]; seq = tt.pat_stops[p][l["board_pos"]:l["alight_pos"] + 1]
            r = int(tt.trip_route[l["trip_idx"]])
            xy = tt.xy[seq]; dist_m = float(np.hypot(*np.diff(xy, axis=0).T).sum()) if len(seq) > 1 else 0.0
            legs.append(dict(kind="bus", dist_m=dist_m, route=str(tt.route_name[r]), agency=tt.route_agency[r], headsign=str(tt.trip_head[l["trip_idx"]]),
                             board=name(l["board_stop"]), alight=name(l["alight_stop"]), dep=l["dep"], arr=l["arr"], n_stops=len(seq) - 1,
                             mins=(l["arr"] - l["dep"]) / 60, coords=_coords(tt, seq), trip_idx=l["trip_idx"]))
    egr = j["egress_s"]
    if egr > 5:
        e_m = d.stops[j["stop"]][1]
        legs.append(dict(kind="walk", role="egress", mins=egr / 60, metres=e_m, from_name=name(j["stop"]), to_name=d.label,
                         coords=_coords(tt, [j["stop"]]) + [(d.lat, d.lon)]))
    leave = first_trip["dep"] - acc_w
    bus = [l for l in legs if l["kind"] == "bus"]
    waits = [(b["dep"] - a["arr"]) / 60 for a, b in zip(bus[:-1], bus[1:])]
    return dict(legs=legs, leave=int(leave), arrive=int(j["arrival"]), duration_s=int(j["arrival"] - leave), transfers=len(bus) - 1,
                bus_min=sum(b["mins"] for b in bus), walk_min=sum(l["mins"] for l in legs if l["kind"] == "walk"), wait_min=sum(waits),
                key=tuple(b["trip_idx"] for b in bus))


def plan(tt, o: Endpoint, d: Endpoint, date: dt.date, t0: int, n_options: int = 4, max_rounds: int = 5):
    """Return (journeys, warnings). Each iteration asks for the best journeys leaving *after* the previous option's first bus."""
    warns = []
    v0, v1 = tt.feed_validity()
    if not (v0 <= date <= v1):
        return [], [f"The timetable feed only covers {v0:%d %b %Y} to {v1:%d %b %Y}; no scheduled service is available for {date:%d %b %Y}."]
    if set(o.stops) & set(d.stops) and o.label == d.label:
        return [], ["Origin and destination are the same place."]
    sd = tt.service_day(date)
    if len(tt.active_service_codes(date)) == 0:
        return [], ["No services are scheduled on that date."]
    targets = {s: w for s, (w, _) in d.stops.items()}
    out, seen, t = [], set(), t0
    for _ in range(n_options + 3):
        src = {s: t + int(w) for s, (w, _) in o.stops.items()}
        res = raptor(tt, sd, src, t, targets, max_rounds=max_rounds)
        js = pareto_journeys(res, targets, max_rounds)
        if not js:
            break
        built = [_build(tt, sd, o, d, j, t) for j in js]
        for b in built:
            if b["key"] not in seen:
                seen.add(b["key"]); out.append(b)
        first = next(l for l in built[0]["legs"] if l["kind"] == "bus")
        acc = o.stops.get(js[0]["source_stop"], (0, 0))[0]
        t = int(first["dep"] - acc + 8 * 60)          # next search starts ~8 min after the previous first bus
        if t > 28 * 3600:
            break
    # drop dominated options (not earlier-leaving, not faster, not fewer transfers than another option)
    keep = []
    for j in out:
        if not any(k is not j and k["leave"] >= j["leave"] and k["arrive"] <= j["arrive"] and k["transfers"] <= j["transfers"]
                   and (k["leave"], k["arrive"], k["transfers"]) != (j["leave"], j["arrive"], j["transfers"]) for k in out):
            keep.append(j)
    out = sorted(keep, key=lambda j: (j["leave"], j["arrive"]))[:n_options]
    if out:
        fastest = min(j["duration_s"] for j in out); few = min(j["transfers"] for j in out)
        for j in out:
            j["tags"] = (["Fastest"] if j["duration_s"] == fastest and len({x["duration_s"] for x in out}) > 1 else []) + \
                        (["Fewest transfers"] if j["transfers"] == few and len({x["transfers"] for x in out}) > 1 else [])
    else:
        warns.append("No scheduled journey found within the 5-trip search limit after the chosen time (service may have ended for the day).")
    return out, warns


def reachable(tt, o: Endpoint, date: dt.date, t0: int, minutes: int = 60, max_rounds: int = 4):
    """One-to-all earliest arrival within `minutes`. Returns DataFrame of stops with travel minutes (incl. access walk)."""
    sd = tt.service_day(date)
    src = {s: t0 + int(w) for s, (w, _) in o.stops.items()}
    res = raptor(tt, sd, src, t0, None, max_rounds=max_rounds, cap=t0 + minutes * 60)
    b = res.best; ok = b < INF
    df = tt.stops.loc[ok, ["stop_idx", "stop_name", "stop_lat", "stop_lon", "agency_id"]].copy()
    df["minutes"] = (b[ok] - t0) / 60
    return df


def time_breakdown(j: dict, req_t0: int) -> dict:
    """Split a journey's door-to-door time into walking / waiting / riding (minutes). Components sum exactly to total_min."""
    walks = [l for l in j["legs"] if l["kind"] == "walk"]
    access = sum(l["mins"] for l in walks if l["role"] == "access")
    egress = sum(l["mins"] for l in walks if l["role"] == "egress")
    t_walk = sum(l["mins"] for l in walks if l["role"] == "transfer")
    onboard = sum(l["mins"] for l in j["legs"] if l["kind"] == "bus")
    t_wait = max(j["wait_min"] - t_walk, 0.0)          # between-bus gaps include the transfer walk
    total = j["duration_s"] / 60
    return dict(access_walk=access, onboard=onboard, transfer_walk=t_walk, transfer_wait=t_wait, egress_walk=egress, total_min=total,
                leave_after_min=(j["leave"] - req_t0) / 60)
