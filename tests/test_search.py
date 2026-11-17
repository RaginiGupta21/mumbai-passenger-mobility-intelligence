"""Checks for the place search.   Run:  python -m pytest -q tests/test_search.py"""
import io
import json
import urllib.error
import numpy as np
import pytest
from src import gap, search
from src.config import *


@pytest.fixture(scope="module")
def d():
    return gap.load_data()


@pytest.fixture(autouse=True)
def no_sleep_no_cache(monkeypatch):
    monkeypatch.setattr(search.time, "sleep", lambda s: None)
    search._CACHE.clear()


def test_parse_latlon():
    assert search.parse_latlon("19.18, 72.84") == (19.18, 72.84)
    assert search.parse_latlon(" 19.18 72.84 ") == (19.18, 72.84)
    assert search.parse_latlon("72.84, 19.18") == (19.18, 72.84)           # longitude first is swapped
    assert search.parse_latlon("Malad station") is None and search.parse_latlon("") is None
    assert search.parse_latlon("200, 300") is None


def test_search_stops_is_case_insensitive_and_limited(d):
    r = search.search_stops(d["stops"], "malad")
    assert 1 <= len(r) <= 5 and all("malad" in x["label"].lower() for x in r)
    assert len({x["label"] for x in r}) == len(r)                          # no duplicate names
    assert search.search_stops(d["stops"], "") == [] and search.search_stops(d["stops"], "a") == []
    assert search.search_stops(d["stops"], "zzzzqqq") == []


def test_service_at_matches_a_brute_force_check(d):
    w = d["all_cells"]; w = w[w.admin_ward == STUDY_WARD]; row = w.iloc[len(w) // 2]
    info = search.service_at(d, float(row.lat), float(row.lon))
    assert info["admin_ward"] == STUDY_WARD and info["prabhag"] == int(row.prabhag)
    st = d["stops"]
    k = np.cos(np.radians(row.lat))
    brute = np.hypot((st.stop_lat - row.lat) * 111320, (st.stop_lon - row.lon) * 111320 * k).min()
    assert abs(info["nearest_stop_m"] - brute) < 1
    assert info["trips_peak_h"] == pytest.approx(float(row.trips_peak_h))


def test_status_follows_the_definitions(d):
    c = d["all_cells"]
    for _, row in c.sample(300, random_state=3).iterrows():
        info = search.service_at(d, float(row.lat), float(row.lon))
        if info["nearest_stop_m"] > NEAR_M:
            assert info["status"].startswith("No bus stop")
        elif info["trips_peak_h"] < LOW_FREQ:
            assert info["status"].startswith("Stop nearby")
        else:
            assert info["status"] == "Well served"


def test_a_point_in_the_sea_has_no_service_info(d):
    assert search.service_at(d, 18.80, 72.60) is None


class _Resp(io.BytesIO):
    def __enter__(self): return self
    def __exit__(self, *a): return False


def test_geocode_parses_results_and_sends_the_right_request(monkeypatch):
    seen = {}

    def fake_urlopen(req, timeout=0):
        seen["url"], seen["ua"] = req.full_url, req.get_header("User-agent")
        return _Resp(json.dumps([{"display_name": "Malad Railway Station, Mumbai, Maharashtra, India", "lat": "19.1864", "lon": "72.8484"}]).encode())
    monkeypatch.setattr(search.urllib.request, "urlopen", fake_urlopen)
    res, err = search.geocode("Malad station")
    assert err is None and res[0]["lat"] == pytest.approx(19.1864) and res[0]["label"].startswith("Address: Malad")
    assert "bounded=1" in seen["url"] and "viewbox=" in seen["url"] and "countrycodes=in" in seen["url"]
    assert "mumbai-service-gap-analysis" in seen["ua"]                      # identifies the app, as the usage policy requires


def test_geocode_caches_successes_only(monkeypatch):
    calls = []
    monkeypatch.setattr(search.urllib.request, "urlopen", lambda req, timeout=0: calls.append(1) or _Resp(b"[]"))
    search.geocode("somewhere"); search.geocode("Somewhere")
    assert len(calls) == 1                                                  # second call came from the cache

    def broken(req, timeout=0): raise urllib.error.URLError("offline")
    search._CACHE.clear(); monkeypatch.setattr(search.urllib.request, "urlopen", broken)
    res, err = search.geocode("another place"); assert res == [] and "could not be reached" in err
    assert "another place" not in search._CACHE                             # failures are not cached


def test_find_falls_back_to_stops_when_the_service_is_down(d, monkeypatch):
    def broken(req, timeout=0): raise urllib.error.URLError("offline")
    monkeypatch.setattr(search.urllib.request, "urlopen", broken)
    cands, msg = search.find("malad", d["stops"])
    assert len(cands) >= 1 and all(c["kind"] == "stop" for c in cands) and "could not be reached" in msg
    cands, msg = search.find("19.18, 72.84", d["stops"]); assert cands[0]["kind"] == "coords" and msg is None
    cands, msg = search.find("zzzzqqqq", d["stops"]); assert cands == [] and msg


def test_blank_search_makes_no_network_call(monkeypatch):
    monkeypatch.setattr(search.urllib.request, "urlopen", lambda *a, **k: pytest.fail("network used"))
    assert search.geocode("") == ([], None) and search.geocode("ab") == ([], None)
