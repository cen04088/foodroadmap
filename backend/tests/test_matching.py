import pytest

from app.matching import match_restaurants_to_route
from app.models import Restaurant

ROUTE_POINTS = [
    {"lat": 37.50, "lng": 127.00, "cumulative_distance_m": 0.0, "cumulative_time_sec": 0.0},
    {"lat": 37.55, "lng": 127.05, "cumulative_distance_m": 7000.0, "cumulative_time_sec": 600.0},
    {"lat": 37.60, "lng": 127.10, "cumulative_distance_m": 14000.0, "cumulative_time_sec": 1200.0},
]


def make_restaurant(id_, lat, lng):
    return Restaurant(id=id_, name=f"restaurant-{id_}", latitude=lat, longitude=lng)


def test_match_restaurants_to_route_includes_nearby_and_excludes_far():
    near = make_restaurant("near", 37.55, 127.051)  # essentially on the second point
    far = make_restaurant("far", 38.5, 128.5)

    matches = match_restaurants_to_route(ROUTE_POINTS, [near, far], radius_km=2.0)

    matched_ids = {m.restaurant.id for m in matches}
    assert "near" in matched_ids
    assert "far" not in matched_ids


def test_match_restaurants_to_route_interpolates_cumulative_time_near_midpoint():
    # Sits almost exactly at the first route point, so its time should be ~0s, not ~600s or ~1200s.
    at_start = make_restaurant("start", 37.50, 127.001)

    matches = match_restaurants_to_route(ROUTE_POINTS, [at_start], radius_km=2.0)

    assert len(matches) == 1
    assert matches[0].cumulative_time_sec == pytest.approx(0.0, abs=60.0)


def test_match_restaurants_to_route_skips_restaurants_without_coordinates():
    no_coords = Restaurant(id="no-coords", name="no coords", latitude=None, longitude=None)

    matches = match_restaurants_to_route(ROUTE_POINTS, [no_coords], radius_km=2.0)

    assert matches == []


def test_match_restaurants_to_route_sorts_by_cumulative_time_ascending():
    late = make_restaurant("late", 37.60, 127.101)
    early = make_restaurant("early", 37.50, 127.001)

    matches = match_restaurants_to_route(ROUTE_POINTS, [late, early], radius_km=2.0)

    assert [m.restaurant.id for m in matches] == ["early", "late"]


def test_match_restaurants_to_route_returns_empty_for_degenerate_route():
    near = make_restaurant("near", 37.50, 127.001)

    matches = match_restaurants_to_route([ROUTE_POINTS[0]], [near], radius_km=2.0)

    assert matches == []
