"""Step 2 - Build RAPTOR pattern tables from the cleaned GTFS parquet files."""
import sys, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import pandas as pd
from src.config import PROC
from src.timetable import build_patterns, Timetable

t = time.time()
st = pd.read_parquet(PROC / "stop_times.parquet"); trips = pd.read_parquet(PROC / "trips.parquet")
P, codes = build_patterns(st, trips)
import pickle
pickle.dump(dict(P=P, svc_codes=codes), open(PROC / "timetable_patterns.pkl", "wb"), protocol=5)
print(f"patterns: {len(P['stops'])}, trips: {sum(len(x) for x in P['trip'])}, services: {codes}, {time.time()-t:.1f}s")
tt = Timetable.load()
print("footpath links:", len(tt.fp_to), " load ok")
