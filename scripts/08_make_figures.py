"""Step 8 - Static figures for the documentation (matplotlib), generated from the processed data."""
import sys, json
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import numpy as np, pandas as pd, geopandas as gpd, matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap
from src.config import *

FIG = DOCS / "figures"; FIG.mkdir(parents=True, exist_ok=True)
cm = LinearSegmentedColormap.from_list("soft", ["#E9D8C4", "#D9A86B", "#8FB3A5", "#3F7C85", "#2F4F63"])
bg = "#F5F2EB"
pg = gpd.read_file(PROC / "prabhags.geojson").to_crs(CRS_UTM)
ind = pd.read_parquet(PROC / "prabhag_scores.parquet"); stops = pd.read_parquet(PROC / "stop_features.parquet")
sites = pd.read_parquet(PROC / "new_stop_sites.parquet"); cells = pd.read_parquet(PROC / "grid_cells.parquet")
g = pg.merge(ind.drop(columns=["admin_ward"]), on="prabhag")
sg = stops[stops.in_greater_mumbai]

def setup(ax, title):
    ax.set_facecolor(bg); ax.set_axis_off(); import textwrap; ax.set_title("\n".join(textwrap.wrap(title, 48)), fontsize=12, color="#2F3E46", loc="left", pad=10)

def choropleth(col, title, fname, vmin=0, vmax=1, label="", extra=None):
    fig, ax = plt.subplots(figsize=(6.2, 8.4), facecolor=bg)
    g.plot(column=col, cmap=cm, vmin=vmin, vmax=vmax, ax=ax, edgecolor="white", linewidth=.3, legend=True, legend_kwds=dict(shrink=.5, label=label))
    if extra: extra(ax)
    setup(ax, title); fig.tight_layout(); fig.savefig(FIG / fname, dpi=140, facecolor=bg); plt.close(fig)

choropleth("cov_500", "Residents within 500 m of a bus stop (by prabhag)", "01_coverage_500m.png", label="share of residents")
choropleth("connectivity_index", "Connectivity Index (0-100, equal-weight, percentile-based)", "02_connectivity_index.png", 0, 100, "index")
def hot(ax):
    h = ind[ind.low_connectivity_hotspot]; hp = gpd.GeoSeries(gpd.points_from_xy(h.centroid_x, h.centroid_y), crs=CRS_UTM)
    hp.plot(ax=ax, facecolor="none", edgecolor="#8F4A45", markersize=70, linewidth=1.6)
choropleth("connectivity_index", "Low-connectivity hotspots (red rings)", "03_hotspots.png", 0, 100, "index", hot)
def newsites(ax):
    sg_ = gpd.GeoSeries(gpd.points_from_xy(sites.lon, sites.lat), crs=CRS_WGS84).to_crs(CRS_UTM)
    for p, r in zip(sg_, sites.itertuples()):
        ax.add_patch(plt.Circle((p.x, p.y), 500, color="#B8795A", alpha=.25)); ax.text(p.x, p.y, str(r.rank), ha="center", va="center", fontsize=7, color="#7A3F2A", weight="bold")
fig, ax = plt.subplots(figsize=(6.2, 8.4), facecolor=bg)
g.plot(color="#E9E4D8", edgecolor="white", linewidth=.3, ax=ax)
pts = gpd.GeoSeries(gpd.points_from_xy(sg.x, sg.y), crs=CRS_UTM); pts.plot(ax=ax, color="#41596E", markersize=1.2, alpha=.6)
newsites(ax); setup(ax, "Bus stops (blue) and 25 suggested new stop catchments (500 m)"); fig.tight_layout(); fig.savefig(FIG / "04_new_stop_catchments.png", dpi=140, facecolor=bg); plt.close(fig)

# stop typology
fig, ax = plt.subplots(figsize=(6.2, 8.4), facecolor=bg); g.plot(color="#EFEBE0", edgecolor="white", linewidth=.3, ax=ax)
col = {"Major hubs": "#B5707A", "Trunk-corridor stops": "#D9A86B", "Local stops": "#8FB3A5"}
for t, c in col.items():
    s = sg[sg.stop_type == t]; ax.scatter(s.x, s.y, s=10 if t != "Local stops" else 2, color=c, label=f"{t} ({len(s):,})", alpha=.85, linewidths=0)
ax.legend(loc="lower left", frameon=False, fontsize=8); setup(ax, "Stop typology (k-means, k=3)"); fig.tight_layout(); fig.savefig(FIG / "05_stop_typology.png", dpi=140, facecolor=bg); plt.close(fig)

# service levels + distance-curve
fig, axs = plt.subplots(1, 2, figsize=(12, 4.2), facecolor=bg)
d = np.arange(0, 2001, 25); w = cells["pop"].to_numpy(); dd = cells.dist_nearest_m.to_numpy()
axs[0].plot(d, [w[dd <= x].sum() / w.sum() for x in d], color="#3F7C85", lw=2.5)
for r in ACCESS_RADII_M: axs[0].axvline(r, ls=":", color="#B8795A"); axs[0].text(r + 8, .05, f"{r} m", color="#B8795A", fontsize=9)
axs[0].set_title("Cumulative share of residents by distance to nearest stop", loc="left", fontsize=11); axs[0].set_xlabel("metres (straight line)"); axs[0].set_ylim(0, 1.02); axs[0].set_facecolor("#FBF9F4")
pk = cells.trips_peak_h_500.to_numpy(); bands = np.select([pk == 0, pk < 4, pk < 10], ["No service", "<4/h", "4-10/h"], "10+/h")
s = pd.Series(w).groupby(bands).sum().reindex(["No service", "<4/h", "4-10/h", "10+/h"]); axs[1].bar(s.index, s.values / s.sum(), color=["#B5707A", "#D9A86B", "#8FB3A5", "#3F7C85"])
axs[1].set_title("Residents by AM-peak service (unique trips/hour within 500 m)", loc="left", fontsize=11); axs[1].set_facecolor("#FBF9F4")
for a in axs: [sp.set_visible(False) for k, sp in a.spines.items() if k in ("top", "right")]
fig.tight_layout(); fig.savefig(FIG / "06_distance_and_service.png", dpi=140, facecolor=bg); plt.close(fig)
print("figures:", sorted(p.name for p in FIG.glob("*.png")))
