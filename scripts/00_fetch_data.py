"""Step 0 - Download every raw input from its public source (idempotent).  python scripts/00_fetch_data.py [--force]

Sources (see docs/DATA_SOURCES.md for licences):
  * GTFS            https://github.com/croyla/mumbai-gtfs
  * Boundaries      https://github.com/datameet/Municipal_Spatial_Data  (Mumbai/)
  * MCGM health     https://github.com/aryamanx5/Mumbai_health-map       (raw KMLs of MCGM open data)
  * OSM education   https://github.com/yashveeeeeeer/india-geodata       (HOT OSM export; filtered to the MMR bbox)
"""
import sys, urllib.request
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.config import RAW

RAWG = "https://raw.githubusercontent.com"
FILES = {
    "mumbai_gtfs_compat.zip": f"{RAWG}/croyla/mumbai-gtfs/main/gtfs_compat.zip",
    "mumbai_gtfs_original.zip": f"{RAWG}/croyla/mumbai-gtfs/main/gtfs.zip",
    "boundaries/bmc_admin_wards.geojson": f"{RAWG}/datameet/Municipal_Spatial_Data/master/Mumbai/BMC_Wards.geojson",
    "boundaries/bmc_electoral_wards_2017.geojson": f"{RAWG}/datameet/Municipal_Spatial_Data/master/Mumbai/bmc_electoral_wards_2017",
    "boundaries/sra_slum_clusters.geojson": f"{RAWG}/datameet/Municipal_Spatial_Data/master/Mumbai/slumClusters.geojson",
    **{f"facilities/{n}.kml": f"{RAWG}/aryamanx5/Mumbai_health-map/main/data/raw/{n}.kml" for n in ["public_hospitals", "dispensaries", "uphcs", "maternity_hospitals"]},
    "facilities/mcgm_hospitals_list.csv": f"{RAWG}/aryamanx5/Mumbai_health-map/main/data/raw/mumbai_hospitals_list.csv",
}
EDU = f"{RAWG}/yashveeeeeeer/india-geodata/main/data/education/facilities/INDIA_EDUCATION_FACILITIES_POINTS.geojson"


def get(url, dest, force):
    dest = RAW / dest; dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists() and not force:
        print("have", dest.relative_to(RAW)); return
    print("get ", dest.relative_to(RAW)); urllib.request.urlretrieve(url, dest)


if __name__ == "__main__":
    force = "--force" in sys.argv
    for d, u in FILES.items(): get(u, d, force)
    out = RAW / "facilities/osm_education_mmr_hotosm.geojson"
    if force or not out.exists():
        import geopandas as gpd
        tmp = RAW / "facilities/_india_education.geojson"; get(EDU, "facilities/_india_education.geojson", True)
        gpd.read_file(tmp).cx[72.6:73.3, 18.8:19.6].to_file(out, driver="GeoJSON"); tmp.unlink()
        print("wrote", out.relative_to(RAW))
