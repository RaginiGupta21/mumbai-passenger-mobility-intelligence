"""Step 5 - Build a searchable 'place' index: stops sharing a name and lying within 600 m form one place."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import numpy as np, pandas as pd, geopandas as gpd
from scipy.cluster.hierarchy import linkage, fcluster
from src.config import *

stops = pd.read_parquet(PROC / "stop_features.parquet")
rows = []
for name, g in stops.groupby("stop_name"):
    if len(g) == 1:
        lab = np.zeros(1, int)
    else:
        lab = fcluster(linkage(g[["x", "y"]].to_numpy(), "single"), 600, "distance") - 1
    for c in np.unique(lab):
        h = g[lab == c]
        rows.append(dict(name=name, x=h.x.mean(), y=h.y.mean(), stop_idx=h.stop_idx.tolist(), n_stops=len(h),
                         agency=",".join(sorted(h.agency_id.unique())), ward=h.admin_ward.dropna().mode().iat[0] if h.admin_ward.notna().any() else "",
                         in_gm=bool(h.in_greater_mumbai.any()), trips_day=float(h.departures_day.sum())))
pl = pd.DataFrame(rows)
g = gpd.GeoSeries(gpd.points_from_xy(pl.x, pl.y), crs=CRS_UTM).to_crs(CRS_WGS84); pl["lat"], pl["lon"] = g.y.values, g.x.values
area = np.where(pl.ward != "", "Ward " + pl.ward.astype(str), pl.agency)
pl["label"] = pl.name
dup = pl.duplicated("name", keep=False)
pl.loc[dup, "label"] = pl.name[dup] + " - " + pd.Series(area, index=pl.index)[dup]
dup2 = pl.duplicated("label", keep=False)
pl.loc[dup2, "label"] = pl.label[dup2] + " #" + (pl[dup2].groupby("label").cumcount() + 1).astype(str)
pl = pl.sort_values("label").reset_index(drop=True); pl["place_id"] = np.arange(len(pl))
pl.to_parquet(PROC / "places.parquet", index=False)
print(len(pl), "places;", int(dup.sum()), "stops with ambiguous names disambiguated")
