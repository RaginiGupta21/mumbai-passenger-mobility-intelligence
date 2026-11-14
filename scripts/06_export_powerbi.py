"""Step 6 - Export tidy CSV tables for Power BI (star-schema friendly)."""
import sys, json
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import pandas as pd
from src.config import *

POWERBI.mkdir(parents=True, exist_ok=True)
ind = pd.read_parquet(PROC / "prabhag_scores.parquet"); stops = pd.read_parquet(PROC / "stop_features.parquet")
fac = pd.read_parquet(PROC / "facilities.parquet"); rs = pd.read_parquet(PROC / "route_summary.parquet")
sites = pd.read_parquet(PROC / "new_stop_sites.parquet"); ward = pd.read_parquet(PROC / "ward_summary.parquet")
cells = pd.read_parquet(PROC / "grid_cells.parquet")

dim_prabhag = ind.drop(columns=["centroid_x", "centroid_y", "cluster", "w"], errors="ignore")
dim_prabhag.to_csv(POWERBI / "dim_prabhag.csv", index=False)
stops[stops.in_greater_mumbai][["stop_id", "stop_name", "stop_lat", "stop_lon", "agency_id", "admin_ward", "n_routes", "departures_day", "departures_peak_h", "degree", "betweenness", "is_cut_vertex", "stops_within_500", "stop_type"]].to_csv(POWERBI / "dim_stop.csv", index=False)
rs.drop(columns=["route_idx"]).to_csv(POWERBI / "dim_route.csv", index=False)
fac[fac.usable][["fid", "name", "category", "group", "lat", "lon", "ward", "precision", "dist_stop_center_m", "dist_stop_min_m", "dist_stop_max_m",
                 "certain_300", "certain_500", "certain_800", "possible_300", "possible_500", "possible_800", "n_routes_500", "trips_day_500", "source"]].to_csv(POWERBI / "fact_facility_access.csv", index=False)
sites.to_csv(POWERBI / "fact_suggested_stop_catchments.csv", index=False)
ward.to_csv(POWERBI / "fact_ward_summary.csv", index=False)
# 100 m grid is large; export a 300 m aggregate for dashboards (sums of pop, means of access metrics)
c = cells.copy(); c["gx"] = (c.x // 300).astype(int); c["gy"] = (c.y // 300).astype(int)
agg = c.groupby(["gx", "gy"]).agg(lat=("lat", "mean"), lon=("lon", "mean"), pop=("pop", "sum"), dist_nearest_m=("dist_nearest_m", "mean"),
                                  trips_peak_h_500=("trips_peak_h_500", "mean"), prabhag=("prabhag", "first")).reset_index(drop=True)
agg.round(4).to_csv(POWERBI / "fact_grid_300m.csv", index=False)
print({f.name: f"{f.stat().st_size / 1e3:.0f} KB" for f in sorted(POWERBI.glob('*.csv'))})
