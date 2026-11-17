"""Small helpers for the app: load the processed data, colour ramp, map layers and recommendation text."""
import json
import folium
import pandas as pd
from .config import *

TILES = "https://tile.openstreetmap.org/{z}/{x}/{y}.png"   # standard OpenStreetMap map tiles: free and no API key needed
ATTR = "© OpenStreetMap contributors"
COLORS = ("#EFE6D8", "#E3B88C", "#C9856B", "#9C5A55", "#6B3F46")           # soft light-to-dark scale (more gap = darker)


def load_data() -> dict:
    d = {"sites": pd.read_parquet(PROC / "new_stop_sites.parquet"), "wards": pd.read_parquet(PROC / "ward_summary.parquet"),
         "cells": pd.read_parquet(PROC / "study_cells.parquet"), "stops": pd.read_parquet(PROC / "stops.parquet"), "all_cells": pd.read_parquet(PROC / "cells.parquet"),
         "meta": json.load(open(PROC / "data_quality.json"))}
    geo = json.load(open(PROC / "prabhags.geojson"))
    d["geo"] = geo
    d["pr"] = pd.DataFrame([f["properties"] for f in geo["features"]])
    return d


def ramp(v, vmin, vmax, colors=COLORS) -> str:
    t = 0 if vmax == vmin else max(0.0, min(1.0, (v - vmin) / (vmax - vmin)))
    n = len(colors) - 1; i = min(int(t * n), n - 1); f = t * n - i
    a = [int(colors[i][k:k + 2], 16) for k in (1, 3, 5)]; b = [int(colors[i + 1][k:k + 2], 16) for k in (1, 3, 5)]
    return "#%02x%02x%02x" % tuple(int(a[j] + (b[j] - a[j]) * f) for j in range(3))


def base_map(center=None, zoom=12):
    m = folium.Map(location=center or [19.07, 72.88], zoom_start=zoom, tiles=None, control_scale=True)
    folium.TileLayer(tiles=TILES, attr=ATTR, max_zoom=19, name="Basemap").add_to(m)
    return m


def ward_view(d):
    """Centre and zoom level that show the whole study ward (more reliable than fit_bounds inside Streamlit)."""
    lons, lats = [], []

    def walk(c):
        if isinstance(c[0], (int, float)):
            lons.append(c[0]); lats.append(c[1])
        else:
            for x in c:
                walk(x)
    for f in d["geo"]["features"]:
        if f["properties"]["admin_ward"] == STUDY_WARD:
            walk(f["geometry"]["coordinates"])
    span = max(max(lons) - min(lons), (max(lats) - min(lats)) * 1.6)
    zoom = 11 if span > 0.2 else 12 if span > 0.09 else 13
    return [(min(lats) + max(lats)) / 2, (min(lons) + max(lons)) / 2], zoom


MEASURES = {   # label -> (column, tooltip format, is a higher value worse?, what the colours mean)
    "Underserved share of residents": ("underserved_share", "{:.0%}", True, "Darker = a larger share of residents underserved."),
    "Residents with no stop within 500 m": ("no_stop_pop", "{:,.0f}", True, "Darker = more residents with no bus stop within 500 m."),
    "Residents with a stop but low frequency": ("low_freq_pop", "{:,.0f}", True, "Darker = more residents who have a stop nearby but few buses."),
    "Peak-hour bus trips (supply)": ("peak_trips_h", "{:.0f} per hour", False, "Darker = FEWER bus trips per peak hour (a bigger supply gap)."),
    "Residents (demand)": ("pop", "{:,.0f}", True, "Darker = more residents. This shows where people live, not where service is missing."),
}


def colour_for(label, v, lo, hi):
    """Colour of one area. Darker always means 'more of a gap'; for supply measures (more is better) the scale is flipped."""
    worse_when_high = MEASURES[label][2]
    return ramp(v, lo, hi) if worse_when_high else ramp(v, hi, lo)


def choropleth(m, d, label, ward_only=True):
    col, fmt, _, _ = MEASURES[label]
    df = d["pr"].set_index("prabhag")
    shown = df[df.admin_ward == STUDY_WARD] if ward_only else df
    vmin, vmax = float(shown[col].min()), float(shown[col].max())
    feats = []
    for f in d["geo"]["features"]:
        p = f["properties"]
        if ward_only and p["admin_ward"] != STUDY_WARD:
            continue
        q = dict(p, label=f"Prabhag {p['prabhag']} ({p['admin_ward']})", residents=f"{p['pop']:,.0f}", value=fmt.format(p[col]),
                 underserved=f"{p['underserved_pop']:,.0f} ({p['underserved_share']:.0%})", v=float(p[col]))
        feats.append({"type": "Feature", "geometry": f["geometry"], "properties": q})
    folium.GeoJson({"type": "FeatureCollection", "features": feats},
                   style_function=lambda f: dict(fillColor=colour_for(label, f["properties"]["v"], vmin, vmax), color="#FFFFFF", weight=1, fillOpacity=.78),
                   highlight_function=lambda f: dict(weight=3, color="#2F3E46"),
                   tooltip=folium.GeoJsonTooltip(fields=["label", "residents", "value", "underserved"], aliases=["", "Residents", label, "Underserved"], sticky=True)).add_to(m)
    return vmin, vmax


def stops_layer(m, d):
    feats = [{"type": "Feature", "geometry": {"type": "Point", "coordinates": [r.stop_lon, r.stop_lat]},
              "properties": {"name": r.stop_name, "trips": f"{r.peak_trips_h:.0f}"}} for r in d["stops"].itertuples()]
    folium.GeoJson({"type": "FeatureCollection", "features": feats}, name="Bus stops",
                   marker=folium.CircleMarker(radius=2.5, weight=0, fill=True, fill_color="#2F4F63", fill_opacity=.8),
                   tooltip=folium.GeoJsonTooltip(fields=["name", "trips"], aliases=["Stop", "Peak trips/hour"])).add_to(m)


def recommendations(d) -> list:
    pr, sites, w = d["pr"], d["sites"], d["wards"]
    s = pr[pr.admin_ward == STUDY_WARD]
    ward = w[w.is_study_ward].iloc[0]
    dense_pr = s[s.area_type == "dense residential"]; thin_pr = s[s.area_type != "dense residential"]
    top_no_stop = dense_pr.sort_values("no_stop_pop", ascending=False).head(3)
    top_low = s.sort_values("low_freq_pop", ascending=False).head(3)
    by_site = sites.groupby("prabhag").newly_covered.sum().sort_values(ascending=False).head(3)
    if sites.empty:
        return [f"Every resident of the {ward_label()} already has a bus stop within {NEAR_M} m, so no new stop areas are suggested.",
                (f"{ward.low_freq_pop:,.0f} residents have a stop nearby but fewer than {LOW_FREQ} scheduled trips per peak hour; more frequent service there would help most."
                 if ward.low_freq_pop > 0 else f"Service is also adequate: no resident has a stop nearby with fewer than {LOW_FREQ} scheduled trips per peak hour.")]
    dense = sites[sites.area_type == "dense residential"]; thin = sites[sites.area_type != "dense residential"]
    first = (f"Add stops in the {len(sites)} suggested areas. Together they would bring about {sites.cumulative_covered.iloc[-1]:,.0f} residents within {NEAR_M} m of a stop "
             f"({sites.cumulative_share_of_no_stop.iloc[-1]:.0%} of those currently without one). {len(dense)} of the {len(sites)} sites are in dense residential prabhags "
             f"(about {dense.newly_covered.sum():,.0f} residents). The other {len(thin)} (about {thin.newly_covered.sum():,.0f} residents) are in large, lower-density prabhags "
             f"({', '.join(map(str, sorted(thin.prabhag.unique())))}) where residents are probably clustered in a few settlements, so check those on the ground first.")
    return [
        first,
        f"Start with the dense residential prabhags where the most residents have no stop nearby: {', '.join(f'{int(r.prabhag)} (about {r.no_stop_pop:,.0f})' for r in top_no_stop.itertuples())}. "
        f"Prabhags {', '.join(str(int(x)) for x in thin_pr.sort_values('no_stop_pop', ascending=False).prabhag)} also show large gaps, but their numbers are less certain because they are big and sparsely built-up.",
        f"Add or lengthen bus trips where a stop exists but service is thin. Prabhags {', '.join(f'{int(r.prabhag)} (about {r.low_freq_pop:,.0f} residents)' for r in top_low.itertuples())} "
        f"have the most residents in that situation. In the whole ward {ward.low_freq_pop:,.0f} residents are affected.",
        "Treat these as starting points for planners, not final decisions: they ignore roads, land use and real passenger counts (see 'How this was calculated, and its limits' at the top of the page).",
    ]


def add_pin(m, pin, info):
    """Marker for a searched place, its 500 m reach, and a dashed line to the nearest bus stop."""
    folium.Circle((pin["lat"], pin["lon"]), radius=NEAR_M, color="#3F7C85", weight=1.5, fill=True, fill_opacity=.08).add_to(m)
    if info:
        folium.PolyLine([(pin["lat"], pin["lon"]), (info["nearest_stop_lat"], info["nearest_stop_lon"])], color="#2F4F63", weight=2, dash_array="5 6",
                        tooltip=f"Nearest stop: {info['nearest_stop']} ({info['nearest_stop_m']:.0f} m)").add_to(m)
    folium.Marker((pin["lat"], pin["lon"]), icon=folium.Icon(color="red", icon="map-marker", prefix="fa"), tooltip=pin["label"]).add_to(m)
