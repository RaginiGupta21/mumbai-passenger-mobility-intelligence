"""Cached data access for the Streamlit app."""
import json
import geopandas as gpd
import pandas as pd
import streamlit as st
from .config import PROC
from .timetable import Timetable


@st.cache_resource(show_spinner="Loading timetable (99k scheduled trips)...")
def get_tt() -> Timetable:
    return Timetable.load()


@st.cache_data(show_spinner=False)
def get_data() -> dict:
    d = {n: pd.read_parquet(PROC / f"{f}.parquet") for n, f in dict(
        stops="stop_features", places="places", fac="facilities", cells="grid_cells", flags="grid_flags", ind="prabhag_scores",
        routes="route_summary", sites="new_stop_sites", ward="ward_summary", routes_raw="routes", trips="trips").items()}
    d["cells"] = pd.concat([d["cells"], d["flags"]], axis=1)
    d["diag"] = json.load(open(PROC / "model_diagnostics.json")); d["dq"] = json.load(open(PROC / "data_quality_gtfs.json"))
    d["prabhag_geo"] = json.load(open(PROC / "prabhags.geojson"))
    st_times = pd.read_parquet(PROC / "stop_times.parquet", columns=["trip_idx", "seq", "dep"])
    first = st_times[st_times.seq == st_times.groupby("trip_idx").seq.transform("min")]
    d["trip_first"] = first.set_index("trip_idx").dep
    return d
