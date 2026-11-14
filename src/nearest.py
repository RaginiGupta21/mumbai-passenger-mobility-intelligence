"""'Walk to nearest stop' - nearest bus stops to any point, with walking time, routes served and next departures."""
from __future__ import annotations
import numpy as np, pandas as pd
from pyproj import Transformer
from .config import *
from .common import s_to_hm

_T = Transformer.from_crs(CRS_WGS84, CRS_UTM, always_xy=True)


def to_xy(lat: float, lon: float):
    return _T.transform(lon, lat)


def routes_at_stop(tt, s: int) -> list[str]:
    names = set()
    for p, _ in tt.stop_patterns[s]:
        for r in np.unique(tt.trip_route.reindex(tt.pat_trip[p]).to_numpy()):
            names.add(str(tt.route_name[int(r)]))
    return sorted(names, key=lambda x: (len(x), x))


def next_departures(tt, sd, stop_ids, t0: int, n: int = 3):
    """Next `n` scheduled departures after t0 over the given stops (terminal arrivals excluded)."""
    rows = []
    for s in stop_ids:
        for p, i in tt.stop_patterns[s]:
            if i == len(tt.pat_stops[p]) - 1:
                continue
            v = sd.view(p)
            if v is None:
                continue
            col = v.dep[:, i]
            for j in np.flatnonzero(col >= t0)[:n]:
                tr = int(v.trip[j]); r = int(tt.trip_route[tr])
                rows.append((int(col[j]), str(tt.route_name[r]), tt.route_agency[r], str(tt.trip_head[tr])))
    rows.sort()
    return rows[:n]


def nearest_stops(tt, lat: float, lon: float, k: int = 5, sd=None, t0: int | None = None) -> pd.DataFrame:
    x, y = to_xy(lat, lon)
    d, idx = tt.tree.query([x, y], k=k)
    S = tt.stops; out = []
    for dist, s in zip(np.atleast_1d(d), np.atleast_1d(idx)):
        s = int(s); routes = routes_at_stop(tt, s)
        nxt = next_departures(tt, sd, [s], t0, 3) if sd is not None and t0 is not None else []
        out.append(dict(stop_idx=s, stop=S.stop_name.iat[s], lat=float(S.stop_lat.iat[s]), lon=float(S.stop_lon.iat[s]), operator=S.agency_id.iat[s],
                        distance_m=float(dist), walk_min=float(dist) * DETOUR_FACTOR / WALK_SPEED_MS / 60,
                        n_routes=len(routes), routes=", ".join(routes[:10]) + (" …" if len(routes) > 10 else ""),
                        departures_day=float(S.departures_day.iat[s]) if "departures_day" in S else np.nan,
                        next_departures="; ".join(f"{s_to_hm(t)} {r}" for t, r, _, _ in nxt) or "none after this time"))
    return pd.DataFrame(out)
