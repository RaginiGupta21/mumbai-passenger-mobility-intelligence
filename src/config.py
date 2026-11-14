"""Central configuration: paths, projection, analysis parameters."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
PROC = ROOT / "data" / "processed"
OUT = ROOT / "outputs"
DOCS = ROOT / "docs"
POWERBI = ROOT / "powerbi" / "data"

GTFS_ZIP = RAW / "mumbai_gtfs_compat.zip"

CRS_WGS84 = "EPSG:4326"
CRS_UTM = "EPSG:32643"          # UTM zone 43N - metric CRS for Mumbai

# Walking assumptions (documented in docs/METHODOLOGY.md)
WALK_SPEED_MS = 1.2             # m/s  (~4.3 km/h)
DETOUR_FACTOR = 1.3             # straight-line -> street-network proxy (no OSM roads available offline)
MIN_TRANSFER_S = 120            # minimum buffer between alighting and boarding (times are partly interpolated)
MAX_TRANSFER_WALK_M = 400       # stop-to-stop walking links (straight-line)
ACCESS_RADII_M = (300, 500, 800)
GRID_M = 100                    # accessibility grid resolution
PEAK_START_H, PEAK_END_H = 8, 10  # AM peak window used for level-of-service

# Level of service (peak departures per hour within 500 m)
LOS_BANDS = [(0, "No service"), (4, "Low (<4/h)"), (10, "Moderate (4-10/h)"), (10**9, "High (10+/h)")]

# Muted palette (soft, non-neon, non-black)
PALETTE = {
    "bg": "#F5F2EB", "panel": "#FFFFFF", "ink": "#2F3E46", "muted": "#6B7B83",
    "teal": "#3F7C85", "sage": "#7FA38F", "sand": "#D9C7A3", "clay": "#B8795A",
    "navy": "#41596E", "rose": "#B5707A", "gold": "#C9A25B", "mist": "#DCE5E4",
}
