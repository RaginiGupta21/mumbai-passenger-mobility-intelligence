# Methodology

Pipeline: `00_fetch_data → 01_build_gtfs → 02_build_timetable → 03_build_accessibility → 04_network_intelligence → 05_build_places → 06_export_powerbi → 07_generate_docs → 08_make_figures` (run with `scripts/run_pipeline.sh`).

## 1. GTFS handling (`scripts/01`, `src/timetable.py`)
* Load `stops, routes, trips, stop_times, calendar, agency, feed_info`; audit referential integrity, time logic, coordinates, implied speeds, calendar (docs/DATA_QUALITY.md). Problems are *flagged*, never silently "fixed".
* Times are converted to seconds since service-day start; values > 24:00:00 (overnight trips) are kept.
* Stops are tagged with the BMC administrative ward and an `in_greater_mumbai` flag (ward union + 250 m tolerance).

## 2. Journey planner (`src/raptor.py`, `src/journey.py`)
* **Patterns.** Trips with identical stop sequences form a pattern (1,112 patterns for 99,080 trips). Each pattern stores dense trips x stops arrival/departure matrices, sorted by first departure.
* **Calendar logic.** `Timetable.active_service_codes(date)` evaluates `calendar` start/end/weekday flags and `calendar_dates` exceptions. For a query on day D the engine uses trips of services active on D plus the after-midnight tail (times - 24 h) of services active on D-1. Dates outside the feed validity return an explicit message, not a guess.
* **Algorithm.** RAPTOR: round *k* relaxes every pattern from the earliest marked stop using at most *k* vehicle trips, then relaxes walking links (<= 400 m between stops). Multi-origin starts carry access-walk offsets; multi-destination ends add egress walks. Output is the Pareto set (arrival time vs trips). Minimum transfer buffer 2 min; non-FIFO patterns (overtaking) are handled by a masked minimum instead of binary search.
* **Origins/destinations.** A *place* groups stops that share a name and lie within 600 m (single-linkage), plus stops within 250 m on foot. Facilities and arbitrary points use stops within 700 m (<= 10 nearest, always at least the nearest stop).
* **Options.** After the best journeys for the chosen time, the search restarts ~8 min after the first bus of the previous best; duplicates and dominated journeys are dropped; "Fastest"/"Fewest transfers" tags are shown only when they discriminate.
* **Reachability.** One-to-all RAPTOR with a time cap (15-90 min, <= 4 trips).
* **Validation (tests/test_core.py).** (i) for 120 random scheduled trips the planner never arrives later than riding that trip; (ii) itineraries respect the transfer buffer and have positive in-vehicle times; (iii) a later departure never arrives earlier; (iv) out-of-feed dates are rejected; (v) the Pareto set is monotone.

### 2b. Passenger features
* **Time summary.** A journey's door-to-door time is split into walk to first stop, riding, waiting between buses, walking between stops and walk to destination; components sum exactly to the total (unit-tested). "Leave by" is the first bus departure minus the access walk.
* **Indicative fare.** Per BEST leg, ride distance = sum of straight lines between consecutive stops (a lower bound). Fare = slab lookup in `data/reference/best_fares.json` (slabs reported in the press for the May 2025 revision), computed at the straight-line distance (low) and at distance x 1.2 (high, an assumption) for non-AC and AC separately because the feed does not say which buses are AC. Legs by TMT/KDMT/VVMT and rides above 25 km are not priced. **This is not an official fare.**
* **Nearest bus stops.** The point is projected to UTM 43N; the k nearest stops come from a KD-tree. Walking time = distance x 1.3 / 1.2 m/s. Routes serving a stop are collected from its route patterns; the next departures use the same calendar-aware timetable views as the planner.

## 3. Population grid and stop access (`scripts/03`)
* 100 m grid in EPSG:32643; keep cell centres inside the 227 prabhag polygons (45,653 cells). Prabhag population, SC and ST counts are divided equally among its cells (the grid total reproduces 12,442,373).
* Distance to the nearest stop uses a KD-tree (straight line). Coverage at 300/500/800 m is population-weighted; the optional "street-detour adjusted" view divides the distance by 1.3.
* **Service level.** Number of *unique* scheduled trips with a departure from any stop within 500 m, daily and per hour in 08:00-10:00 (a bus passing five nearby stops counts once). Bands: none / < 4 / 4-10 / 10+ trips per hour. Distinct routes within 500 m are counted likewise. (A first version summed stop departures and over-counted; it was replaced.)
* **Slum clusters.** Grid cells whose centre lies in an SRA slum polygon; coverage is an *area* share.
* **Equity.** Population-weighted SC and ST coverage versus the prabhag average; paired Wilcoxon signed-rank test across 227 prabhags.

## 4. Facilities
* Colleges/universities: OSM points, precise. MCGM health facilities: coordinates rounded to *d* decimals imply a box of +/- 0.5·10^-d degrees. The box centre, corners and edge midpoints (9 samples) give a minimum and maximum distance to the nearest stop: **certainly within r** if the maximum <= r, **possibly within r** if the minimum <= r. Records with 1 decimal (~+/-5 km) are excluded.
* Catchment strength: unique routes and trips within 500 m.

## 5. Transit-time accessibility
From each prabhag's population-weighted centre (walk <= 800 m to <= 10 stops), one-to-all RAPTOR for a 09:00 weekday departure (<= 4 trips, <= 75 min). Facility time = arrival at a stop within 800 m + walk (x1.3 detour at 1.2 m/s). Outputs: minutes to nearest facility, counts reachable within 30/45/60 min, and share of area reachable within 30/45/60 min.

## 6. Network analysis (`scripts/04`, NetworkX)
Graph: stops as nodes; edges between consecutive stops on any trip (weight = median scheduled run time, floor 30 s); extra edges between stops <= 200 m apart (walk time + 2 min). Metrics: connected components (with and without walk interchange), articulation points, degree, approximate betweenness centrality (600 sampled sources, travel-time weights), stops within 500 m.

## 7. Clustering (scikit-learn) - where justified
| Unit | Features | Method | k selection | Result |
|---|---|---|---|---|
| Stops in Greater Mumbai (4,346) | routes, departures/day, peak departures/h, degree, betweenness, nearby stops (log1p, z-score) | k-means | silhouette k = 3-7 | k = 3 (sil. 0.31): hubs / trunk / local |
| Routes (612) | trips/day, length, span, peak trips/h | k-means | silhouette k = 3-6 | k = 5 (sil. 0.36) |
| Prabhags (227) | coverage, walk distance, peak service, routes, 45-min reach, facility reach, density, SC+ST share | k-means | silhouette k = 4-6 (k = 3 rejected: isolates 4 outliers) | k = 4 (sil. 0.29, run-to-run ARI 0.97) |

Clustering is used because each case is a *typology of many units described by several correlated measures*; it is **not** used for the journey planner or the coverage statistics. Scheduled speed was excluded from route clustering after the audit showed it to be unreliable. Because silhouettes are < 0.5 the groups are tiers on a continuum; cluster names are assigned by rank on mean departures (stops, routes) or mean Connectivity Index (prabhags) and described by their actual profiles in the app.

## 8. Connectivity Index
Equal-weight mean of six percentile-ranked components: 500 m coverage, mean walk distance (inverted), AM-peak trips/h, route choice, 45-min network reach, essential-facility reach (mean percentile of colleges <= 60 min, public hospitals <= 60 min, primary health <= 45 min). Robustness: 1,000 Dirichlet-random weightings; median Spearman rho 0.96 (5th percentile 0.86). **Hotspots**: prabhag in the bottom quartile whose 6 nearest neighbours' mean index is also low. **Spatial autocorrelation**: Moran's I (6-NN weights, 999 permutations) = 0.33, p = 0.001.

## 9. Suggested stop catchments
Greedy maximum-coverage: candidates are populated grid cells > 500 m from any stop; each iteration picks the cell whose 500 m disc covers the most not-yet-covered population (uniform within prabhag), up to 25 sites. Greedy is within (1-1/e) of the optimum for this submodular objective. Output is a ranked list of catchment centres for planners.
