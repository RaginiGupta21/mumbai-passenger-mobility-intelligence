"""Step 1 - Load the Mumbai GTFS feed, audit its quality, and write clean parquet tables.

Nothing is invented: every value comes from the feed. Quality issues are *flagged*, not silently fixed.
"""
import io, json, sys, zipfile
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import numpy as np, pandas as pd, geopandas as gpd
from src.config import *
from src.common import haversine_m, hms_to_s

PROC.mkdir(parents=True, exist_ok=True)
z = zipfile.ZipFile(GTFS_ZIP)
rd = lambda n, **k: pd.read_csv(io.BytesIO(z.read(n)), **k)
agency = rd("agency.txt", dtype=str)
routes = rd("routes.txt", dtype=str)
stops = rd("stops.txt", dtype={"stop_id": str})
trips = rd("trips.txt", dtype=str)
cal = rd("calendar.txt", dtype=str)
feed = rd("feed_info.txt", dtype=str)
st = rd("stop_times.txt", dtype={"trip_id": str, "stop_id": str})
dq = {"files_present": sorted(z.namelist()), "feed_info": feed.iloc[0].to_dict()}

# ---------- integrity ----------
dq["counts"] = dict(agencies=len(agency), routes=len(routes), stops=len(stops), trips=len(trips), stop_times=len(st))
dq["integrity"] = {
    "stops_duplicate_id": int(stops.stop_id.duplicated().sum()),
    "stops_missing_coords": int(stops[["stop_lat", "stop_lon"]].isna().any(axis=1).sum()),
    "trips_without_stop_times": int((~trips.trip_id.isin(st.trip_id)).sum()),
    "stop_times_orphan_trip": int((~st.trip_id.isin(trips.trip_id)).sum()),
    "stop_times_orphan_stop": int((~st.stop_id.isin(stops.stop_id)).sum()),
    "stops_never_served": int((~stops.stop_id.isin(st.stop_id)).sum()),
    "trips_orphan_route": int((~trips.route_id.isin(routes.route_id)).sum()),
    "routes_without_trips": int((~routes.route_id.isin(trips.route_id)).sum()),
    "trips_missing_headsign": int(trips.trip_headsign.isna().sum()),
}
dq["calendar"] = {"service_ids": cal.service_id.tolist(), "start": cal.start_date.min(), "end": cal.end_date.max(),
                  "days_active": cal.iloc[0, 1:8].astype(int).tolist(), "calendar_dates_file": "calendar_dates.txt" in z.namelist(),
                  "note": "A single service pattern runs all 7 days: the feed does not distinguish weekday/weekend timetables."}
dq["shapes_file"] = "shapes.txt" in z.namelist()
dq["frequencies_file"] = "frequencies.txt" in z.namelist()

# ---------- time logic ----------
st["arr"] = hms_to_s(st.arrival_time); st["dep"] = hms_to_s(st.departure_time)
st = st.sort_values(["trip_id", "stop_sequence"], kind="stable").reset_index(drop=True)
g = st.groupby("trip_id", sort=False)
st["dt"] = g.arr.diff()
dq["time_logic"] = {
    "dep_before_arr": int((st.dep < st.arr).sum()),
    "negative_time_steps": int((st.dt < 0).sum()),
    "zero_time_steps_share": round(float((st.dt == 0).sum() / st.dt.notna().sum()), 4),
    "timepoint_share": round(float(st.timepoint.mean()), 4),
    "times_after_24h": int((st.arr >= 86400).sum()),
    "max_time_h": round(float(st.arr.max() / 3600), 1),
    "trips_single_stop": int((g.size() < 2).sum()),
}

# ---------- spatial ----------
stops["stop_lat"] = stops.stop_lat.astype(float); stops["stop_lon"] = stops.stop_lon.astype(float)
stops["agency_id"] = stops.stop_id.str.split("_").str[0]
gm = gpd.read_file(RAW / "boundaries/bmc_admin_wards.geojson").to_crs(CRS_UTM)
sg = gpd.GeoDataFrame(stops, geometry=gpd.points_from_xy(stops.stop_lon, stops.stop_lat), crs=CRS_WGS84).to_crs(CRS_UTM)
stops["x"] = sg.geometry.x.values; stops["y"] = sg.geometry.y.values
gmu = gm.union_all().buffer(250)    # 250 m tolerance for stops on the boundary / creek edges
stops["in_greater_mumbai"] = sg.within(gmu).values
j = gpd.sjoin(sg[["geometry"]], gm[["name", "geometry"]].rename(columns={"name": "admin_ward"}), how="left", predicate="within")
stops["admin_ward"] = j.admin_ward.groupby(level=0).first().reindex(stops.index).values

# implied speed between consecutive stops (flag implausible segments, do not delete)
sx = stops.set_index("stop_id")
st["lat"] = st.stop_id.map(sx.stop_lat); st["lon"] = st.stop_id.map(sx.stop_lon)
st["d_m"] = haversine_m(st.groupby("trip_id").lat.shift(), st.groupby("trip_id").lon.shift(), st.lat, st.lon)
mv = st[(st.dt > 0) & st.d_m.notna()]
spd = (mv.d_m / mv.dt) * 3.6
dq["spatial"] = {
    "stops_by_agency": stops.agency_id.value_counts().to_dict(),
    "stops_in_greater_mumbai": int(stops.in_greater_mumbai.sum()),
    "bbox": [round(stops.stop_lon.min(), 4), round(stops.stop_lat.min(), 4), round(stops.stop_lon.max(), 4), round(stops.stop_lat.max(), 4)],
    "unique_stop_names": int(stops.stop_name.nunique()),
    "segments_speed_gt_80kmh_share": round(float((spd > 80).mean()), 5),
    "segments_speed_gt_80kmh": int((spd > 80).sum()),
    "median_segment_speed_kmh": round(float(spd.median()), 1),
}

# ---------- write clean tables with compact integer keys ----------
stops = stops.reset_index(drop=True); stops["stop_idx"] = np.arange(len(stops), dtype=np.int32)
stop_idx = stops.set_index("stop_id").stop_idx
trips = trips.reset_index(drop=True); trips["trip_idx"] = np.arange(len(trips), dtype=np.int32)
trip_idx = trips.set_index("trip_id").trip_idx
routes = routes.reset_index(drop=True); routes["route_idx"] = np.arange(len(routes), dtype=np.int32)
route_idx = routes.set_index("route_id").route_idx
trips["route_idx"] = trips.route_id.map(route_idx).astype(np.int32)
trips["agency_id"] = trips.route_id.map(routes.set_index("route_id").agency_id)
trips["direction_id"] = pd.to_numeric(trips.direction_id, errors="coerce")
out = pd.DataFrame({"trip_idx": st.trip_id.map(trip_idx).astype(np.int32), "stop_idx": st.stop_id.map(stop_idx).astype(np.int32),
                    "seq": st.stop_sequence.astype(np.int16), "arr": st.arr.astype(np.int32), "dep": st.dep.astype(np.int32),
                    "timepoint": st.timepoint.astype(np.int8), "dist_prev_m": st.d_m.fillna(0).astype(np.float32)})
out.to_parquet(PROC / "stop_times.parquet", index=False)
stops.drop(columns=[]).to_parquet(PROC / "stops.parquet", index=False)
routes.to_parquet(PROC / "routes.parquet", index=False)
trips.to_parquet(PROC / "trips.parquet", index=False)
cal.to_parquet(PROC / "calendar.parquet", index=False)
agency.to_parquet(PROC / "agency.parquet", index=False)
(PROC / "data_quality_gtfs.json").write_text(json.dumps(dq, indent=2, default=str))
print(json.dumps(dq, indent=2, default=str))
