"""Core correctness tests.  Run:  pytest -q tests/test_core.py"""
import datetime as dt, numpy as np, pandas as pd, pytest
from src.config import *
from src.timetable import Timetable
from src.raptor import raptor, pareto_journeys
from src.journey import plan, endpoint_from_place, endpoint_from_point, reachable

DAY = dt.date(2026, 11, 12)


@pytest.fixture(scope="module")
def tt(): return Timetable.load()
@pytest.fixture(scope="module")
def P(): return {n: pd.read_parquet(PROC / f"{n}.parquet") for n in ["stops", "trips", "routes", "stop_times", "places", "facilities", "grid_cells", "prabhag_scores"]}


# ---------------- data integrity ----------------
def test_gtfs_referential_integrity(P):
    st, trips, stops = P["stop_times"], P["trips"], P["stops"]
    assert st.trip_idx.isin(trips.trip_idx).all() and st.stop_idx.isin(stops.stop_idx).all()
    assert trips.route_idx.isin(P["routes"].route_idx).all()

def test_times_monotonic_within_trip(P):
    st = P["stop_times"].sort_values(["trip_idx", "seq"])
    assert (st.groupby("trip_idx").arr.diff().dropna() >= 0).all()
    assert (st.dep >= st.arr).all()

def test_stop_coordinates_in_mmr(P):
    s = P["stops"]; assert s.stop_lat.between(18.5, 19.8).all() and s.stop_lon.between(72.5, 73.5).all()

def test_population_matches_census_total(P):
    assert abs(P["grid_cells"]["pop"].sum() - 12_442_373) < 50           # grid conserves the ward totals
    assert P["prabhag_scores"]["pop"].sum() == 12_442_373


# ---------------- calendar logic ----------------
def test_calendar_validity(tt):
    v0, v1 = tt.feed_validity()
    assert len(tt.active_service_codes(v0)) == 1 and len(tt.active_service_codes(v1)) == 1
    assert len(tt.active_service_codes(v0 - dt.timedelta(days=1))) == 0
    assert len(tt.active_service_codes(v1 + dt.timedelta(days=1))) == 0

def test_out_of_feed_date_gives_warning_not_journey(tt, P):
    pl = P["places"]; g = lambda n: endpoint_from_place(tt, pl[pl.label == n].iloc[0])
    js, w = plan(tt, g("Mumbai Central Station"), g("Malad Station (W)"), dt.date(2030, 1, 1), 9 * 3600)
    assert js == [] and "feed only covers" in w[0]


# ---------------- RAPTOR correctness ----------------
def test_never_slower_than_riding_a_scheduled_trip(tt, P):
    """For random (trip, board, alight) triples RAPTOR must arrive no later than the trip itself."""
    st = P["stop_times"]; rng = np.random.default_rng(7); sd = tt.service_day(DAY); checked = 0
    for ti in rng.choice(st.trip_idx.unique(), 120, replace=False):
        df = st[st.trip_idx == ti].sort_values("seq")
        if len(df) < 4: continue
        a, b = sorted(rng.choice(len(df), 2, replace=False))
        s0, s1 = int(df.stop_idx.iloc[a]), int(df.stop_idx.iloc[b]); t0 = int(df.dep.iloc[a])
        if s0 == s1 or t0 >= 86400: continue
        res = raptor(tt, sd, {s0: t0}, t0, {s1: 0}); js = pareto_journeys(res, {s1: 0})
        assert js and min(j["arrival"] for j in js) <= int(df.arr.iloc[b]); checked += 1
    assert checked > 60

def test_pareto_monotone(tt, P):
    pl = P["places"]; g = lambda n: endpoint_from_place(tt, pl[pl.label == n].iloc[0]); o, d = g("Colaba Bus Station"), g("Borivali (W) Station")
    sd = tt.service_day(DAY); tg = {s: w for s, (w, _) in d.stops.items()}
    res = raptor(tt, sd, {s: 9 * 3600 + int(w) for s, (w, _) in o.stops.items()}, 9 * 3600, tg)
    js = pareto_journeys(res, tg)
    assert js and all(a["arrival"] > b["arrival"] and a["k"] < b["k"] for a, b in zip(js[1:], js[:-1])) or len(js) == 1


# ---------------- journey itinerary consistency ----------------
def test_itinerary_is_physically_consistent(tt, P):
    pl = P["places"]; g = lambda n: endpoint_from_place(tt, pl[pl.label == n].iloc[0])
    js, w = plan(tt, g("Mumbai Central Station"), g("Malad Station (W)"), DAY, 9 * 3600, n_options=4)
    assert js and not w
    for j in js:
        bus = [l for l in j["legs"] if l["kind"] == "bus"]
        assert j["arrive"] > j["leave"] >= 9 * 3600 - 600
        assert all(b["arr"] > b["dep"] for b in bus)
        for a, b in zip(bus[:-1], bus[1:]):
            assert b["dep"] - a["arr"] >= MIN_TRANSFER_S - 1            # transfer buffer respected
        assert j["transfers"] == len(bus) - 1 and j["wait_min"] >= 0
        assert j["duration_s"] < 4 * 3600

def test_later_departure_never_arrives_earlier(tt, P):
    pl = P["places"]; g = lambda n: endpoint_from_place(tt, pl[pl.label == n].iloc[0]); o, d = g("Mumbai Central Station"), g("Malad Station (W)")
    a = plan(tt, o, d, DAY, 9 * 3600, 1)[0][0]["arrive"]; b = plan(tt, o, d, DAY, 12 * 3600, 1)[0][0]["arrive"]
    assert b > a

def test_overnight_trips_are_found_after_midnight(tt, P):
    """Trips that started the previous day (times >24:00) must be available at 00:30."""
    pl = P["places"]; o = endpoint_from_place(tt, pl[pl.label == "Mumbai Central Station"].iloc[0])
    df = reachable(tt, o, DAY, 30 * 60, 60)
    assert len(df) > 0

def test_facility_endpoint(tt, P):
    f = P["facilities"]; c = f[f.group == "Education"].iloc[0]; pl = P["places"]
    d = endpoint_from_point(tt, c["name"], c.lat, c.lon, c.x, c.y)
    js, w = plan(tt, endpoint_from_place(tt, pl[pl.label == "Mumbai Central Station"].iloc[0]), d, DAY, 9 * 3600, 2)
    assert js


# ---------------- accessibility invariants ----------------
def test_coverage_monotone_in_radius(P):
    c = P["grid_cells"]; cov = [c.loc[c.dist_nearest_m <= r, "pop"].sum() / c["pop"].sum() for r in ACCESS_RADII_M]
    assert cov[0] < cov[1] < cov[2] <= 1

def test_facility_uncertainty_logic(P):
    f = P["facilities"]
    for r in ACCESS_RADII_M:
        assert (f[f"certain_{r}"] <= f[f"possible_{r}"]).all()            # certain implies possible
    assert (f.dist_stop_min_m <= f.dist_stop_center_m + 1e-6).all() and (f.dist_stop_max_m >= f.dist_stop_center_m - 1e-6).all()
    assert (f[f.precision == "precise"].dist_stop_min_m == f[f.precision == "precise"].dist_stop_max_m).all()

def test_unique_trip_metric_not_inflated(P):
    c = P["grid_cells"]; assert c.trips_peak_h_500.max() < 1500 and (c.n_routes_500 <= c.trips_day_500).all()

def test_index_bounds_and_archetypes(P):
    i = P["prabhag_scores"]; assert i.connectivity_index.between(0, 100).all() and i.archetype.notna().all() and i.shape[0] == 227

def test_places_unique_labels(P):
    assert P["places"].label.is_unique


# ---------------- passenger features: fares, time summary, nearest stops ----------------
def test_fare_slab_boundaries():
    from src import fares
    assert fares.slab_fare(5.0, "non_ac") == 10 and fares.slab_fare(5.01, "non_ac") == 15
    assert fares.slab_fare(25.0, "ac") == 40 and fares.slab_fare(25.01, "ac") is None

def test_fare_only_prices_best_legs_and_is_a_range():
    from src import fares
    legs = [dict(kind="bus", agency="BEST", dist_m=4000), dict(kind="bus", agency="TMT", dist_m=9000), dict(kind="walk")]
    f = fares.estimate(legs)
    assert f["best_legs"] == 1 and f["other_legs"] == 1 and f["other_operators"] == ["TMT"]
    lo, hi = f["non_ac"]; assert lo <= hi and lo == 10                       # 4 km -> first slab
    assert f["ac"][0] == 12

def test_fare_above_table_is_not_priced():
    from src import fares
    assert fares.estimate([dict(kind="bus", agency="BEST", dist_m=30000)])["non_ac"] is None

def test_time_breakdown_sums_to_total(tt, P):
    from src.journey import time_breakdown
    pl = P["places"]; g = lambda n: endpoint_from_place(tt, pl[pl.label == n].iloc[0])
    js, _ = plan(tt, g("Mumbai Central Station"), g("Malad Station (W)"), DAY, 9 * 3600, 4)
    for j in js:
        b = time_breakdown(j, 9 * 3600)
        s = b["access_walk"] + b["onboard"] + b["transfer_walk"] + b["transfer_wait"] + b["egress_walk"]
        assert abs(s - b["total_min"]) < 0.5 and b["leave_after_min"] >= -1

def test_nearest_stops_sorted_and_plausible(tt):
    from src.nearest import nearest_stops
    sd = tt.service_day(DAY); r = nearest_stops(tt, 19.0760, 72.8777, 5, sd, 9 * 3600)
    assert len(r) == 5 and r.distance_m.is_monotonic_increasing and r.distance_m.iloc[0] < 500
    assert (r.walk_min > 0).all() and r.n_routes.iloc[0] >= 1

def test_leg_distance_present(tt, P):
    pl = P["places"]; g = lambda n: endpoint_from_place(tt, pl[pl.label == n].iloc[0])
    js, _ = plan(tt, g("Mumbai Central Station"), g("Malad Station (W)"), DAY, 9 * 3600, 1)
    assert all(l["dist_m"] > 100 for l in js[0]["legs"] if l["kind"] == "bus")
