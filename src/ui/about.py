import pandas as pd, streamlit as st
from .style import hero, note
from ..config import *


def render(d, tt):
    hero("Methods, Data Quality & Limitations", "How every number in this application was produced, and what it can and cannot tell you.")
    dq = d["dq"]; t1, t2, t3, t4 = st.tabs(["Data sources", "GTFS quality audit", "Methodology", "Limitations"])
    with t1:
        src = pd.DataFrame([
            ["Bus timetable (GTFS)", "croyla/mumbai-gtfs (gtfs_compat.zip) - BEST, TMT, KDMT, VVMT; compiled by BLRTransit from public operator data", "github.com/croyla/mumbai-gtfs", "MIT", "Feed valid 19 Aug 2026 - 15 Feb 2027; unofficial community feed"],
            ["BMC electoral wards 2017 (227 prabhags)", "DataMeet Municipal_Spatial_Data - polygons with 2011-Census-based population, SC & ST population", "github.com/datameet/Municipal_Spatial_Data", "CC BY-SA 2.5 India", "Population 12,442,373 = Census 2011 total"],
            ["BMC administrative wards (24)", "DataMeet", "same", "CC BY-SA 2.5 India", "Used for stop-to-ward tagging"],
            ["Slum clusters", "DataMeet, digitised from SRA slum-cluster map", "same", "CC BY-SA 2.5 India", "Polygons only - no population"],
            ["Colleges & universities", "OpenStreetMap via HOT export (as repackaged in india-geodata)", "github.com/yashveeeeeeer/india-geodata", "ODbL © OSM contributors (repackaging: CC BY 4.0)", "44 in Greater Mumbai - incomplete"],
            ["Public health facilities", "MCGM open data KMLs (hospitals, maternity homes, UPHCs, dispensaries)", "data.opencity.in (MCGM); copy via github.com/aryamanx5/Mumbai_health-map", "MCGM open data - the GitHub copy has no licence file: verify at source", "Coordinates rounded; no private facilities"],
        ], columns=["Dataset", "Description", "Location", "Licence", "Notes"])
        st.dataframe(src, hide_index=True, width="stretch")
        note("Data tried and rejected: NIC HealthGIS facilities (contain no Greater Mumbai records); live OSM/Overpass (not reachable from the build environment).")
    with t2:
        c = dq["counts"]; ig = dq["integrity"]; tl = dq["time_logic"]; sp = dq["spatial"]
        a = pd.DataFrame([
            ["Agencies / routes / stops / trips / stop-times", f"{c['agencies']} / {c['routes']:,} / {c['stops']:,} / {c['trips']:,} / {c['stop_times']:,}", "ok"],
            ["Duplicate stop IDs, missing coordinates, orphan references", "0 / 0 / 0", "ok"],
            ["Routes with no trips", f"{ig['routes_without_trips']} of {c['routes']}", "flag - excluded from route analysis"],
            ["Negative time steps / departure before arrival", f"{tl['negative_time_steps']} / {tl['dep_before_arr']}", "ok"],
            ["Zero-minute steps between consecutive stops", f"{tl['zero_time_steps_share']:.1%}", "flag - interpolated times"],
            ["Official timepoints", f"{tl['timepoint_share']:.1%} of stop times", "flag - intermediate times approximate"],
            ["Times after 24:00 (overnight trips)", f"{tl['times_after_24h']:,} stop times, max {tl['max_time_h']} h", "handled (prior-day tail logic)"],
            ["Calendar", f"{dq['calendar']['start']} - {dq['calendar']['end']}; one service ID, 7 days/week", "flag - no weekday/weekend difference"],
            ["shapes.txt / frequencies.txt / calendar_dates.txt", "absent", "flag - straight lines between stops"],
            ["Stops inside Greater Mumbai", f"{sp['stops_in_greater_mumbai']:,} of {c['stops']:,}", "analysis scope"],
            ["Segments faster than 80 km/h", f"{sp['segments_speed_gt_80kmh']} (median {sp['median_segment_speed_kmh']} km/h)", "flag - kept, not used for speed analysis"],
            ["Feed publisher", dq["feed_info"]["feed_publisher_name"], "unofficial compilation"],
        ], columns=["Check", "Result", "Status"])
        st.dataframe(a, hide_index=True, width="stretch")
    with t3:
        st.markdown(f"""
**Journey planning (RAPTOR).** Scheduled trips are grouped into {tt.n_patterns:,} stop-sequence patterns. For a chosen origin, destination, date and time the engine runs *RAPTOR*
(Round-bAsed Public Transit Optimized Router): round *k* finds the earliest arrival using at most *k* bus trips. It returns Pareto-optimal options (arrival time vs number of transfers),
considers walking links of up to {MAX_TRANSFER_WALK_M} m between stops, enforces a {MIN_TRANSFER_S // 60}-minute minimum transfer buffer, and respects the GTFS calendar including after-midnight trips.
Later options are found by re-searching ~8 minutes after the previous first bus; dominated options are dropped. Correctness was validated by checking that the planner never arrives later than simply riding a known scheduled trip (150 random trips).

**Walking.** {WALK_SPEED_MS} m/s (≈{WALK_SPEED_MS * 3.6:.1f} km/h) on straight-line distance × {DETOUR_FACTOR} street-detour factor. An offline road network was unavailable, so this proxy is used; the "street-detour adjusted" toggle shows the effect.

**Population & accessibility.** Greater Mumbai is covered by a {GRID_M} m grid (45,653 cells). Each prabhag's population (and its SC and ST counts) is spread uniformly over its cells; the grid total reproduces the Census figure exactly.
For each cell: distance to the nearest stop, stops/routes within 500 m, and the number of **unique** scheduled trips serving the 500 m catchment (daily, and per hour in the {PEAK_START_H:02d}-{PEAK_END_H:02d}h peak).

**Facilities.** College points are precise (OSM). MCGM health points are mostly rounded to 2 decimals, so each is evaluated over its rounding box (centre, corners, edge-midpoints): *certainly within r* when the farthest sample is within r, *possibly within r* when the nearest sample is. Records at 1 decimal (~±5 km) are excluded.

**Transit-time accessibility.** From each prabhag's population-weighted centre, a one-to-all RAPTOR run (weekday 09:00, ≤4 trips, ≤75 min) gives arrival times at all stops; facility travel time adds the walk from the stops within 800 m.

**Network analysis (NetworkX).** Stops are nodes; consecutive stops on any trip are edges weighted by median scheduled run time; stops within 200 m are joined by walk-time edges. We compute components, articulation (cut) vertices, degree and approximate betweenness (600 sampled sources).

**Clustering (scikit-learn).** *Where justified*: stop tiers, route types and prabhag archetypes are all typologies of many units described by several correlated features, so k-means on log-scaled, standardised features is appropriate. k is chosen by silhouette (prabhags: k ≥ 4, because k = 3 only isolates 4 outliers). Silhouettes are modest (0.29-0.36), so results are *descriptive tiers along a continuum*. Prabhag clusters are stable across seeds (ARI ≈ 0.97). Speed was removed from route clustering after the audit showed unreliable interpolated speeds.

**Connectivity Index.** Equal-weight mean of six percentile-ranked components (coverage, walk distance, peak service, route choice, 45-min network reach, essential-facility reach). Robustness: 1,000 random Dirichlet weightings, median Spearman ρ = {d['diag']['index_sensitivity']['spearman_median']}.
Hotspots: bottom-quartile prabhags whose 6 nearest neighbours are also low; spatial dependence tested with Moran's I (999 permutations).

**Equity.** SC/ST coverage compared with the prabhag average by Wilcoxon signed-rank test; slum clusters assessed by area share (no slum population is available).

**Suggested stop catchments.** Greedy maximum-coverage selection of 25 sites on the 100 m grid (candidate = uncovered cells), each covering residents within 500 m not already covered.
        """)
    with t4:
        st.markdown("""
- **Scheduled supply only.** No live positions, delays, crowding or passenger counts - none exist in the open data used, and none were invented.
- **Bus only.** Suburban rail, Metro, monorail and ferries are not in the feed; areas near stations may be better connected than shown. Journey times therefore overstate door-to-door times for rail-friendly trips.
- **Interpolated times.** Only ~7% of stop times are official timepoints; intermediate times and run times are approximate.
- **Unofficial feed.** The GTFS is a community compilation (BLRTransit); operator changes after the feed date are not captured. One timetable applies on all 7 days.
- **Uniform density within a prabhag.** Parks, port land and industry are not excluded, so unserved population is overstated in low-density prabhags (flagged in tables). Real population is also not static - Census 2011 is the latest ward-level count available.
- **Straight-line / proxy walking.** No road network, barriers (rail lines, creeks) or footpath quality are modelled. Accessibility for wheelchair users, children or older adults needs on-street data (kerbs, footpaths) that open data does not provide.
- **Facilities are partial.** OSM colleges are incomplete; MCGM data excludes private providers and has rounded coordinates. Absence of a facility in the data is not absence on the ground.
- **Suggested catchments are prompts** for planners, not engineered stop locations.
- **Greater Mumbai only** for population-based analysis (population layers cover the BMC area); journey planning covers the entire feed (BEST + TMT + KDMT + VVMT).
        """)
