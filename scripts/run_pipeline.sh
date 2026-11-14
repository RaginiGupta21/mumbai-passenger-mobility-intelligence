#!/usr/bin/env bash
# Rebuild everything from raw data. Runtime ~2-3 minutes on a laptop.
set -euo pipefail
cd "$(dirname "$0")/.."
python scripts/00_fetch_data.py   # skips files that already exist
python scripts/01_build_gtfs.py   # load + audit + clean GTFS
python scripts/02_build_timetable.py   # RAPTOR route patterns
python scripts/03_build_accessibility.py   # 100 m population grid, facility access, transit-time reach
python scripts/04_network_intelligence.py   # NetworkX, clustering, equity, gaps, siting
python scripts/05_build_places.py   # searchable place index
python scripts/06_export_powerbi.py   # Power BI tables
python scripts/07_generate_docs.py   # data-quality report + findings
python scripts/08_make_figures.py   # documentation figures
python -m pytest -q tests/test_core.py
echo "Done. Launch the app with:  streamlit run app.py"
