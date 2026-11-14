# Limitations and responsible use

1. **Scheduled, not real-time.** Times are timetable values. Delays, breakdowns, crowding and actual headways are unknown.
2. **Bus only.** Suburban rail, Metro, monorail and ferries are not in the feed. Areas served mainly by rail look worse than they are for rail-based trips, and door-to-door times for rail-friendly journeys are overstated.
3. **Interpolated stop times.** Only 7.5% of stop times are official timepoints; 51% of consecutive stop pairs have identical times. Treat journey times as +/- 5 min. 78 of 603 routes show implausible scheduled speeds, so speed is reported with a warning and never used in modelling.
4. **Unofficial, single-pattern feed.** The GTFS is a community compilation; there is one service pattern for all 7 days, so weekday/weekend and holiday differences cannot be studied.
5. **Straight-line walking.** No road network, barriers (rail lines, creeks, highways), crossings or footpath quality. The detour factor 1.3 is a proxy. True accessibility for wheelchair users, older adults or children requires on-street data (kerbs, footpaths, crossings, stop furniture) that open data does not contain; this project measures *distance-based* access only.
6. **Uniform population inside a prabhag.** Parks, port, industrial and military land are not masked, so unserved population is **overstated** in low-density prabhags (flagged `urban_density_flag`) and some "hotspot" prabhags are largely non-residential. Census 2011 is the latest ward-level count; the city has grown since.
7. **Partial facility data.** OSM colleges are incomplete (44); MCGM data excludes private hospitals and uses rounded coordinates (handled with certain/possible bounds). Absence in the data is not absence on the ground. Schools, markets, workplaces and jobs are not analysed.
8. **Typologies are descriptive.** Silhouette scores of 0.29-0.36 mean groups sit on a continuum. k for prabhags was constrained to >= 4 (k = 3 only isolates 4 outliers).
9. **Suggested stop catchments are prompts**, not engineered locations; road access, land use and operator constraints must be checked on site.
10. **Greater Mumbai only** for population-based results. Journey planning covers the whole feed (incl. Thane, Kalyan-Dombivli, Vasai-Virar), but no population data are modelled there.
11. **Equity.** SC/ST figures are ward-level shares spread evenly; they say nothing about individual households. No significance does not mean no disadvantage - it means this data cannot detect a systematic gap at ward level.

12. **Fares are indicative, not official.** The feed has no fare data. The fare table was compiled from news reports of BEST's May 2025 revision, and later reports say a restructuring is under consideration. Real fares depend on route fare stages and AC/non-AC service; only BEST legs are priced, passes are ignored, and the high estimate uses an assumed 1.2 road-distance factor. Edit `data/reference/best_fares.json` when BEST publishes a new chart.
13. **Nearest-stop walking time** is straight-line x 1.3 - barriers (rail lines, creeks, highways) are not modelled.
