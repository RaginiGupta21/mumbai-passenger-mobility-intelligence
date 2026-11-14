# Mumbai Passenger Mobility Intelligence System

A passenger-friendly, data-science-backed application that analyses Mumbai's **scheduled public bus connectivity**, journey options, accessibility and inclusive mobility, built entirely on open secondary data (no surveys, no fieldwork). **No synthetic data, live bus positions, actual arrival times or passenger counts are used or invented.**

```bash
pip install -r requirements.txt
streamlit run app.py          # processed data is included - the app starts immediately
# optional: rebuild everything from public sources (~2-3 min)
bash scripts/run_pipeline.sh
```

## What it does
| Module | Highlights |
|---|---|
| **Journey Explorer** | **Door-to-door time summary** (walk / wait / ride chart, leave-by time), an **indicative BEST fare range**, and a **Nearest bus stops** tool (click the map, type coordinates or pick a place → distance, walking time, routes, next departures). Origin/destination = any stop/area, college/university or public health facility; date + time; up to 6 Pareto/non-dominated scheduled options with transfers, walking, waiting, boarding/alighting stops and a route map. "Where can I reach in 15-90 min?" map. Engine: RAPTOR over 99,080 scheduled trips with real GTFS calendar logic (incl. after-midnight trips). |
| **Accessibility & Inclusion** | Population-weighted stop access at 300/500/800 m (100 m grid, 12.44 M residents), ward filters, peak service level (unique trips/hour), SC/ST and slum-cluster equity, colleges & health-facility access with explicit coordinate-uncertainty handling, 09:00 travel-time reach from every prabhag. |
| **Routes & Schedules** | 603 active routes: stops on a map, per-trip stop times, hourly timetable, peak headway; stop departure board; service availability by date; operator summary. |
| **Network Intelligence** | NetworkX components / cut vertices / betweenness; k-means typologies of stops, routes and prabhags (silhouette-selected); Connectivity Index with sensitivity analysis; Moran's I hotspots; greedy maximum-coverage **new-stop catchments**; auto-written, number-backed recommendations; CSV downloads. |
| **How to use** | In-app five-minute guide and glossary. |
| **Methods & Data** | Sources + licences, GTFS quality audit, methodology, limitations - inside the app. |

## Headline results (Greater Mumbai, bus network)
* **90.5 %** of residents are within 500 m of a bus stop (77.4 % within 300 m; 95.4 % within 800 m). **1.18 M** residents have none within 500 m.
* Gaps are spatially clustered (Moran's I 0.33, p = 0.001): M-East, T, P-North and R-Central wards are weakest (73-80 % coverage). Top dense prabhags by unserved residents: 118 (S), 143 and 145 (M-East), 111 (S), 57 (P-South).
* Where stops exist, peak service is mostly frequent (only 67 k residents are covered but get < 4 trips/hour).
* SC / ST coverage (88.5 % / 85.3 %) is a few points below the city (90.5 %), not statistically significant at prabhag level. 95.8 % of slum-cluster area is within 500 m of a stop.
* The VVMT (Vasai-Virar) network is a separate component - no scheduled transfer to BEST/TMT.
* 25 suggested catchments would reach ~381 k of the unserved residents (32 %).

Full list: [docs/FINDINGS.md](docs/FINDINGS.md). Figures: `docs/figures/`.

## Data (all real; see docs/DATA_SOURCES.md)
Mumbai bus GTFS (BEST/TMT/KDMT/VVMT, valid 19 Aug 2026 - 15 Feb 2027, MIT) · BMC 227 electoral wards with Census-2011-based population, SC/ST (DataMeet, CC BY-SA 2.5 IN) · SRA slum clusters (DataMeet) · OpenStreetMap colleges/universities (HOT export) · MCGM public health facilities (KML).

## Honest limitations (details: docs/LIMITATIONS.md)
Scheduled not live · bus only (no rail/Metro) · only 7.5 % of stop times are official timepoints (rest interpolated) · one timetable for all 7 days · unofficial community GTFS · straight-line walking x1.3 (no road network offline) · uniform density within a prabhag · OSM colleges incomplete (44) and MCGM health coordinates rounded (~±0.5 km, handled with certain/possible bounds) · typologies are descriptive (silhouette 0.29-0.36).

## Project structure
```
app.py                       Streamlit entry point
src/                         config, timetable, raptor, journey, facilities, maps, data, ui/ (one module per page)
scripts/00..08_*.py          reproducible pipeline (+ run_pipeline.sh)
data/raw/                    source files (provenance in docs/DATA_SOURCES.md)
data/reference/              best_fares.json - editable, sourced indicative fare table
data/processed/              parquet tables, geojson, model_diagnostics.json, data_quality_gtfs.json
powerbi/                     Power BI-ready CSV tables + build guide
docs/                        METHODOLOGY, DATA_SOURCES, DATA_QUALITY, FINDINGS, LIMITATIONS, figures/
tests/                       test_core.py (23 pytest checks), smoke_all_pages.py (30 headless UI checks incl. nearest-stops modes)
```

## Testing
```bash
python -m pytest -q tests/test_core.py   # data integrity, calendar, RAPTOR never slower than a scheduled trip, itinerary consistency, accessibility invariants
python tests/smoke_all_pages.py          # renders every page and clicks the real controls headlessly
```
Not covered by automated tests: visual rendering in a real browser (map tiles load from the keyless CARTO basemap, so internet access is needed for the base map).

## Credits and licence
Code: MIT. Data retains its original licences - attribution: © OpenStreetMap contributors (ODbL); DataMeet Trust (CC BY-SA 2.5 IN); MCGM; croyla/mumbai-gtfs.
