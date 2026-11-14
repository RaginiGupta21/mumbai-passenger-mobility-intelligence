"""Indicative fare estimator for BEST legs. All numbers come from data/reference/best_fares.json (editable)."""
from __future__ import annotations
import json
from functools import lru_cache
from .config import ROOT

FARE_FILE = ROOT / "data" / "reference" / "best_fares.json"


@lru_cache(maxsize=1)
def table() -> dict:
    return json.loads(FARE_FILE.read_text())


def slab_fare(km: float, kind: str) -> int | None:
    """Fare for a ride of `km` kilometres; None if beyond the reported table."""
    t = table()
    for ub, f in zip(t["slabs_upper_km"], t[f"{kind}_inr"]):
        if km <= ub:
            return f
    return None


def leg_fare(dist_m: float) -> dict:
    """Low/high fare for one BEST leg: low uses the straight-line distance, high uses distance x road_factor_high."""
    t = table(); lo_km = dist_m / 1000; hi_km = lo_km * t["road_factor_high"]
    out = {"km_low": lo_km, "km_high": hi_km}
    for kind in ("non_ac", "ac"):
        lo, hi = slab_fare(lo_km, kind), slab_fare(hi_km, kind)
        out[kind] = (lo, hi if hi is not None else None) if lo is not None else None
    return out


def estimate(legs: list[dict]) -> dict:
    """Sum fares over BEST bus legs. Returns totals (or None if any BEST leg is above the table) and leg counts."""
    best = [l for l in legs if l["kind"] == "bus" and l["agency"] == "BEST"]
    other = [l for l in legs if l["kind"] == "bus" and l["agency"] != "BEST"]
    per = [leg_fare(l["dist_m"]) for l in best]
    res = {"best_legs": len(best), "other_legs": len(other), "per_leg": per, "other_operators": sorted({l["agency"] for l in other})}
    for kind in ("non_ac", "ac"):
        if any(p[kind] is None or p[kind][1] is None for p in per):
            res[kind] = None
        else:
            res[kind] = (sum(p[kind][0] for p in per), sum(p[kind][1] for p in per)) if per else (0, 0)
    return res


def fmt_range(r) -> str:
    if r is None: return "not priced (>25 km)"
    lo, hi = r
    return f"₹{lo}" if lo == hi else f"₹{lo}-{hi}"
