# Power BI dashboard kit

Power BI Desktop is not available in the build environment, so **no .pbix file is shipped**; instead the tables below (`powerbi/data/*.csv`) are tidy and join-ready. A dashboard can be built in ~20 minutes.

| Table | Grain | Key | Use |
|---|---|---|---|
| `dim_prabhag.csv` | 227 prabhags | `prabhag` | Choropleth/bubble map (lat, lon), coverage, service, index, archetype, hotspot flag |
| `fact_ward_summary.csv` | 24 BMC wards | `admin_ward` | Ward bar charts |
| `dim_stop.csv` | 4,346 stops | `stop_id` | Stop map, typology, betweenness |
| `dim_route.csv` | 603 routes | `route_id` | Route typology scatter, headway |
| `fact_facility_access.csv` | usable facilities | `fid` | Certain/possible access tables |
| `fact_suggested_stop_catchments.csv` | 25 sites | `rank` | Prioritisation map/table |
| `fact_grid_300m.csv` | 300 m cells | - | Heat/density map (population, mean distance, service) |

**Relationships:** `dim_prabhag[admin_ward]` -> `fact_ward_summary[admin_ward]` (many-to-one); `fact_suggested_stop_catchments[prabhag]` -> `dim_prabhag[prabhag]`; `fact_grid_300m[prabhag]` -> `dim_prabhag[prabhag]`.

**Suggested pages:** (1) Overview KPIs + coverage by ward; (2) Prabhag map coloured by `connectivity_index`, slicers on `archetype`, `urban_density_flag`; (3) Equity (`cov_500` vs `sc_cov_500` vs `st_cov_500`); (4) Facilities (`certain_500` / `possible_500` by `category`); (5) Priorities (`pop_uncovered_500` top-N + catchment table).

**DAX starters**
```DAX
Residents = SUM(dim_prabhag[pop])
Coverage 500m = DIVIDE(SUMX(dim_prabhag, dim_prabhag[pop] * dim_prabhag[cov_500]), [Residents])
Unserved 500m = SUM(dim_prabhag[pop_uncovered_500])
SC Coverage 500m = DIVIDE(SUMX(dim_prabhag, dim_prabhag[sc_pop] * dim_prabhag[sc_cov_500]), SUM(dim_prabhag[sc_pop]))
Facilities Certainly 500m = CALCULATE(COUNTROWS(fact_facility_access), fact_facility_access[certain_500] = TRUE())
```
Use the Bubble/Filled map with `lat`/`lon`. For a shape map, convert `data/processed/prabhags.geojson` to TopoJSON (e.g. mapshaper.org) and load as a custom shape map keyed on `prabhag`.

Caveat for any dashboard: keep the data-quality notes visible - the facility layers are partial and times are scheduled, not live.
