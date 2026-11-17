"""Prepare the data for the Public Transport Demand and Service Gap Analysis.

Run from the project folder:   python scripts/01_prepare_data.py

What it does, in order:
  1. Loads the Mumbai bus timetable (GTFS) and checks its quality.
  2. Loads the 227 prabhags (electoral-ward areas) with Census 2011 population = our DEMAND measure.
  3. Spreads each prabhag's residents evenly over a 100 m grid.
  4. For every grid cell finds the nearest bus stop and the scheduled trips per peak hour = our SUPPLY measure.
  5. Flags residents who are underserved: no stop within NEAR_M metres, or a stop but fewer than LOW_FREQ trips/hour.
  6. Adds the results up per prabhag and per ward, and suggests new stop areas in the study ward.
Everything written goes to data/processed/.
"""
import io, json, sys, zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import numpy as np
import pandas as pd
import geopandas as gpd
from scipy import sparse
from scipy.spatial import cKDTree

from src.config import *

PROC.mkdir(parents=True, exist_ok=True)

# ------------------------------------------------------------------ 1. timetable + quality check
z = zipfile.ZipFile(GTFS_ZIP)
stops = pd.read_csv(io.BytesIO(z.read("stops.txt")), dtype={"stop_id": str})
trips = pd.read_csv(io.BytesIO(z.read("trips.txt")), usecols=["trip_id"], dtype=str)
st = pd.read_csv(io.BytesIO(z.read("stop_times.txt")), dtype={"trip_id": str, "stop_id": str},
                 usecols=["trip_id", "stop_id", "departure_time", "stop_sequence", "timepoint"])

hh, mm, ss = (st.departure_time.str.split(":", expand=True).astype(int)[i] for i in range(3))
st["dep"] = hh * 3600 + mm * 60 + ss

quality = {
    "stops": len(stops), "trips": len(trips), "stop_time_rows": len(st),
    "stop_times_with_unknown_stop": int((~st.stop_id.isin(stops.stop_id)).sum()),
    "stop_times_with_unknown_trip": int((~st.trip_id.isin(trips.trip_id)).sum()),
    "trips_without_stop_times": int((~trips.trip_id.isin(st.trip_id)).sum()),
    "duplicate_stop_ids": int(stops.stop_id.duplicated().sum()),
    "share_official_timepoints": round(float(st.timepoint.mean()), 4),
    "note": "Only a small share of stop times are official timepoints; the rest are interpolated, so times are approximate.",
}

# ------------------------------------------------------------------ 2. prabhags = demand
wards = gpd.read_file(WARDS_FILE).to_crs(CRS_UTM)
wards = wards.rename(columns={"WARD": "admin_ward", "PRABHAG_NO": "prabhag", "POPULATION": "pop"})
wards["geometry"] = wards.buffer(0)
wards = wards[["prabhag", "admin_ward", "pop", "geometry"]].reset_index(drop=True)
wards["pid"] = np.arange(len(wards))
wards["area_km2"] = wards.area / 1e6
quality["residents_total"] = int(wards["pop"].sum())
quality["residents_matches_census_2011_total"] = bool(abs(wards["pop"].sum() - 12_442_373) < 10)
assert STUDY_WARD in set(wards.admin_ward), f"STUDY_WARD '{STUDY_WARD}' not found. Options: {sorted(set(wards.admin_ward))}"

# ------------------------------------------------------------------ 3. grid: spread residents evenly inside each prabhag
minx, miny, maxx, maxy = wards.total_bounds
gx, gy = np.meshgrid(np.arange(minx + GRID_M / 2, maxx, GRID_M), np.arange(miny + GRID_M / 2, maxy, GRID_M))
cells = gpd.GeoDataFrame({"x": gx.ravel(), "y": gy.ravel()}, geometry=gpd.points_from_xy(gx.ravel(), gy.ravel()), crs=CRS_UTM)
cells = gpd.sjoin(cells, wards[["pid", "geometry"]], how="inner", predicate="within").drop(columns="index_right")
cells = cells[~cells.index.duplicated()].reset_index(drop=True)
cells["pop"] = cells.pid.map(wards.set_index("pid")["pop"] / cells.groupby("pid").size())
cells["prabhag"] = cells.pid.map(wards.set_index("pid").prabhag)
cells["admin_ward"] = cells.pid.map(wards.set_index("pid").admin_ward)

# ------------------------------------------------------------------ 4. supply: nearest stop and scheduled trips per peak hour
sg = gpd.GeoDataFrame(stops, geometry=gpd.points_from_xy(stops.stop_lon, stops.stop_lat), crs="EPSG:4326").to_crs(CRS_UTM)
stops["x"], stops["y"] = sg.geometry.x.values, sg.geometry.y.values
stops["stop_idx"] = np.arange(len(stops))
stop_idx = stops.set_index("stop_id").stop_idx

stree = cKDTree(stops[["x", "y"]].to_numpy())
ctree = cKDTree(cells[["x", "y"]].to_numpy())
cells["dist_nearest_m"], _ = stree.query(cells[["x", "y"]].to_numpy())

# a bus is only a boarding chance at stops where it still has somewhere to go, so drop each trip's last stop
is_last = st.groupby("trip_id").stop_sequence.transform("max") == st.stop_sequence
peak = st[~is_last & (st.dep >= PEAK_START_H * 3600) & (st.dep < PEAK_END_H * 3600)].copy()
peak["s"] = peak.stop_id.map(stop_idx)
peak["t"] = pd.factorize(peak.trip_id)[0]
M = sparse.csr_matrix((np.ones(len(peak)), (peak.s, peak.t)), shape=(len(stops), peak.t.max() + 1))   # stop x trip

A = ctree.sparse_distance_matrix(stree, NEAR_M, output_type="coo_matrix").tocsr()                    # cell x stop within NEAR_M
A.data[:] = 1.0
hours = PEAK_END_H - PEAK_START_H
uniq = np.zeros(len(cells), dtype=np.float32)
for i in range(0, len(cells), 4000):      # count each trip once even if it passes several nearby stops
    uniq[i:i + 4000] = (A[i:i + 4000] @ M).getnnz(axis=1)
cells["trips_peak_h"] = uniq / hours
stops["peak_trips_h"] = np.asarray(M.sum(axis=1)).ravel() / hours

# ------------------------------------------------------------------ 5. the gap
cells["no_stop"] = cells.dist_nearest_m > NEAR_M
cells["low_freq"] = (~cells.no_stop) & (cells.trips_peak_h < LOW_FREQ)
cells["underserved"] = cells.no_stop | cells.low_freq
cells["pop_no_stop"] = np.where(cells.no_stop, cells["pop"], 0.0)
cells["pop_low_freq"] = np.where(cells.low_freq, cells["pop"], 0.0)
cells["pop_underserved"] = cells["pop"] * cells.underserved

# ------------------------------------------------------------------ 6. aggregate to prabhag and ward
g = cells.groupby("pid")
pr = pd.DataFrame({"pop_check": g["pop"].sum(), "no_stop_pop": g.pop_no_stop.sum(), "low_freq_pop": g.pop_low_freq.sum(),
                   "underserved_pop": g.pop_underserved.sum(),
                   "peak_trips_h": g.apply(lambda d: np.average(d.trips_peak_h, weights=d["pop"]), include_groups=False),
                   "mean_dist_m": g.apply(lambda d: np.average(d.dist_nearest_m, weights=d["pop"]), include_groups=False)})
pr = wards.drop(columns="geometry").merge(pr, left_on="pid", right_index=True)
pr["density_km2"] = pr["pop"] / pr.area_km2
pr["area_type"] = np.where(pr.density_km2 >= 5000, "dense residential", "low density (may include parks, port or industry)")
for k in ("no_stop", "low_freq", "underserved"):
    pr[f"{k}_share"] = pr[f"{k}_pop"] / pr["pop"]
pr["in_study_ward"] = pr.admin_ward == STUDY_WARD

wd = pr.groupby("admin_ward").agg(pop=("pop", "sum"), no_stop_pop=("no_stop_pop", "sum"), low_freq_pop=("low_freq_pop", "sum"),
                                  underserved_pop=("underserved_pop", "sum"), prabhags=("prabhag", "size")).reset_index()
wd["underserved_share"] = wd.underserved_pop / wd["pop"]; wd["no_stop_share"] = wd.no_stop_pop / wd["pop"]; wd["low_freq_share"] = wd.low_freq_pop / wd["pop"]
wd["is_study_ward"] = wd.admin_ward == STUDY_WARD

# ------------------------------------------------------------------ 7. suggested new stop areas in the study ward (greedy)
ll = gpd.GeoSeries(gpd.points_from_xy(cells.x, cells.y), crs=CRS_UTM).to_crs("EPSG:4326")
cells["lat"], cells["lon"] = ll.y.values, ll.x.values
u = cells[(cells.admin_ward == STUDY_WARD) & cells.no_stop & (cells["pop"] > 0)].reset_index(drop=True)
remaining = u["pop"].to_numpy().copy(); sites = []
if len(u) > 0:                      # nothing to suggest if every resident already has a stop nearby
    ut = cKDTree(u[["x", "y"]].to_numpy())
    adj = ut.sparse_distance_matrix(ut, NEAR_M, output_type="coo_matrix").tocsr()
    adj.data[:] = 1.0
    adj = adj + sparse.eye(len(u), format="csr"); adj.data[:] = 1.0
    for rank in range(1, N_NEW_STOPS + 1):
        gain = adj @ remaining
        j = int(np.argmax(gain))
        if gain[j] <= 0:
            break
        sites.append({"rank": rank, "lat": float(u.lat[j]), "lon": float(u.lon[j]), "prabhag": int(u.prabhag[j]),
                      "newly_covered": float(gain[j])})
        remaining[adj[j].indices] = 0
sites = pd.DataFrame(sites, columns=["rank", "lat", "lon", "prabhag", "newly_covered"])
sites["cumulative_covered"] = sites.newly_covered.cumsum()
sites["cumulative_share_of_no_stop"] = sites.cumulative_covered / max(u["pop"].sum(), 1)
sites = sites.merge(pr[["prabhag", "density_km2", "area_type"]], on="prabhag", how="left")   # flag sites in low-density prabhags

# ------------------------------------------------------------------ write outputs
geo = wards[["pid", "geometry"]].merge(pr, on="pid").drop(columns=["pid", "pop_check"]).to_crs("EPSG:4326")
geo.to_file(PROC / "prabhags.geojson", driver="GeoJSON")
wd.to_parquet(PROC / "ward_summary.parquet", index=False)
cells[cells.admin_ward == STUDY_WARD][["lat", "lon", "pop", "prabhag", "dist_nearest_m", "trips_peak_h", "no_stop", "low_freq"]] \
    .astype({"pop": "float32", "dist_nearest_m": "float32", "trips_peak_h": "float32"}).to_parquet(PROC / "study_cells.parquet", index=False)
sw = gpd.GeoSeries(gpd.points_from_xy(stops.x, stops.y), crs=CRS_UTM)
keep = sw.within(wards.union_all().buffer(NEAR_M)).values
stops.loc[keep, ["stop_id", "stop_name", "stop_lat", "stop_lon", "peak_trips_h"]].to_parquet(PROC / "stops.parquet", index=False)
cells[["lat", "lon", "pop", "prabhag", "admin_ward", "dist_nearest_m", "trips_peak_h", "no_stop", "low_freq"]] \
    .astype({"lat": "float32", "lon": "float32", "pop": "float32", "prabhag": "int16", "dist_nearest_m": "float32", "trips_peak_h": "float32", "admin_ward": "category"}) \
    .to_parquet(PROC / "cells.parquet", index=False)      # whole city: lets the app look up the service at any searched address
sites.to_parquet(PROC / "new_stop_sites.parquet", index=False)

city = {"residents": float(pr["pop"].sum()), "underserved": float(pr.underserved_pop.sum()), "no_stop": float(pr.no_stop_pop.sum()), "low_freq": float(pr.low_freq_pop.sum())}
meta = {"study_ward": STUDY_WARD, "near_m": NEAR_M, "low_freq_trips_per_hour": LOW_FREQ, "peak_hours": [PEAK_START_H, PEAK_END_H], "grid_m": GRID_M, "city": city,
        "feed_note": "Scheduled timetable only: no live data, no passenger counts."}
(PROC / "data_quality.json").write_text(json.dumps({"quality": quality, "settings": meta}, indent=2))

s = wd[wd.is_study_ward].iloc[0]
print(json.dumps(quality, indent=1))
print(f"\nGreater Mumbai: {city['underserved'] / city['residents']:.1%} of residents underserved")
print(f"{STUDY_WARD}: {s['pop']:,.0f} residents, {s.underserved_pop:,.0f} underserved ({s.underserved_share:.1%}); "
      f"no stop {s.no_stop_pop:,.0f}, low frequency {s.low_freq_pop:,.0f}")
if len(sites):
    print(f"{len(sites)} new stop areas would cover {sites.cumulative_covered.iloc[-1]:,.0f} residents "
          f"({sites.cumulative_share_of_no_stop.iloc[-1]:.1%} of those with no stop)")
else:
    print("Every resident of the study ward already has a stop within reach, so no new stop areas are suggested.")
print("files:", sorted(p.name for p in PROC.iterdir()))
