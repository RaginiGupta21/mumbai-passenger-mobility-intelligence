"""Step 4 - Network analysis, clustering, equity tests, connectivity-gap detection and recommendations."""
import sys, json, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import numpy as np, pandas as pd, networkx as nx
from scipy import sparse, stats
from scipy.spatial import cKDTree
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import silhouette_score, davies_bouldin_score, adjusted_rand_score
from src.config import *
from src.common import load

SEED = 42; rng = np.random.default_rng(SEED); diag = {}
stops, st, trips, routes = load("stops"), load("stop_times"), load("trips"), load("routes")
cells, ind = load("grid_cells"), load("prabhag_indicators")

# ============ A. Stop network (NetworkX) ============
st = st.sort_values(["trip_idx", "seq"])
nxt = st.groupby("trip_idx").stop_idx.shift(-1); nx_arr = st.groupby("trip_idx").arr.shift(-1)
e = pd.DataFrame({"a": st.stop_idx, "b": nxt, "t": nx_arr - st.dep, "trip": st.trip_idx}).dropna(subset=["b"])
e["b"] = e.b.astype(int); e["route"] = e.trip.map(trips.set_index("trip_idx").route_idx)
e = e[e.a != e.b]
e["u"] = np.minimum(e.a, e.b); e["v"] = np.maximum(e.a, e.b)
eg = e.groupby(["u", "v"]).agg(n_trips=("trip", "size"), n_routes=("route", "nunique"), run_s=("t", "median")).reset_index()
eg["w"] = eg.run_s.clip(lower=30)
G = nx.Graph()
G.add_nodes_from(stops.stop_idx.tolist())
G.add_weighted_edges_from(eg[["u", "v", "w"]].itertuples(index=False, name=None), weight="w")
bus_components = nx.number_connected_components(G)
# interchange links: stops within 200 m treated as walkable transfers (walk time + 2 min buffer)
tree = cKDTree(stops[["x", "y"]].to_numpy()); pr = tree.query_pairs(200, output_type="ndarray")
for a, b in pr:
    d = float(np.hypot(*(tree.data[a] - tree.data[b])))
    if not G.has_edge(int(a), int(b)):
        G.add_edge(int(a), int(b), w=d * DETOUR_FACTOR / WALK_SPEED_MS + MIN_TRANSFER_S)
comps = sorted(nx.connected_components(G), key=len, reverse=True)
comp_id = {n: i for i, c in enumerate(comps) for n in c}
stops["component"] = stops.stop_idx.map(comp_id)
t0 = time.time()
bc = nx.betweenness_centrality(G, k=600, weight="w", seed=SEED, normalized=True)
print("betweenness", round(time.time() - t0), "s")
stops["degree"] = [G.degree(i) for i in stops.stop_idx]
stops["betweenness"] = stops.stop_idx.map(bc)
cutv = set(nx.articulation_points(nx.Graph((u, v) for u, v in G.edges() if G[u][v]["w"] is not None)))
stops["is_cut_vertex"] = stops.stop_idx.isin(cutv)
stops["stops_within_500"] = [len(x) - 1 for x in tree.query_ball_point(tree.data, 500)]
iso = stops[stops.component > 0].agency_id.value_counts().to_dict()
diag["network"] = dict(isolated_component_agencies=iso, nodes=G.number_of_nodes(), edges=G.number_of_edges(), components_bus_only=int(bus_components),
                       components_with_interchange=len(comps), largest_component_share=round(len(comps[0]) / G.number_of_nodes(), 4),
                       small_components=int(sum(len(c) < 50 for c in comps)), cut_vertices=int(len(cutv)))

# ============ B. Stop typology (KMeans) ============
def pick_k(X, ks=range(3, 8), sample=4000):
    res = {}
    for k in ks:
        km = KMeans(k, n_init=10, random_state=SEED).fit(X)
        idx = rng.choice(len(X), min(sample, len(X)), replace=False)
        res[k] = (silhouette_score(X[idx], km.labels_[idx]), davies_bouldin_score(X, km.labels_))
    k = max(res, key=lambda k: res[k][0])
    return k, {int(a): dict(silhouette=round(b[0], 3), davies_bouldin=round(b[1], 3)) for a, b in res.items()}

sf = stops[stops.in_greater_mumbai].copy()
feat = ["n_routes", "departures_day", "departures_peak_h", "degree", "betweenness", "stops_within_500"]
X = StandardScaler().fit_transform(np.log1p(sf[feat].to_numpy()))
k, scores = pick_k(X)
km = KMeans(k, n_init=20, random_state=SEED).fit(X); sf["cluster"] = km.labels_
order = sf.groupby("cluster").departures_day.mean().sort_values(ascending=False).index.tolist()
names = ["Major hubs", "Trunk-corridor stops", "Local stops", "Minor local stops", "Thin-service stops", "Very thin service", "Marginal stops"]
sf["stop_type"] = sf.cluster.map({c: names[i] for i, c in enumerate(order)})
stops = stops.merge(sf[["stop_idx", "stop_type"]], on="stop_idx", how="left")
diag["stop_clustering"] = dict(k=int(k), selection=scores, n=len(sf), features=feat,
                               profile=sf.groupby("stop_type")[["n_routes", "departures_day", "degree", "betweenness"]].mean().round(2).to_dict("index"),
                               sizes=sf.stop_type.value_counts().to_dict(),
                               note="log1p + z-score; k chosen by silhouette over k=3..7")
stops.to_parquet(PROC / "stop_features.parquet", index=False)

# ============ C. Route summary + typology ============
st["route_idx"] = st.trip_idx.map(trips.set_index("trip_idx").route_idx)
tr = st.groupby("trip_idx").agg(first_dep=("dep", "min"), last_arr=("arr", "max"), n_stops=("seq", "size"), length_m=("dist_prev_m", "sum"))
tr = tr.join(trips.set_index("trip_idx")[["route_idx", "direction_id", "trip_headsign"]])
tr["dur"] = tr.last_arr - tr.first_dep
pkt = tr[(tr.first_dep >= PEAK_START_H * 3600) & (tr.first_dep < PEAK_END_H * 3600)].groupby("route_idx").size() / (PEAK_END_H - PEAK_START_H)
rs = tr.groupby("route_idx").agg(trips_day=("dur", "size"), length_km=("length_m", lambda s: s.median() / 1000), median_stops=("n_stops", "median"),
                                 median_dur_min=("dur", lambda s: s.median() / 60), first_dep=("first_dep", "min"), last_dep=("first_dep", "max"))
rs["peak_trips_h"] = pkt.reindex(rs.index).fillna(0)
rs["span_h"] = (rs.last_dep - rs.first_dep) / 3600
rs["sched_speed_kmh"] = (rs.length_km / (rs.median_dur_min / 60)).replace([np.inf], np.nan)
rs["headway_peak_min"] = np.where(rs.peak_trips_h > 0, 60 / rs.peak_trips_h, np.nan)
rs = routes.set_index("route_idx")[["route_id", "agency_id", "route_short_name", "route_long_name"]].join(rs, how="inner").reset_index()
rs["speed_plausible"] = rs.sched_speed_kmh.between(5, 60)   # urban bus speeds outside 5-60 km/h indicate interpolated / degenerate stop times
rf = ["trips_day", "length_km", "span_h", "peak_trips_h"]   # speed deliberately excluded: unreliable in this feed
rsk = rs.dropna(subset=rf).copy()
speed_flag = dict(routes_with_speed=int(rs.sched_speed_kmh.notna().sum()), implausible_speed_routes=int((~rs.speed_plausible & rs.sched_speed_kmh.notna()).sum()))
Xr = StandardScaler().fit_transform(np.log1p(rsk[rf].clip(lower=0).to_numpy()))
kr, sr_ = pick_k(Xr, range(3, 7))
kmr = KMeans(kr, n_init=20, random_state=SEED).fit(Xr); rsk["cluster"] = kmr.labels_
ordr = rsk.groupby("cluster").trips_day.mean().sort_values(ascending=False).index.tolist()
rn = ["High-frequency routes", "Regular routes", "Low-frequency routes", "Sparse / limited-span routes", "Marginal routes", "Marginal routes (2)"]
rsk["route_type"] = rsk.cluster.map({c: rn[i] for i, c in enumerate(ordr)})
rs = rs.merge(rsk[["route_idx", "route_type"]], on="route_idx", how="left")
rs.to_parquet(PROC / "route_summary.parquet", index=False)
diag["route_clustering"] = dict(speed_quality=speed_flag, k=int(kr), selection=sr_, n=len(rsk), features=rf,
                                profile=rsk.groupby("route_type")[rf].median().round(1).to_dict("index"), sizes=rsk.route_type.value_counts().to_dict())

# ============ D. Prabhag connectivity index, clustering, spatial statistics ============
ind = ind.copy()
ind["college_nearest_f"] = ind.college_nearest_min.fillna(75); ind["ph_nearest_f"] = ind.public_hospital_nearest_min.fillna(75)
pct = lambda s: s.rank(pct=True) * 100
comp = pd.DataFrame({
    "Stop coverage (500 m)": pct(ind.cov_500), "Walk distance (shorter=better)": pct(-ind.mean_dist_m),
    "Peak service (trips/h)": pct(ind.trips_peak_h_500_popw), "Route choice": pct(ind.routes_500_popw),
    "Network reach (45 min)": pct(ind.area_reach_45),
    "Essential-facility reach": pct((pct(ind.college_n_60) + pct(ind.public_hospital_n_60) + pct(ind.primary_health_n_45)) / 3)})
ind["connectivity_index"] = comp.mean(axis=1)
for c in comp: ind["ci_" + c.split(" (")[0].lower().replace(" ", "_")] = comp[c]
# sensitivity: random weights (Dirichlet) -> rank stability of the equal-weight index
base = ind.connectivity_index.rank()
rhos, bottom = [], np.zeros(len(ind))
for _ in range(1000):
    w = rng.dirichlet(np.ones(comp.shape[1])); s = (comp * w).sum(axis=1)
    rhos.append(stats.spearmanr(base, s)[0]); bottom += (s.rank() <= 0.1 * len(ind))
ind["bottom_decile_stability"] = bottom / 1000
diag["index_sensitivity"] = dict(components=list(comp.columns), weights="equal (1/6) by default", spearman_median=round(float(np.median(rhos)), 3),
                                 spearman_p5=round(float(np.percentile(rhos, 5)), 3), draws=1000)
# clustering of prabhags
cf = ["cov_500", "mean_dist_m", "trips_peak_h_500_popw", "routes_500_popw", "area_reach_45", "college_n_60", "public_hospital_n_60", "primary_health_n_45", "pop_density_km2", "sc_st_share"]
Xp = StandardScaler().fit_transform(np.log1p(ind[cf].clip(lower=0).to_numpy()))
# k>=4: k=3 merely separates 4 outlier prabhags from a 199-prabhag majority (high silhouette, no planning value)
kp, sp_ = pick_k(Xp, range(4, 7), sample=len(Xp))
kmp = KMeans(kp, n_init=30, random_state=SEED).fit(Xp); ind["cluster"] = kmp.labels_
aris = [adjusted_rand_score(kmp.labels_, KMeans(kp, n_init=10, random_state=s).fit_predict(Xp)) for s in range(5)]
ordp = ind.groupby("cluster").connectivity_index.mean().sort_values(ascending=False).index.tolist()
pn = ["Highly connected core", "Well connected", "Partially covered", "Underserved periphery", "Marginal (5)", "Marginal (6)"]
ind["archetype"] = ind.cluster.map({c: pn[i] for i, c in enumerate(ordp)})
diag["prabhag_clustering"] = dict(k=int(kp), selection=sp_, features=cf, stability_ari_mean=round(float(np.mean(aris)), 3),
                                  profile=ind.groupby("archetype")[["pop", "cov_500", "trips_peak_h_500_popw", "connectivity_index", "pop_density_km2"]].mean().round(2).to_dict("index"),
                                  sizes=ind.archetype.value_counts().to_dict())
# Moran's I on connectivity index (k=6 nearest-neighbour weights, permutation test)
xy = ind[["centroid_x", "centroid_y"]].to_numpy(); nnb = cKDTree(xy).query(xy, 7)[1][:, 1:]
def moran(z):
    z = z - z.mean(); num = sum(z[i] * z[nnb[i]].sum() for i in range(len(z))); return (len(z) / (len(z) * 6)) * num / (z ** 2).sum()
z = ind.connectivity_index.to_numpy(); I = moran(z)
perm = np.array([moran(rng.permutation(z)) for _ in range(999)]); pval = (1 + (perm >= I).sum()) / 1000
diag["spatial_autocorrelation"] = dict(morans_I=round(float(I), 3), p_value=float(pval), permutations=999, weights="6 nearest neighbours (prabhag centroids)")
# local hotspot flag: prabhag in bottom quartile whose neighbours' mean is also bottom-quartile
q = ind.connectivity_index.quantile(0.25); nb_mean = ind.connectivity_index.to_numpy()[nnb].mean(axis=1)
ind["low_connectivity_hotspot"] = (ind.connectivity_index <= q) & (nb_mean <= np.quantile(nb_mean, 0.35))
ind["urban_density_flag"] = np.where(ind.pop_density_km2 >= 5000, "dense urban", "low density (may include park / port / industrial land)")
# equity tests
ok = ind[(ind.sc_pop > 0) & ind.sc_cov_500.notna()]
w_sc = stats.wilcoxon(ok.sc_cov_500 - ok.cov_500); okst = ind[(ind.st_pop > 0) & ind.st_cov_500.notna()]; w_st = stats.wilcoxon(okst.st_cov_500 - okst.cov_500)
tot = lambda m, col: float((ind[col] * ind[m]).sum() / ind[m].sum())
diag["equity"] = dict(city_cov_500=tot("pop", "cov_500"), sc_cov_500=tot("sc_pop", "sc_cov_500"), st_cov_500=tot("st_pop", "st_cov_500"),
                      wilcoxon_sc_p=float(w_sc.pvalue), wilcoxon_st_p=float(w_st.pvalue), n_sc=len(ok), n_st=len(okst),
                      slum_area_cov_500=float(cells[cells.is_slum].dist_nearest_m.le(500).mean()), non_slum_area_cov_500=float(cells[~cells.is_slum].dist_nearest_m.le(500).mean()))
# ward summary (BMC administrative wards as labelled in the electoral-ward file)
def wagg(g):
    P = g["pop"].sum(); return pd.Series({"prabhags": len(g), "pop": P, "cov_300": (g.cov_300 * g["pop"]).sum() / P, "cov_500": (g.cov_500 * g["pop"]).sum() / P,
                                         "cov_800": (g.cov_800 * g["pop"]).sum() / P, "pop_uncovered_500": g.pop_uncovered_500.sum(),
                                         "connectivity_index": np.average(g.connectivity_index, weights=g["pop"]),
                                         "trips_peak_h_500": np.average(g.trips_peak_h_500_popw, weights=g["pop"])})
ward = ind.groupby("admin_ward").apply(wagg, include_groups=False).reset_index()
ward.to_parquet(PROC / "ward_summary.parquet", index=False)

# ============ E. Connectivity gaps + prescriptive siting ============
cells["covered_500"] = cells.dist_nearest_m <= 500
cells["low_service"] = cells.covered_500 & (cells.trips_peak_h_500 < 4)
P = cells["pop"].sum()
gaps = dict(pop_total=float(P), pop_no_stop_500=float(cells.loc[~cells.covered_500, "pop"].sum()), pop_no_stop_800=float(cells.loc[cells.dist_nearest_m > 800, "pop"].sum()),
            pop_low_service=float(cells.loc[cells.low_service, "pop"].sum()))
unc = cells[(cells.dist_nearest_m > 500) & (cells["pop"] > 0)].reset_index(drop=True)
ut = cKDTree(unc[["x", "y"]].to_numpy()); Adj = ut.sparse_distance_matrix(ut, 500, output_type="coo_matrix").tocsr(); Adj.data[:] = 1; Adj = Adj + sparse.eye(len(unc), format="csr")
Adj.data[:] = 1
rem = unc["pop"].to_numpy().copy(); sites = []
for it in range(25):
    gain = Adj @ rem; j = int(np.argmax(gain))
    if gain[j] <= 0: break
    sites.append(dict(rank=it + 1, lat=float(unc.lat[j]), lon=float(unc.lon[j]), newly_covered_pop=float(gain[j]), prabhag=int(unc.prabhag[j]), admin_ward=unc.admin_ward[j]))
    rem[Adj[j].indices] = 0
sites = pd.DataFrame(sites); sites["cum_pop"] = sites.newly_covered_pop.cumsum(); sites["cum_share_of_uncovered"] = sites.cum_pop / gaps["pop_no_stop_500"]
sites.to_parquet(PROC / "new_stop_sites.parquet", index=False)
gaps["top25_sites_cover_pop"] = float(sites.newly_covered_pop.sum())
diag["gaps"] = gaps
thin = stops[stops.in_greater_mumbai & (stops.n_routes <= 1) & (stops.departures_day < 20)]
diag["thin_stops"] = dict(n=int(len(thin)), share=round(len(thin) / stops.in_greater_mumbai.sum(), 4), rule="single route and <20 scheduled departures per day")
ind.to_parquet(PROC / "prabhag_scores.parquet", index=False)
cells[["covered_500", "low_service"]].to_parquet(PROC / "grid_flags.parquet", index=False)

# ============ F. Auto-generated, number-backed recommendations ============
top = ind[ind.urban_density_flag == "dense urban"].sort_values("pop_uncovered_500", ascending=False).head(8)
recs = []
for _, r in top.iterrows():
    recs.append(dict(area=f"Prabhag {int(r.prabhag)} ({r.admin_ward})", pop=int(r["pop"]), uncovered_500=int(r.pop_uncovered_500), cov_500=float(r.cov_500),
                     connectivity_index=float(r.connectivity_index), archetype=r.archetype))
diag["priority_areas"] = recs
(PROC / "model_diagnostics.json").write_text(json.dumps(diag, indent=2, default=lambda o: o.item() if hasattr(o, "item") else str(o)))
print(json.dumps({k: diag[k] for k in ["network", "index_sensitivity", "spatial_autocorrelation", "equity", "gaps", "thin_stops"]}, indent=1, default=str))
print("stop k", k, scores); print("route k", kr, sr_); print("prabhag k", kp, sp_, "ARI", diag["prabhag_clustering"]["stability_ari_mean"])
print(pd.DataFrame(diag["prabhag_clustering"]["profile"]).T.round(2)); print(pd.DataFrame(diag["stop_clustering"]["profile"]).T.round(2))
