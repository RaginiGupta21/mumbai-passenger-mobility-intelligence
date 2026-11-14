"""Step 3 - Population-weighted accessibility on a 100 m grid + facility access + transit-time reach.

Population: BMC 2017 electoral wards (227 prabhags, 2011-Census based). Assumption: population is spread uniformly
within each prabhag (dasymetric refinement impossible without land-use data) - documented limitation.
"""
import sys, time, datetime as dt
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import numpy as np, pandas as pd, geopandas as gpd
from scipy import sparse
from scipy.spatial import cKDTree
from src.config import *
from src.common import load
from src.facilities import load_mcgm_health, load_osm_education, uncertainty_half_widths_m
from src.timetable import Timetable
from src.raptor import raptor, INF

t00 = time.time()
stops, st, trips = load("stops"), load("stop_times"), load("trips")
# ---------------- boundaries & population ----------------
pw = gpd.read_file(RAW / "boundaries/bmc_electoral_wards_2017.geojson").to_crs(CRS_UTM)
pw = pw.rename(columns={"WARD": "admin_ward", "PRABHAG_NO": "prabhag", "POPULATION": "pop", "SC_POP": "sc_pop", "ST_POP": "st_pop"})
pw["geometry"] = pw.buffer(0); pw = pw.reset_index(drop=True); pw["pid"] = np.arange(len(pw))
pw["area_km2"] = pw.area / 1e6
print("prabhags", len(pw), "pop total", int(pw["pop"].sum()), "area km2", round(pw.area_km2.sum(), 1), "dup prabhag nos", int(pw.prabhag.duplicated().sum()))
slums = gpd.read_file(RAW / "boundaries/sra_slum_clusters.geojson").to_crs(CRS_UTM); slums["geometry"] = slums.buffer(0)

# ---------------- grid ----------------
minx, miny, maxx, maxy = pw.total_bounds
gx, gy = np.meshgrid(np.arange(minx + GRID_M / 2, maxx, GRID_M), np.arange(miny + GRID_M / 2, maxy, GRID_M))
cells = gpd.GeoDataFrame({"x": gx.ravel(), "y": gy.ravel()}, geometry=gpd.points_from_xy(gx.ravel(), gy.ravel()), crs=CRS_UTM)
cells = gpd.sjoin(cells, pw[["pid", "geometry"]], how="inner", predicate="within").drop(columns="index_right")
cells = cells[~cells.index.duplicated()].reset_index(drop=True)
n_per = cells.groupby("pid").size()
for c in ["pop", "sc_pop", "st_pop"]:
    cells[c] = cells.pid.map(pw.set_index("pid")[c] / n_per)
cells["admin_ward"] = cells.pid.map(pw.set_index("pid").admin_ward); cells["prabhag"] = cells.pid.map(pw.set_index("pid").prabhag)
cells["is_slum"] = gpd.sjoin(cells[["geometry"]], slums[["geometry"]], how="left", predicate="within").groupby(level=0).index_right.first().notna().reindex(cells.index).values
print("cells", len(cells), "pop check", int(cells["pop"].sum()), "slum cells", int(cells.is_slum.sum()))

# ---------------- stop service metrics ----------------
last = st.groupby("trip_idx").seq.transform("max") == st.seq
dep = st[~last].copy()
dep["route_idx"] = dep.trip_idx.map(trips.set_index("trip_idx").route_idx)
n_dep = dep.groupby("stop_idx").size().reindex(stops.stop_idx, fill_value=0).to_numpy()
pk = dep[(dep.dep >= PEAK_START_H * 3600) & (dep.dep < PEAK_END_H * 3600)]
n_pk = (pk.groupby("stop_idx").size().reindex(stops.stop_idx, fill_value=0).to_numpy() / (PEAK_END_H - PEAK_START_H))
sr = dep[["stop_idx", "route_idx"]].drop_duplicates()
R = sparse.csr_matrix((np.ones(len(sr)), (sr.stop_idx, sr.route_idx)), shape=(len(stops), int(trips.route_idx.max()) + 1))
stops["departures_day"] = n_dep; stops["departures_peak_h"] = n_pk; stops["n_routes"] = np.asarray((R > 0).sum(axis=1)).ravel()

ctree, stree = cKDTree(cells[["x", "y"]].to_numpy()), cKDTree(stops[["x", "y"]].to_numpy())
d, nn = stree.query(cells[["x", "y"]].to_numpy())
cells["dist_nearest_m"] = d; cells["nearest_stop"] = nn.astype(np.int32)
A = (ctree.sparse_distance_matrix(stree, 500, output_type="coo_matrix")).tocsr()
A.data[:] = 1.0
cells["n_stops_500"] = np.asarray(A.sum(axis=1)).ravel().astype(np.int16)
cells["n_routes_500"] = np.asarray(((A @ R) > 0).sum(axis=1)).ravel().astype(np.int16)
# unique scheduled trips serving the 500 m catchment (a trip passing 5 nearby stops is counted once)
Tall = sparse.csr_matrix((np.ones(len(dep)), (dep.stop_idx, dep.trip_idx)), shape=(len(stops), len(trips)))
pkd = dep[(dep.dep >= PEAK_START_H * 3600) & (dep.dep < PEAK_END_H * 3600)]
Tpk = sparse.csr_matrix((np.ones(len(pkd)), (pkd.stop_idx, pkd.trip_idx)), shape=(len(stops), len(trips)))
def unique_trips(adj, M, chunk=4000):
    out = np.zeros(adj.shape[0], dtype=np.float32)
    for i in range(0, adj.shape[0], chunk):
        out[i:i + chunk] = (adj[i:i + chunk] @ M).getnnz(axis=1)
    return out
cells["trips_day_500"] = unique_trips(A, Tall); cells["trips_peak_h_500"] = unique_trips(A, Tpk) / (PEAK_END_H - PEAK_START_H)
print("coverage pop <=300/500/800 m:", [round(float(cells.loc[cells.dist_nearest_m <= r, "pop"].sum() / cells["pop"].sum()), 3) for r in ACCESS_RADII_M])

# ---------------- facilities ----------------
fac = pd.concat([load_mcgm_health(), load_osm_education()], ignore_index=True)
fg = gpd.GeoDataFrame(fac, geometry=gpd.points_from_xy(fac.lon, fac.lat), crs=CRS_WGS84).to_crs(CRS_UTM)
fac["x"], fac["y"] = fg.geometry.x.values, fg.geometry.y.values
gm = pw.union_all().buffer(300)
fac["in_greater_mumbai"] = fg.within(gm).values
fac = fac[fac.in_greater_mumbai].reset_index(drop=True)
fac["precision"] = np.where(fac.decimals >= 4, "precise", np.where(fac.decimals >= 2, "rounded (~±0.5 km)", "very coarse (~±5 km)"))
dmin, dmax, dc = [], [], []
for _, r in fac.iterrows():
    hy, hx = uncertainty_half_widths_m(int(r.decimals), r.lat) if r.decimals < 4 else (0, 0)
    off = np.array([(0, 0), (hx, 0), (-hx, 0), (0, hy), (0, -hy), (hx, hy), (hx, -hy), (-hx, hy), (-hx, -hy)])
    pts = np.array([r.x, r.y]) + off
    dd, _ = stree.query(pts); dmin.append(dd.min()); dmax.append(dd.max()); dc.append(dd[0])
fac["dist_stop_center_m"] = dc; fac["dist_stop_min_m"] = dmin; fac["dist_stop_max_m"] = dmax
for r_ in ACCESS_RADII_M:
    fac[f"certain_{r_}"] = fac.dist_stop_max_m <= r_       # within r even in the worst case of the rounding box
    fac[f"possible_{r_}"] = fac.dist_stop_min_m <= r_
Af = ctree.sparse_distance_matrix(stree, 1, output_type="coo_matrix")  # dummy to keep API warm
fa = sparse.csr_matrix(cKDTree(stops[["x", "y"]].to_numpy()).sparse_distance_matrix(cKDTree(fac[["x", "y"]].to_numpy()), 500, output_type="coo_matrix")).tocsr()
fa.data[:] = 1.0
fac["n_routes_500"] = np.asarray(((fa.T @ R) > 0).sum(axis=1)).ravel().astype(int)
fac["trips_day_500"] = unique_trips(fa.T.tocsr(), Tall); fac["trips_peak_h_500"] = unique_trips(fa.T.tocsr(), Tpk) / (PEAK_END_H - PEAK_START_H)
fac["fid"] = np.arange(len(fac))
fac["usable"] = fac.decimals >= 2   # 1-decimal coordinates (~±5 km) are kept for transparency but excluded from all metrics
# hospital beds (MCGM hospitals list) joined by exact normalised name where possible
print(fac.groupby(["group", "category", "precision"]).size())

# ---------------- transit-time accessibility from every prabhag (RAPTOR one-to-all) ----------------
tt = Timetable.load()
REF_DATE = dt.date(2026, 11, 18); T0 = 9 * 3600; CAP = T0 + 75 * 60
sd = tt.service_day(REF_DATE)
ftree = cKDTree(fac[["x", "y"]].to_numpy())
fstops = [[(int(s), float(np.hypot(*(stree.data[s] - [fx, fy]))) ) for s in stree.query_ball_point([fx, fy], 800)] for fx, fy in fac[["x", "y"]].to_numpy()]
cells["w"] = cells["pop"]
cen = cells.groupby("pid").apply(lambda g: pd.Series({"cx": np.average(g.x, weights=g.w), "cy": np.average(g.y, weights=g.w)}), include_groups=False)
rows, cell_time = [], np.full((len(pw), 0), 0)
cat_of = fac.category.to_numpy(); grp_of = fac.group.to_numpy()
cell_best = {}
t1 = time.time()
for pid, (cx, cy) in cen.iterrows():
    links = tt.walk_links(cx, cy, max_m=800, max_n=10)
    src = {s: T0 + int(w) for s, (w, _) in links.items()}
    res = raptor(tt, sd, src, T0, None, max_rounds=4, cap=CAP)
    best = res.best
    cell_best[pid] = best
    ft = np.full(len(fac), np.inf)
    for i, lst in enumerate(fstops):
        for s, dm in lst:
            if best[s] < INF:
                ft[i] = min(ft[i], best[s] + dm * DETOUR_FACTOR / WALK_SPEED_MS - T0)
    # Ward-level worst/best: also record whether origin can reach the facility at all
    rec = {"pid": pid, "origin_walk_min": min(w for w, _ in links.values()) / 60}
    use = fac.usable.to_numpy()
    for label, mask in [("college", (grp_of == "Education") & use), ("public_hospital", (cat_of == "Public hospital") & use),
                        ("primary_health", np.isin(cat_of, ["UPHC (urban primary health centre)", "Dispensary"]) & use)]:
        v = ft[mask] / 60
        rec[f"{label}_nearest_min"] = np.nanmin(v) if np.isfinite(v).any() else np.nan
        for T in (30, 45, 60):
            rec[f"{label}_n_{T}"] = int((v <= T).sum())
    pc = cells[cells.pid == pid]
    tcell = best[pc.nearest_stop.to_numpy()].astype(float)
    tcell = np.where(tcell < INF, tcell - T0 + pc.dist_nearest_m.to_numpy() * DETOUR_FACTOR / WALK_SPEED_MS, np.inf) / 60
    for T in (30, 45, 60):
        rec[f"area_reach_{T}"] = float((tcell <= T).mean())
    rows.append(rec)
print(f"RAPTOR one-to-all x {len(pw)}: {time.time()-t1:.0f}s")
reach = pd.DataFrame(rows)

# ---------------- aggregate indicators per prabhag ----------------
def agg(g):
    P = g["pop"].sum(); o = {}
    for r_ in ACCESS_RADII_M:
        o[f"cov_{r_}"] = g.loc[g.dist_nearest_m <= r_, "pop"].sum() / P if P else np.nan
    o["sc_cov_500"] = g.loc[g.dist_nearest_m <= 500, "sc_pop"].sum() / g.sc_pop.sum() if g.sc_pop.sum() else np.nan
    o["st_cov_500"] = g.loc[g.dist_nearest_m <= 500, "st_pop"].sum() / g.st_pop.sum() if g.st_pop.sum() else np.nan
    o["mean_dist_m"] = np.average(g.dist_nearest_m, weights=g["pop"])
    o["routes_500_popw"] = np.average(g.n_routes_500, weights=g["pop"])
    o["trips_peak_h_500_popw"] = np.average(g.trips_peak_h_500, weights=g["pop"])
    o["trips_day_500_popw"] = np.average(g.trips_day_500, weights=g["pop"])
    o["slum_cells"] = int(g.is_slum.sum()); o["slum_cov_500"] = (g.loc[g.is_slum, "dist_nearest_m"] <= 500).mean() if g.is_slum.any() else np.nan
    o["slum_share_area"] = g.is_slum.mean()
    return pd.Series(o)
ind = cells.groupby("pid").apply(agg, include_groups=False).reset_index()
ind = pw.drop(columns="geometry").merge(ind, on="pid").merge(reach, on="pid")
ind["pop_density_km2"] = ind["pop"] / ind.area_km2
ind["sc_st_share"] = (ind.sc_pop + ind.st_pop) / ind["pop"]
ind["pop_uncovered_500"] = ind["pop"] * (1 - ind.cov_500); ind["pop_uncovered_800"] = ind["pop"] * (1 - ind.cov_800)
ind["centroid_x"] = pw.geometry.centroid.x.values; ind["centroid_y"] = pw.geometry.centroid.y.values
# attach lon/lat centroids for web maps
cg = gpd.GeoSeries(gpd.points_from_xy(ind.centroid_x, ind.centroid_y), crs=CRS_UTM).to_crs(CRS_WGS84)
ind["lat"], ind["lon"] = cg.y.values, cg.x.values

cells_out = cells.drop(columns=["geometry", "w"]).copy()
cg2 = gpd.GeoSeries(gpd.points_from_xy(cells.x, cells.y), crs=CRS_UTM).to_crs(CRS_WGS84)
cells_out["lat"], cells_out["lon"] = cg2.y.values.astype(np.float32), cg2.x.values.astype(np.float32)
for c in ["x", "y", "pop", "sc_pop", "st_pop", "dist_nearest_m"]:
    cells_out[c] = cells_out[c].astype(np.float32)
cells_out.to_parquet(PROC / "grid_cells.parquet", index=False)
ind.to_parquet(PROC / "prabhag_indicators.parquet", index=False)
stops.to_parquet(PROC / "stops.parquet", index=False)
fac.to_parquet(PROC / "facilities.parquet", index=False)
pw[["pid", "prabhag", "admin_ward", "geometry"]].to_crs(CRS_WGS84).to_file(PROC / "prabhags.geojson", driver="GeoJSON")
gpd.read_file(RAW / "boundaries/bmc_admin_wards.geojson").to_file(PROC / "admin_wards.geojson", driver="GeoJSON")
print(ind[["cov_300", "cov_500", "cov_800"]].describe().round(3).T)
print("DONE", round(time.time() - t00), "s")
