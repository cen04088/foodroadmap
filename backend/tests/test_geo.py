import math

import pytest

from app.geo import (
    bounding_box_with_margin,
    downsample_route_points,
    haversine_km,
    project_point_onto_segment,
)


def test_haversine_km_zero_for_same_point():
    assert haversine_km(37.5, 127.0, 37.5, 127.0) == pytest.approx(0.0, abs=1e-9)


def test_haversine_km_known_distance():
    # 서울시청(37.5665, 126.9780) ~ 강남역(37.4979, 127.0276) 대략 8.4km 안팎
    distance = haversine_km(37.5665, 126.9780, 37.4979, 127.0276)
    assert 8.0 < distance < 9.0


def test_project_point_onto_segment_on_the_line_midpoint():
    distance_km, t = project_point_onto_segment(
        point=(37.5, 127.005),
        seg_start=(37.5, 127.0),
        seg_end=(37.5, 127.01),
    )
    assert distance_km == pytest.approx(0.0, abs=1e-6)
    assert t == pytest.approx(0.5, abs=1e-3)


def test_project_point_onto_segment_beyond_segment_end_clamps_to_endpoint():
    distance_km, t = project_point_onto_segment(
        point=(37.5, 127.02),
        seg_start=(37.5, 127.0),
        seg_end=(37.5, 127.01),
    )
    assert t == pytest.approx(1.0, abs=1e-9)
    expected_distance = haversine_km(37.5, 127.02, 37.5, 127.01)
    assert distance_km == pytest.approx(expected_distance, rel=1e-3)


def test_project_point_onto_segment_perpendicular_offset():
    # seg_start->seg_end runs east along the same latitude; point is ~1km north of the midpoint
    distance_km, t = project_point_onto_segment(
        point=(37.509, 127.005),
        seg_start=(37.5, 127.0),
        seg_end=(37.5, 127.01),
    )
    assert 0.9 < distance_km < 1.1
    assert t == pytest.approx(0.5, abs=1e-2)


def test_project_point_onto_segment_degenerate_segment():
    # seg_start == seg_end: distance is just point-to-point, t is 0
    distance_km, t = project_point_onto_segment(
        point=(37.51, 127.0),
        seg_start=(37.5, 127.0),
        seg_end=(37.5, 127.0),
    )
    assert distance_km == pytest.approx(haversine_km(37.51, 127.0, 37.5, 127.0), rel=1e-6)
    assert t == 0.0


def test_downsample_route_points_returns_input_unchanged_when_within_limit():
    points = [{"lat": 37.5 + i * 0.001, "lng": 127.0} for i in range(10)]
    assert downsample_route_points(points, max_points=10) is points
    assert downsample_route_points(points, max_points=50) is points


def test_downsample_route_points_keeps_first_and_last_point():
    points = [{"lat": 37.5 + i * 0.0001, "lng": 127.0, "cumulative_time_sec": i} for i in range(1000)]
    result = downsample_route_points(points, max_points=100)

    assert len(result) <= 100
    assert result[0] == points[0]
    assert result[-1] == points[-1]


def test_downsample_route_points_preserves_order_with_no_duplicates():
    points = [{"lat": 37.5 + i * 0.0001, "lng": 127.0} for i in range(500)]
    result = downsample_route_points(points, max_points=50)

    lats = [p["lat"] for p in result]
    assert lats == sorted(lats)
    assert len(set(id(p) for p in result)) == len(result)


def test_bounding_box_with_margin_expands_by_margin():
    points = [
        {"lat": 37.50, "lng": 127.00},
        {"lat": 37.55, "lng": 127.05},
    ]
    min_lat, max_lat, min_lng, max_lng = bounding_box_with_margin(points, margin_km=2.0)

    assert min_lat < 37.50
    assert max_lat > 37.55
    assert min_lng < 127.00
    assert max_lng > 127.05
    # margin in degrees latitude should be roughly margin_km / 111
    assert (37.50 - min_lat) == pytest.approx(2.0 / 111.0, rel=0.05)
