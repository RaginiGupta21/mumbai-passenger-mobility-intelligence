"""Facility loaders (all real data; no synthetic points) with explicit coordinate-precision handling."""
from __future__ import annotations
import re, xml.etree.ElementTree as ET
import numpy as np, pandas as pd, geopandas as gpd
from .config import *

KML_FILES = {"public_hospitals.kml": "Public hospital", "maternity_hospitals.kml": "Maternity home",
             "uphcs.kml": "UPHC (urban primary health centre)", "dispensaries.kml": "Dispensary"}


def _dec(s: str) -> int:
    return len(s.split(".")[1]) if "." in s else 0


def load_mcgm_health() -> pd.DataFrame:
    """MCGM public health facility KMLs. Coordinates in the source are rounded (mostly 2 decimals ~ +/-0.5 km)."""
    rows = []
    for f, cat in KML_FILES.items():
        root = ET.parse(RAW / "facilities" / f).getroot()
        for pm in root.iter("{http://www.opengis.net/kml/2.2}Placemark"):
            nm = (pm.findtext("{http://www.opengis.net/kml/2.2}n") or pm.findtext("{http://www.opengis.net/kml/2.2}name") or "").strip()
            ext = {sd.get("name"): (sd.text or "").strip() for sd in pm.iter("{http://www.opengis.net/kml/2.2}SimpleData")}
            c = pm.findtext(".//{http://www.opengis.net/kml/2.2}coordinates")
            if not c or not c.strip():
                continue
            lon_s, lat_s = c.strip().split(",")[:2]
            rows.append(dict(name=nm.title() if nm.isupper() else nm, category=cat, group="Health", lon=float(lon_s), lat=float(lat_s),
                             decimals=min(_dec(lon_s), _dec(lat_s)), ward=ext.get("WARD", ""), address=ext.get("ADDRESS", ext.get("UPHC_Addre", "")),
                             subtype=ext.get("TYPE", ""), source="MCGM open data (via data.opencity.in), KML", ))
    return pd.DataFrame(rows)


def load_osm_education() -> pd.DataFrame:
    g = gpd.read_file(RAW / "facilities" / "osm_education_mmr_hotosm.geojson")
    g = g[g.amenity.isin(["college", "university"])].copy()
    g["name"] = g["name:en"].fillna(g["name"]).fillna("(unnamed college/university - OSM)")
    return pd.DataFrame(dict(name=g.name.values, category=g.amenity.str.title().values, group="Education", lon=g.geometry.x.values,
                             lat=g.geometry.y.values, decimals=7, ward="", address="", subtype=g.amenity.values,
                             source="OpenStreetMap contributors (HOT export, 2024), ODbL"))


def uncertainty_half_widths_m(decimals: int, lat: float) -> tuple[float, float]:
    """Half-width of the rounding box (N-S, E-W) in metres for coordinates rounded to `decimals`."""
    h = 0.5 * 10 ** (-decimals)
    return h * 111_320.0, h * 111_320.0 * np.cos(np.radians(lat))
