"""Shared helpers: geometry, time formatting, loading of processed data."""
from __future__ import annotations
import numpy as np
import pandas as pd
from .config import PROC

EARTH_R = 6371008.8


def haversine_m(lat1, lon1, lat2, lon2):
    lat1, lon1, lat2, lon2 = map(np.radians, (lat1, lon1, lat2, lon2))
    a = np.sin((lat2 - lat1) / 2) ** 2 + np.cos(lat1) * np.cos(lat2) * np.sin((lon2 - lon1) / 2) ** 2
    return 2 * EARTH_R * np.arcsin(np.sqrt(a))


def hms_to_s(series: pd.Series) -> np.ndarray:
    """GTFS 'HH:MM:SS' (HH may exceed 24) -> seconds since service-day start."""
    p = series.str.split(":", expand=True).astype(np.int64)
    return (p[0] * 3600 + p[1] * 60 + p[2]).to_numpy()


def s_to_hm(sec: float | int) -> str:
    """Seconds -> 'HH:MM' with +1d marker for service times after midnight."""
    sec = int(round(sec))
    d, r = divmod(sec, 86400)
    h, m = divmod(r // 60, 60)
    return f"{h:02d}:{m:02d}" + (f" (+{d}d)" if d > 0 else "")


def fmt_dur(sec: float) -> str:
    m = int(round(sec / 60))
    return f"{m // 60} h {m % 60:02d} min" if m >= 60 else f"{m} min"


def load(name: str) -> pd.DataFrame:
    return pd.read_parquet(PROC / f"{name}.parquet")
