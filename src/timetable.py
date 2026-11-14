"""GTFS timetable model: route patterns, service calendar logic, walking links.

A *pattern* is a unique ordered stop sequence. All trips of a pattern are stored as dense
(trips x stops) arrival/departure matrices sorted by first departure, which is what RAPTOR needs.
"""
from __future__ import annotations
import pickle, datetime as dt
from dataclasses import dataclass, field
import numpy as np, pandas as pd
from scipy.spatial import cKDTree
from .config import *

DAY = 86400


def build_patterns(stop_times: pd.DataFrame, trips: pd.DataFrame):
    st = stop_times.sort_values(["trip_idx", "seq"], kind="stable")
    ti = st.trip_idx.to_numpy(); si = st.stop_idx.to_numpy(); arr = st.arr.to_numpy(); dep = st.dep.to_numpy()
    bounds = np.flatnonzero(np.r_[True, ti[1:] != ti[:-1], True])
    svc_codes = {s: i for i, s in enumerate(sorted(trips.service_id.unique()))}
    svc_of_trip = trips.set_index("trip_idx").service_id.map(svc_codes)
    groups: dict[bytes, list] = {}
    for a, b in zip(bounds[:-1], bounds[1:]):
        groups.setdefault(si[a:b].tobytes(), []).append((a, b))
    P = dict(stops=[], dep=[], arr=[], trip=[], svc=[], over=[])
    for key, lst in groups.items():
        n = lst[0][1] - lst[0][0]
        D = np.stack([dep[a:b] for a, b in lst]); A = np.stack([arr[a:b] for a, b in lst])
        T = np.array([ti[a] for a, _ in lst], dtype=np.int32)
        order = np.argsort(D[:, 0], kind="stable")
        D, A, T = D[order], A[order], T[order]
        P["stops"].append(np.frombuffer(key, dtype=si.dtype).copy()); P["dep"].append(D.astype(np.int32)); P["arr"].append(A.astype(np.int32))
        P["trip"].append(T); P["svc"].append(svc_of_trip.loc[T].to_numpy().astype(np.int16)); P["over"].append(A.max(axis=1) >= DAY)
    return P, svc_codes


@dataclass
class View:
    dep: np.ndarray; arr: np.ndarray; trip: np.ndarray; fifo: bool


class ServiceDay:
    """Resolves which services run on a date (calendar + calendar_dates) and caches per-pattern views."""

    def __init__(self, tt: "Timetable", date: dt.date):
        self.tt, self.date = tt, date
        self.today = tt.active_service_codes(date)
        self.yday = tt.active_service_codes(date - dt.timedelta(days=1))
        self.cache: dict[int, View] = {}

    def view(self, p: int) -> View | None:
        v = self.cache.get(p, 0)
        if v != 0:
            return v
        tt = self.tt
        m_today = np.isin(tt.pat_svc[p], self.today)
        m_y = np.isin(tt.pat_svc[p], self.yday) & tt.pat_over[p]      # after-midnight tail of previous day's trips
        if not (m_today.any() or m_y.any()):
            self.cache[p] = None; return None
        D = np.vstack([tt.pat_dep[p][m_today], tt.pat_dep[p][m_y] - DAY]); A = np.vstack([tt.pat_arr[p][m_today], tt.pat_arr[p][m_y] - DAY])
        T = np.concatenate([tt.pat_trip[p][m_today], tt.pat_trip[p][m_y]])
        o = np.argsort(D[:, 0], kind="stable"); D, A, T = D[o], A[o], T[o]
        fifo = bool(np.all(np.diff(D, axis=0) >= 0)) if len(D) > 1 else True
        self.cache[p] = View(D, A, T, fifo)
        return self.cache[p]


class Timetable:
    def __init__(self, stops, routes, trips, cal, caldates, P, svc_codes):
        self.stops, self.routes, self.trips, self.cal, self.caldates = stops, routes, trips, cal, caldates
        self.pat_stops, self.pat_dep, self.pat_arr, self.pat_trip, self.pat_svc, self.pat_over = (P[k] for k in ("stops", "dep", "arr", "trip", "svc", "over"))
        self.svc_codes = svc_codes
        self.n_stops = len(stops); self.n_patterns = len(self.pat_stops)
        self.xy = stops[["x", "y"]].to_numpy()
        self.tree = cKDTree(self.xy)
        # stop -> [(pattern, position)]
        sp = [[] for _ in range(self.n_stops)]
        for p, s in enumerate(self.pat_stops):
            for i, st_ in enumerate(s):
                sp[st_].append((p, i))
        self.stop_patterns = sp
        self._build_footpaths()
        self.trip_pattern = np.full(int(trips.trip_idx.max()) + 1, -1, dtype=np.int32)
        for p, T in enumerate(self.pat_trip):
            self.trip_pattern[T] = p
        self.trip_route = trips.set_index("trip_idx").route_idx
        self.trip_head = trips.set_index("trip_idx").trip_headsign
        self.route_name = routes.set_index("route_idx").route_short_name
        self.route_agency = routes.set_index("route_idx").agency_id
        self.route_long = routes.set_index("route_idx").route_long_name

    # ------------------------------------------------------------------ calendar logic
    def active_service_codes(self, date: dt.date) -> np.ndarray:
        d = int(date.strftime("%Y%m%d")); wd = date.strftime("%A").lower()
        active = set()
        for _, r in self.cal.iterrows():
            if int(r.start_date) <= d <= int(r.end_date) and str(r[wd]) == "1":
                active.add(r.service_id)
        if self.caldates is not None and len(self.caldates):
            cd = self.caldates[self.caldates.date.astype(int) == d]
            for _, r in cd.iterrows():
                (active.add if str(r.exception_type) == "1" else active.discard)(r.service_id)
        return np.array([self.svc_codes[s] for s in active if s in self.svc_codes], dtype=np.int16)

    def feed_validity(self) -> tuple[dt.date, dt.date]:
        f = lambda s: dt.datetime.strptime(str(s), "%Y%m%d").date()
        return f(self.cal.start_date.min()), f(self.cal.end_date.max())

    def service_day(self, date: dt.date) -> ServiceDay:
        return ServiceDay(self, date)

    # ------------------------------------------------------------------ walking
    def _build_footpaths(self):
        pairs = self.tree.query_pairs(MAX_TRANSFER_WALK_M, output_type="ndarray")
        a = np.r_[pairs[:, 0], pairs[:, 1]]; b = np.r_[pairs[:, 1], pairs[:, 0]]
        d = np.hypot(*(self.xy[a] - self.xy[b]).T)
        secs = (d * DETOUR_FACTOR / WALK_SPEED_MS).astype(np.int32)
        o = np.argsort(a, kind="stable"); a, b, secs = a[o], b[o], secs[o]
        self.fp_ptr = np.searchsorted(a, np.arange(self.n_stops + 1)); self.fp_to = b.astype(np.int32); self.fp_s = secs

    def walk_links(self, x: float, y: float, max_m: float = 700, max_n: int = 12, speed=WALK_SPEED_MS, detour=DETOUR_FACTOR):
        """Stops reachable on foot from a point -> {stop_idx: (walk_seconds, straight_m)}. Always returns the nearest stop."""
        idx = self.tree.query_ball_point([x, y], max_m)
        if not idx:
            _, i = self.tree.query([x, y]); idx = [int(i)]
        d = np.hypot(*(self.xy[idx] - [x, y]).T)
        o = np.argsort(d)[:max_n]
        return {int(idx[k]): (float(d[k] * detour / speed), float(d[k])) for k in o}

    # ------------------------------------------------------------------ persistence
    def save(self, path):
        pickle.dump(dict(P=dict(stops=self.pat_stops, dep=self.pat_dep, arr=self.pat_arr, trip=self.pat_trip, svc=self.pat_svc, over=self.pat_over),
                         svc_codes=self.svc_codes), open(path, "wb"), protocol=5)

    @classmethod
    def load(cls, proc=PROC):
        d = pickle.load(open(proc / "timetable_patterns.pkl", "rb"))
        stops = pd.read_parquet(proc / "stops.parquet"); routes = pd.read_parquet(proc / "routes.parquet")
        trips = pd.read_parquet(proc / "trips.parquet"); cal = pd.read_parquet(proc / "calendar.parquet")
        return cls(stops, routes, trips, cal, None, d["P"], d["svc_codes"])
