"""Settings for the study. Change STUDY_WARD to analyse a different ward (e.g. "M - East"), then rerun the data script."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
PROC = ROOT / "data" / "processed"
GTFS_ZIP = RAW / "mumbai_gtfs_compat.zip"
WARDS_FILE = RAW / "boundaries" / "bmc_electoral_wards_2017.geojson"

STUDY_WARD = "P - North"          # BMC administrative ward studied in detail (as named in the ward file)

CRS_UTM = "EPSG:32643"            # metric map projection for Mumbai
NEAR_M = 500                      # a stop within this straight-line distance counts as "near"
LOW_FREQ = 10                     # fewer scheduled trips per peak hour than this counts as low frequency
PEAK_START_H, PEAK_END_H = 8, 10  # morning peak window
GRID_M = 100                      # size of the grid cells used to place residents
N_NEW_STOPS = 10                  # how many new stop areas to suggest in the study ward


def ward_label(ward: str = STUDY_WARD) -> str:
    return ward.replace(" - ", "-") + " ward"
