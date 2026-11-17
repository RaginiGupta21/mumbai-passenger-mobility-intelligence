"""Find a place on the map: pasted coordinates, bus-stop names (works offline) and addresses (OpenStreetMap Nominatim).

Nominatim is a free service run by the OpenStreetMap community. Its usage policy asks for: a User-Agent that
identifies the app, at most 1 request per second, no search-as-you-type, and caching of results. This module
follows that (one request per button press, cached, rate-limited). It is meant for light use such as a student demo.
"""
import json
import re
import threading
import time
import urllib.error
import urllib.parse
import urllib.request

import numpy as np

from .config import NEAR_M, LOW_FREQ

USER_AGENT = "mumbai-service-gap-analysis/1.0 (student project; github.com/RaginiGupta21/mumbai-passenger-mobility-intelligence)"
NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
VIEWBOX = (72.75, 19.32, 73.00, 18.88)       # left, top, right, bottom: roughly Greater Mumbai
_CACHE: dict = {}                            # only successful answers are kept
_LOCK = threading.Lock()
_last_call = [0.0]


def parse_latlon(text: str):
    """'19.18, 72.84' (as copied from Google Maps) -> (19.18, 72.84), or None if the text is not two numbers."""
    m = re.fullmatch(r"\s*(-?\d{1,3}(?:\.\d+)?)\s*[, ]\s*(-?\d{1,3}(?:\.\d+)?)\s*", text or "")
    if not m:
        return None
    a, b = float(m.group(1)), float(m.group(2))
    if (abs(a) > 90 and abs(b) <= 90) or (70 <= a <= 75 and 15 <= b <= 22):   # given as longitude, latitude (Mumbai is near 72.8E, 19N)
        a, b = b, a
    return (a, b) if abs(a) <= 90 and abs(b) <= 180 else None


def search_stops(stops, text: str, limit: int = 5) -> list:
    """Bus stops whose name contains the text. Works without internet."""
    text = (text or "").strip()
    if len(text) < 2:
        return []
    hit = stops[stops.stop_name.str.contains(re.escape(text), case=False, na=False)]
    hit = hit.drop_duplicates("stop_name").head(limit)
    return [{"label": f"Bus stop: {r.stop_name}", "lat": float(r.stop_lat), "lon": float(r.stop_lon), "kind": "stop"} for r in hit.itertuples()]


def geocode(text: str, limit: int = 5, timeout: int = 8):
    """Look up an address or place name. Returns (results, error_message); error_message is None on success."""
    text = (text or "").strip()
    if len(text) < 3:
        return [], None
    key = text.lower()
    if key in _CACHE:
        return _CACHE[key], None
    params = {"q": text, "format": "jsonv2", "limit": limit, "countrycodes": "in", "bounded": 1,
              "viewbox": ",".join(str(v) for v in VIEWBOX)}
    req = urllib.request.Request(NOMINATIM_URL + "?" + urllib.parse.urlencode(params), headers={"User-Agent": USER_AGENT})
    with _LOCK:                              # stay under 1 request per second
        wait = 1.1 - (time.time() - _last_call[0])
        if wait > 0:
            time.sleep(wait)
        _last_call[0] = time.time()
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        except (urllib.error.URLError, TimeoutError, OSError, ValueError) as e:
            return [], f"The address search service could not be reached ({type(e).__name__}). Try a bus stop name or paste coordinates instead."
    results = [{"label": "Address: " + d["display_name"][:110], "lat": float(d["lat"]), "lon": float(d["lon"]), "kind": "address"} for d in data]
    _CACHE[key] = results
    return results, None


def find(text: str, stops):
    """Everything we can find for the text. Returns (candidates, message)."""
    ll = parse_latlon(text)
    if ll:
        return [{"label": f"Coordinates {ll[0]:.5f}, {ll[1]:.5f}", "lat": ll[0], "lon": ll[1], "kind": "coords"}], None
    cands = search_stops(stops, text)
    geo, err = geocode(text)
    cands += geo
    if not cands:
        return [], err or "Nothing found. Try a bus stop name, a landmark, or paste coordinates like 19.18, 72.84."
    return cands, err


def _metres(lat, lon, lats, lons):
    k = np.cos(np.radians(lat))
    return np.hypot((lats - lat) * 111_320.0, (lons - lon) * 111_320.0 * k)


def service_at(d: dict, lat: float, lon: float):
    """What bus service does this point get? Uses the nearest 100 m grid cell for trips per hour and the stop list for distance.
    Returns None if the point is outside the mapped Greater Mumbai area."""
    c = d["all_cells"]
    dist = _metres(lat, lon, c.lat.to_numpy(), c.lon.to_numpy())
    i = int(np.argmin(dist))
    if dist[i] > 150:
        return None
    cell = c.iloc[i]
    st = d["stops"]
    sd = _metres(lat, lon, st.stop_lat.to_numpy(), st.stop_lon.to_numpy()); j = int(np.argmin(sd))
    stop = st.iloc[j]
    nearest = float(sd[j]); trips = float(cell.trips_peak_h)
    status = "No bus stop within %d m" % NEAR_M if nearest > NEAR_M else \
             "Stop nearby, but low frequency" if trips < LOW_FREQ else "Well served"
    return {"prabhag": int(cell.prabhag), "admin_ward": cell.admin_ward, "nearest_stop": stop.stop_name, "nearest_stop_lat": float(stop.stop_lat),
            "nearest_stop_lon": float(stop.stop_lon), "nearest_stop_m": nearest, "trips_peak_h": trips, "status": status}
