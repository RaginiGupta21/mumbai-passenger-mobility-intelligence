# Method

## Steps (all in `scripts/01_prepare_data.py`)

1. **Load and check the timetable.** Count stops, trips and stop times; look for stop times that point to missing stops or trips; measure the share of official timepoints. Results go to `data/processed/data_quality.json`.
2. **Load the prabhags.** 227 areas with Census 2011 population. The total is checked against the known Census figure (12,442,373).
3. **Place residents on a grid.** A point every 100 m is kept if it falls inside a prabhag. Each prabhag's residents are divided equally between its grid cells, so the total is unchanged.
4. **Measure supply for each cell.**
   - Distance to the nearest bus stop (map coordinates in metres, UTM zone 43N).
   - Scheduled trips per peak hour: the number of different trips leaving any stop within 500 m between 08:00 and 10:00, divided by two. A trip's last stop is ignored because nobody can board there.
5. **Flag the gap.** A cell is *no stop* if the nearest stop is over 500 m away. It is *low frequency* if a stop is near but trips per peak hour are under 10. Residents in either kind of cell are *underserved*. Nobody is counted twice.
6. **Add up.** Totals per prabhag and per BMC ward. Prabhags with fewer than 5,000 residents per km2 are labelled *low density* because they may include parks, port or industrial land.
7. **Suggest new stop areas** (study ward only). Take the cells with no stop nearby. Repeatedly pick the cell whose 500 m circle would cover the most not-yet-covered residents, remove those residents, and repeat ten times (a *greedy* search). The ranking shows the biggest gain first.

## Settings (`src/config.py`)

| Setting | Value | Meaning |
|---|---|---|
| `STUDY_WARD` | P - North | Ward studied in detail |
| `NEAR_M` | 500 | A stop this close counts as near (straight line) |
| `LOW_FREQ` | 10 | Fewer trips per peak hour than this is low frequency |
| `PEAK_START_H`, `PEAK_END_H` | 8, 10 | Morning peak |
| `GRID_M` | 100 | Grid cell size |
| `N_NEW_STOPS` | 10 | Suggested new stop areas |

The values 500 m and 10 trips per hour are planning judgements, not fixed rules. Changing them changes the numbers, so state them whenever you quote a result.

## What the results can and cannot say

- They show where residents have little bus service relative to the number who live there. They do not show how many people actually travel, because passenger counts are not available.
- The suggested stop areas depend on the even-spread assumption and ignore roads and land use. Treat them as places to investigate.
- Results for the large, low-density prabhags (32 and 49 in P-North) are the least certain.

## Checks (`tests/`)

- Residents add up to the Census total, and each ward's totals match its prabhags.
- Underserved residents equal no-stop plus low-frequency residents (nobody counted twice).
- Cell flags follow the definitions exactly.
- The suggested stop areas are in order of gain, cover no more people than lack a stop, and sit at least 500 m from existing stops.
- The app opens both pages and the main controls work.
