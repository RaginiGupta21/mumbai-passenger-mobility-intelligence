# Data sources and licences

| # | Dataset | Used for | Source | Licence | Verified |
|---|---|---|---|---|---|
| 1 | Mumbai bus GTFS (`gtfs_compat.zip`; `gtfs.zip` kept for reference) - BEST, TMT, KDMT, VVMT; publisher "BLRTransit" | Journey planning, routes, schedules, network analysis | https://github.com/croyla/mumbai-gtfs | MIT | Licence file read; feed audited (docs/DATA_QUALITY.md) |
| 2 | BMC electoral wards 2017 - 227 prabhags with population, SC & ST population | Population grid, equity | https://github.com/datameet/Municipal_Spatial_Data (`Mumbai/bmc_electoral_wards_2017`) | CC BY-SA 2.5 India (DataMeet) | Population sums to the Census 2011 total (12,442,373) |
| 3 | BMC administrative wards (24) | Stop-to-ward tagging, Greater Mumbai boundary | same repo (`Mumbai/BMC_Wards.geojson`) | CC BY-SA 2.5 India | - |
| 4 | SRA slum clusters (2,542 polygons) | Inclusive-mobility indicator (area-based) | same repo (`Mumbai/slumClusters.geojson`) | CC BY-SA 2.5 India | Polygons only, no population |
| 5 | Colleges & universities (OpenStreetMap, HOT export, filtered to MMR) | Facility access | https://github.com/yashveeeeeeer/india-geodata (`data/education/facilities`) | ODbL (OSM contributors); repackaging CC BY 4.0 | 44 in Greater Mumbai - incomplete |
| 6 | MCGM public health facilities - hospitals, maternity homes, UPHCs, dispensaries (KML) | Facility access | MCGM open data via https://data.opencity.in ; copy used: https://github.com/aryamanx5/Mumbai_health-map (`data/raw/*.kml`) | MCGM open data; **the GitHub copy has no licence file** - verify at the original portal for formal use | Coordinates mostly 2 decimals (~+/-0.5 km); original KML values, not rounded by this project |

| 7 | BEST fare slabs (reference table) | Indicative fare range | Press reports (Free Press Journal) of the May 2025 revision, saved with URLs in `data/reference/best_fares.json` | Facts compiled from news; **not an official BEST table** | Verify at bestundertaking.com |

## Evaluated and rejected
* **NIC HealthGIS national facility file** (via india-geodata release): 147,957 points, **zero in Greater Mumbai**.
* **Smart-student-commute / Move_IQ repositories**: derived datasets with no verifiable provenance for facilities.
* **Live OpenStreetMap (Overpass) queries**: unreachable from the build environment. Replacing dataset 5 with a full OSM extract is the most valuable data upgrade (see LIMITATIONS.md).

## Synthetic vs real
**No synthetic data is used.** Everything shown is either (a) a real input above, (b) a quantity derived from real inputs by code in this repository, or (c) a stated modelling assumption (walking speed 1.2 m/s, detour factor 1.3, uniform density within a prabhag, 2-minute transfer buffer, 500 m catchments). There are no live bus positions, actual arrival times or passenger counts anywhere.

Attribution: contains data (c) OpenStreetMap contributors (ODbL); DataMeet Trust (CC BY-SA 2.5 India); MCGM open data; croyla/mumbai-gtfs (MIT).
