from unittest.mock import Mock, patch

import pytest
import requests

from app.geo import haversine_km
from app.kakao.directions import (
    KakaoDirectionsError,
    fetch_route,
    parse_route_points,
    parse_route_summary,
)

# 실제 카카오모빌리티 REST API 키로 라이브 호출해(서울시청→강남역, 2026-09-01) 응답
# 구조를 검증한 뒤, 그 구조를 그대로 반영해 만든 합성 응답 (좌표/거리값은 테스트용으로 단순화).
FAKE_RESPONSE = {
    "trans_id": "fake-trans-id",
    "routes": [
        {
            "result_code": 0,
            "result_msg": "",
            "summary": {
                "origin": {"name": "", "x": 127.0, "y": 37.5},
                "destination": {"name": "", "x": 127.1, "y": 37.6},
                "distance": 15000,
                "duration": 1200,
            },
            "sections": [
                {
                    "distance": 15000,
                    "duration": 1200,
                    "roads": [
                        {
                            "name": "Road A",
                            "distance": 10000,
                            "duration": 800,
                            "traffic_speed": 40.0,
                            "traffic_state": 1,
                            "vertexes": [127.0, 37.5, 127.05, 37.55],
                        },
                        {
                            "name": "Road B",
                            "distance": 5000,
                            "duration": 400,
                            "traffic_speed": 40.0,
                            "traffic_state": 1,
                            "vertexes": [127.05, 37.55, 127.1, 37.6],
                        },
                    ],
                }
            ],
        }
    ],
}


def test_fetch_route_returns_json_and_passes_correct_params():
    fake_response = Mock()
    fake_response.raise_for_status = Mock()
    fake_response.json = Mock(return_value=FAKE_RESPONSE)

    with patch("app.kakao.directions.requests.get", return_value=fake_response) as mock_get:
        result = fetch_route(37.5, 127.0, 37.6, 127.1, api_key="test-key")

    assert result == FAKE_RESPONSE
    mock_get.assert_called_once()
    _, kwargs = mock_get.call_args
    assert kwargs["params"]["origin"] == "127.0,37.5"
    assert kwargs["params"]["destination"] == "127.1,37.6"
    assert kwargs["headers"]["Authorization"] == "KakaoAK test-key"


def test_fetch_route_raises_kakao_directions_error_on_request_failure():
    with patch("app.kakao.directions.requests.get", side_effect=requests.ConnectionError("boom")):
        with pytest.raises(KakaoDirectionsError):
            fetch_route(37.5, 127.0, 37.6, 127.1, api_key="test-key")


def test_fetch_route_raises_kakao_directions_error_on_json_decode_failure():
    fake_response = Mock()
    fake_response.raise_for_status = Mock()
    fake_response.json = Mock(side_effect=requests.exceptions.JSONDecodeError("msg", "doc", 0))

    with patch("app.kakao.directions.requests.get", return_value=fake_response):
        with pytest.raises(KakaoDirectionsError):
            fetch_route(37.5, 127.0, 37.6, 127.1, api_key="test-key")


def test_parse_route_summary_extracts_totals():
    summary = parse_route_summary(FAKE_RESPONSE)
    assert summary == {"total_distance_m": 15000, "total_duration_sec": 1200}


def test_parse_route_points_accumulates_distance_and_time_across_roads():
    points = parse_route_points(FAKE_RESPONSE)

    assert len(points) == 3
    assert points[0] == {"lat": 37.5, "lng": 127.0, "cumulative_distance_m": 0.0, "cumulative_time_sec": 0.0}

    # Road A has a single segment, so it gets 100% of Road A's duration (800s).
    assert points[1]["lat"] == pytest.approx(37.55)
    assert points[1]["lng"] == pytest.approx(127.05)
    assert points[1]["cumulative_time_sec"] == pytest.approx(800.0)
    expected_seg1_m = haversine_km(37.5, 127.0, 37.55, 127.05) * 1000
    assert points[1]["cumulative_distance_m"] == pytest.approx(expected_seg1_m)

    # Road B has a single segment too, gets 100% of Road B's duration (400s) on top.
    assert points[2]["lat"] == pytest.approx(37.6)
    assert points[2]["lng"] == pytest.approx(127.1)
    assert points[2]["cumulative_time_sec"] == pytest.approx(1200.0)
    expected_seg2_m = haversine_km(37.55, 127.05, 37.6, 127.1) * 1000
    assert points[2]["cumulative_distance_m"] == pytest.approx(expected_seg1_m + expected_seg2_m)


def test_parse_route_points_raises_when_no_routes():
    with pytest.raises(KakaoDirectionsError):
        parse_route_points({"routes": []})


def test_parse_route_points_raises_when_result_code_nonzero():
    bad_response = {
        "routes": [{"result_code": 1, "result_msg": "경로를 찾을 수 없습니다", "sections": []}]
    }
    with pytest.raises(KakaoDirectionsError):
        parse_route_points(bad_response)


def test_parse_route_points_proportional_time_split_across_unequal_segments():
    """Test that a road with 3+ vertexes (2+ segments) splits duration proportionally by haversine distance."""
    response = {
        "trans_id": "fake-trans-id",
        "routes": [
            {
                "result_code": 0,
                "result_msg": "",
                "summary": {
                    "origin": {"name": "", "x": 127.0, "y": 37.5},
                    "destination": {"name": "", "x": 127.2, "y": 37.7},
                    "distance": 20000,
                    "duration": 1200,
                },
                "sections": [
                    {
                        "distance": 20000,
                        "duration": 1200,
                        "roads": [
                            {
                                "name": "Multi-segment Road",
                                "distance": 20000,
                                "duration": 600,  # 600 seconds to split across 3 segments
                                "traffic_speed": 40.0,
                                "traffic_state": 1,
                                # 4 vertexes = 3 segments
                                "vertexes": [127.0, 37.5, 127.05, 37.6, 127.15, 37.65, 127.2, 37.7],
                            },
                        ],
                    }
                ],
            }
        ],
    }

    points = parse_route_points(response)

    # Should have 4 points: start + 3 intermediate/end
    assert len(points) == 4

    # First point: origin at cumulative 0
    assert points[0] == {"lat": 37.5, "lng": 127.0, "cumulative_distance_m": 0.0, "cumulative_time_sec": 0.0}

    # Intermediate points should have non-equal time splits based on segment distances
    # seg1: (127.0,37.5) -> (127.05,37.6)
    seg1_m = haversine_km(37.5, 127.0, 37.6, 127.05) * 1000
    # seg2: (127.05,37.6) -> (127.15,37.65)
    seg2_m = haversine_km(37.6, 127.05, 37.65, 127.15) * 1000
    # seg3: (127.15,37.65) -> (127.2,37.7)
    seg3_m = haversine_km(37.65, 127.15, 37.7, 127.2) * 1000
    total_m = seg1_m + seg2_m + seg3_m

    # Point 1 (after segment 1)
    expected_time_1 = (seg1_m / total_m) * 600  # proportional to first segment
    assert points[1]["lat"] == pytest.approx(37.6)
    assert points[1]["lng"] == pytest.approx(127.05)
    assert points[1]["cumulative_distance_m"] == pytest.approx(seg1_m)
    assert points[1]["cumulative_time_sec"] == pytest.approx(expected_time_1)

    # Point 2 (after segment 1+2)
    expected_time_2 = ((seg1_m + seg2_m) / total_m) * 600
    assert points[2]["lat"] == pytest.approx(37.65)
    assert points[2]["lng"] == pytest.approx(127.15)
    assert points[2]["cumulative_distance_m"] == pytest.approx(seg1_m + seg2_m)
    assert points[2]["cumulative_time_sec"] == pytest.approx(expected_time_2)

    # Point 3 (end, gets 100% of road duration)
    assert points[3]["lat"] == pytest.approx(37.7)
    assert points[3]["lng"] == pytest.approx(127.2)
    assert points[3]["cumulative_distance_m"] == pytest.approx(total_m)
    assert points[3]["cumulative_time_sec"] == pytest.approx(600.0)


def test_parse_route_points_handles_degenerate_road_in_middle():
    """Test that a degenerate road (< 2 vertexes) advances cumulative totals even when skipping point emission."""
    response = {
        "trans_id": "fake-trans-id",
        "routes": [
            {
                "result_code": 0,
                "result_msg": "",
                "summary": {
                    "origin": {"name": "", "x": 127.0, "y": 37.5},
                    "destination": {"name": "", "x": 127.1, "y": 37.6},
                    "distance": 20000,
                    "duration": 1400,
                },
                "sections": [
                    {
                        "distance": 20000,
                        "duration": 1400,
                        "roads": [
                            {
                                "name": "Road A (normal)",
                                "distance": 10000,
                                "duration": 600,
                                "traffic_speed": 40.0,
                                "traffic_state": 1,
                                "vertexes": [127.0, 37.5, 127.05, 37.55],
                            },
                            {
                                "name": "Road B (degenerate - single vertex)",
                                "distance": 5000,
                                "duration": 400,
                                "traffic_speed": 40.0,
                                "traffic_state": 1,
                                "vertexes": [127.05, 37.55],  # Only 1 coordinate pair, no segments
                            },
                            {
                                "name": "Road C (normal)",
                                "distance": 5000,
                                "duration": 400,
                                "traffic_speed": 40.0,
                                "traffic_state": 1,
                                "vertexes": [127.05, 37.55, 127.1, 37.6],
                            },
                        ],
                    }
                ],
            }
        ],
    }

    points = parse_route_points(response)

    # Should have 3 points: start (Road A) + end (Road C), Road B doesn't emit any points
    assert len(points) == 3

    # First point: Road A start
    assert points[0] == {"lat": 37.5, "lng": 127.0, "cumulative_distance_m": 0.0, "cumulative_time_sec": 0.0}

    # Second point: Road A end
    road_a_m = haversine_km(37.5, 127.0, 37.55, 127.05) * 1000
    assert points[1]["lat"] == pytest.approx(37.55)
    assert points[1]["lng"] == pytest.approx(127.05)
    assert points[1]["cumulative_distance_m"] == pytest.approx(road_a_m)
    assert points[1]["cumulative_time_sec"] == pytest.approx(600.0)

    # Third point: Road C end
    # The degenerate Road B should have added 5000m and 400s to cumulative totals
    road_c_m = haversine_km(37.55, 127.05, 37.6, 127.1) * 1000
    expected_cumulative_distance = road_a_m + 5000 + road_c_m  # Road A + Road B (dropped) + Road C
    expected_cumulative_time = 600 + 400 + 400  # Road A + Road B (dropped) + Road C
    assert points[2]["lat"] == pytest.approx(37.6)
    assert points[2]["lng"] == pytest.approx(127.1)
    assert points[2]["cumulative_distance_m"] == pytest.approx(expected_cumulative_distance)
    assert points[2]["cumulative_time_sec"] == pytest.approx(expected_cumulative_time)
