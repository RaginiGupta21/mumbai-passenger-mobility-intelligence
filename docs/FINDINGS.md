# Key findings

Auto-generated from the computed outputs. Scope: Greater Mumbai residents (12,442,372), scheduled bus network (BEST + TMT + KDMT + VVMT).

## 1. Stop access (straight-line distance)
| Radius | Residents covered |
|---|---|
| 300 m | 77.4% |
| 500 m | 90.5% |
| 800 m | 95.4% |

* **1,178,656** residents (9.5%) have no stop within 500 m; **566,930** (4.6%) none within 800 m.
* Weakest wards by 500 m coverage: M - East (73.1%), T (76.3%), P - North (77.3%), R - Central (80.3%). Best: D (99.5%), G - North (99.8%), C (100.0%).
* Dense prabhags with the most unserved residents: Prabhag 118 (S) - 41,649 of 55,966; Prabhag 143 (M - East) - 41,385 of 51,412; Prabhag 145 (M - East) - 40,709 of 53,213; Prabhag 111 (S) - 35,280 of 58,366; Prabhag 57 (P - South) - 34,661 of 57,477; Prabhag 12 (R - Central) - 34,460 of 47,352.
* Gaps are **spatially clustered**: Moran's I = 0.328 (p = 0.001); 40 prabhags are flagged as low-connectivity hotspots (some are low-density, park-adjacent prabhags - see the density flag).

## 2. Service quality
* Where a stop exists, service is mostly frequent: only 67,134 residents are covered yet receive < 4 scheduled trips/hour in the AM peak.
* 171 stops (3.9% of Greater Mumbai stops) are thin-service (one route, < 20 departures/day).
* The route typology (k-means) finds {'Regular routes': 238, 'High-frequency routes': 178, 'Low-frequency routes': 112, 'Sparse / limited-span routes': 58, 'Marginal routes': 26}. 26 routes are classed 'marginal' (median 2 trips/day).

## 3. Inclusion and equity
* Coverage within 500 m: all residents 90.5%, Scheduled Castes 88.5%, Scheduled Tribes 85.3%.
* A paired Wilcoxon test across 227 prabhags finds **no statistically significant** gap (SC p = 0.82, ST p = 0.40). City-wide SC/ST coverage is a few points below the all-resident figure, but the difference is small relative to prabhag-to-prabhag variation; it is a pattern to monitor, not evidence of systematic exclusion.
* 95.8% of mapped slum-cluster area lies within 500 m of a stop (area measure only; no slum population data exist).

## 4. Colleges and health facilities (usable-precision records)
| category                           |   Facilities |   Certainly <= 500 m |   Possibly <= 500 m |   Median distance to nearest stop (m) |
|:-----------------------------------|-------------:|---------------------:|--------------------:|--------------------------------------:|
| College                            |           37 |                   33 |                  33 |                                   160 |
| Dispensary                         |          172 |                  129 |                 167 |                                   138 |
| Maternity home                     |           26 |                   13 |                  26 |                                   112 |
| Public hospital                    |           29 |                   25 |                  29 |                                   136 |
| UPHC (urban primary health centre) |          197 |                  144 |                 195 |                                   136 |
| University                         |            7 |                    6 |                   6 |                                   195 |

* Median bus travel time (09:00, <= 3 transfers) from a prabhag's population centre to the nearest college: **16 min**; to the nearest public hospital: **15 min**. Coverage of facility data is partial - see limitations.

## 5. Network structure
* 7,506 stops, 24,335 links; 2 connected components once 200 m walk interchanges are allowed - the second is the VVMT network (55 stops).
* 97 cut-vertex stops (removal disconnects part of the network).
* Stop typology: {'Local stops': 2216, 'Trunk-corridor stops': 1967, 'Major hubs': 163}. Prabhag archetypes: {'Highly connected core': 147, 'Well connected': 59, 'Partially covered': 17, 'Underserved periphery': 4}.
* Connectivity Index is robust: median Spearman rho = 0.959 across 1,000 random weightings.

## 6. Prescriptive result
The 25 suggested new stop catchments would bring **380,510** residents (32.3% of those currently beyond 500 m) within reach. The first five cover 118,230. These are planning prompts, not engineered stop locations.
