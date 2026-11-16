"""Checks that the numbers behind the app are consistent.   Run:  python -m pytest -q tests"""
import json
import numpy as np
import pandas as pd
import pytest
from src.config import *
from src import gap


@pytest.fixture(scope="module")
def d():
    return gap.load_data()


def test_population_matches_census_total(d):
    assert abs(d["pr"]["pop"].sum() - 12_442_373) < 10          # prabhag populations add up to the Census 2011 total
    assert len(d["pr"]) == 227


def test_underserved_is_the_sum_of_its_two_parts(d):
    pr = d["pr"]
    assert np.allclose(pr.underserved_pop, pr.no_stop_pop + pr.low_freq_pop, atol=1e-3)     # nobody counted twice
    assert (pr.underserved_pop <= pr["pop"] + 1e-3).all() and (pr[["no_stop_pop", "low_freq_pop"]] >= 0).all().all()


def test_ward_totals_agree_with_prabhag_totals(d):
    pr, w = d["pr"], d["wards"]
    assert np.isclose(w.underserved_pop.sum(), pr.underserved_pop.sum())
    assert np.isclose(w["pop"].sum(), pr["pop"].sum())
    assert (w.underserved_share.between(0, 1)).all()


def test_study_ward_exists_and_is_flagged(d):
    w = d["wards"]
    assert w.is_study_ward.sum() == 1 and w[w.is_study_ward].admin_ward.iloc[0] == STUDY_WARD


def test_cell_flags_follow_the_definitions(d):
    c = d["cells"]
    assert (c[c.no_stop].dist_nearest_m > NEAR_M).all()
    assert (c[~c.no_stop].dist_nearest_m <= NEAR_M).all()
    assert (c[c.low_freq].trips_peak_h < LOW_FREQ).all() and not (c.no_stop & c.low_freq).any()


def test_study_cells_add_up_to_the_ward(d):
    ward_pop = d["wards"].query("is_study_ward")["pop"].iloc[0]
    assert abs(d["cells"]["pop"].sum() - ward_pop) < 5


def test_new_stop_areas_are_sensible(d):
    s, w = d["sites"], d["wards"].query("is_study_ward").iloc[0]
    if s.empty:                                                                     # nobody lacks a stop: nothing to suggest
        assert w.no_stop_pop < 1
        return
    assert len(s) <= N_NEW_STOPS and s.newly_covered.is_monotonic_decreasing       # greedy: biggest gain first
    assert (s.newly_covered > 0).all() and np.isclose(s.cumulative_covered.iloc[-1], s.newly_covered.sum())
    assert s.cumulative_covered.iloc[-1] <= w.no_stop_pop + 1                      # cannot cover more people than lack a stop
    assert s.lat.between(18.8, 19.4).all() and s.lon.between(72.7, 73.1).all()


def test_sites_fall_inside_cells_with_no_stop(d):
    """Each suggested site should be at least NEAR_M from existing stops (otherwise it is not filling a gap)."""
    from scipy.spatial import cKDTree
    if d["sites"].empty:
        return
    st = d["stops"]; k = np.cos(np.radians(19.1))
    tree = cKDTree(np.c_[st.stop_lat * 111320, st.stop_lon * 111320 * k])
    dist, _ = tree.query(np.c_[d["sites"].lat * 111320, d["sites"].lon * 111320 * k])
    assert (dist > NEAR_M * 0.9).all()


def test_data_quality_file_documents_the_main_issue(d):
    q = d["meta"]["quality"]
    assert q["stop_times_with_unknown_stop"] == 0 and q["residents_matches_census_2011_total"] is True
    assert q["share_official_timepoints"] < 0.2                                    # most stop times are interpolated


def test_colour_ramp_is_valid():
    assert gap.ramp(0, 0, 1).startswith("#") and len(gap.ramp(0.5, 0, 1)) == 7 and gap.ramp(5, 5, 5).lower() == gap.COLORS[0].lower()


def test_recommendations_are_generated_from_data(d):
    r = gap.recommendations(d)
    assert len(r) in (2, 4) and all(isinstance(x, str) and len(x) > 40 for x in r)   # 2 when the ward needs no new stops


def test_sites_in_low_density_prabhags_are_flagged(d):
    s = d["sites"]
    assert "area_type" in s.columns and s.area_type.notna().all()
    low = s.area_type != "dense residential"
    pr = d["pr"].set_index("prabhag")
    assert (pr.loc[s[low].prabhag, "density_km2"] < 5000).all() and (pr.loc[s[~low].prabhag, "density_km2"] >= 5000).all()


def test_map_uses_a_basemap_that_needs_no_api_key_and_views_the_ward(d):
    assert "cartocdn" not in gap.TILES and "openstreetmap" in gap.TILES
    centre, zoom = gap.ward_view(d)
    assert 18.8 < centre[0] < 19.4 and 72.7 < centre[1] < 73.1 and zoom in (11, 12, 13)


def test_darker_always_means_a_bigger_gap():
    dark, light = gap.COLORS[-1].lower(), gap.COLORS[0].lower()
    # more underserved residents -> darker
    assert gap.colour_for("Underserved share of residents", 1.0, 0.0, 1.0).lower() == dark
    assert gap.colour_for("Underserved share of residents", 0.0, 0.0, 1.0).lower() == light
    # FEWER peak trips (worse supply) -> darker (the scale is flipped for supply)
    assert gap.colour_for("Peak-hour bus trips (supply)", 10, 10, 230).lower() == dark
    assert gap.colour_for("Peak-hour bus trips (supply)", 230, 10, 230).lower() == light


def test_every_measure_has_an_explanation(d):
    for label, (col, fmt, worse, note) in gap.MEASURES.items():
        assert col in d["pr"].columns and note.startswith("Darker")
