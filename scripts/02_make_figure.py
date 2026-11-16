"""Draw the overview figure used in the README.   Run:  python scripts/02_make_figure.py   (needs matplotlib)"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import geopandas as gpd, pandas as pd, matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap
from src.config import *

cm = LinearSegmentedColormap.from_list("gap", ["#EFE6D8", "#E3B88C", "#C9856B", "#9C5A55", "#6B3F46"])
g = gpd.read_file(PROC / "prabhags.geojson").to_crs(CRS_UTM); ward = g[g.admin_ward == STUDY_WARD]
sites = pd.read_parquet(PROC / "new_stop_sites.parquet"); stops = pd.read_parquet(PROC / "stops.parquet")
sp = gpd.GeoDataFrame(stops, geometry=gpd.points_from_xy(stops.stop_lon, stops.stop_lat), crs="EPSG:4326").to_crs(CRS_UTM)
st_ = gpd.GeoDataFrame(sites, geometry=gpd.points_from_xy(sites.lon, sites.lat), crs="EPSG:4326").to_crs(CRS_UTM)
fig, ax = plt.subplots(1, 2, figsize=(12, 5.6), facecolor="#F5F2EB")
ward.plot(column="underserved_share", cmap=cm, vmin=0, vmax=1, edgecolor="white", linewidth=.8, ax=ax[0], legend=True, legend_kwds={"shrink": .6, "label": "share of residents underserved"})
for _, r in ward.iterrows():
    c = r.geometry.representative_point(); ax[0].text(c.x, c.y, int(r.prabhag), fontsize=7, ha="center", color="#2F3E46")
ax[0].set_title(f"Service gap by prabhag: {ward_label()}", loc="left", fontsize=12, color="#2F3E46")
ward.plot(color="#EFE6D8", edgecolor="white", linewidth=.8, ax=ax[1])
sp[sp.within(ward.union_all().buffer(NEAR_M))].plot(ax=ax[1], color="#2F4F63", markersize=4, alpha=.8)
for p, r in zip(st_.geometry, sites.itertuples()):
    ax[1].add_patch(plt.Circle((p.x, p.y), NEAR_M, color="#3F7C85" if r.area_type == "dense residential" else "#B8795A", alpha=.22)); ax[1].text(p.x, p.y, str(r.rank), ha="center", va="center", fontsize=8, weight="bold", color="#1F3F4A")
ax[1].set_title("Existing stops and 10 suggested new stop areas (orange = lower-density prabhag)", loc="left", fontsize=12, color="#2F3E46")
for a in ax: a.set_axis_off(); a.set_facecolor("#F5F2EB")
fig.tight_layout(); (DOCS := ROOT / "docs").mkdir(exist_ok=True); fig.savefig(DOCS / "overview.png", dpi=130, facecolor="#F5F2EB")
print("saved docs/overview.png")
