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
