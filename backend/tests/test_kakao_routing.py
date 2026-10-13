from unittest.mock import Mock, patch

import pytest
import requests

from app.kakao.directions import KakaoDirectionsError
from app.kakao.routing import (
    KakaoRoutingStatusError,
    fetch_routing,
    parse_routing_points,
    parse_routing_summary,
)

# 카카오맵 REST API 문서(도보 경로 조회, 2026-10-12 확인)의 응답 스키마를 따른 합성 응답.
# route는 객체, path.points는 [x(경도), y(위도)] 숫자 쌍 배열, 시간은 초 단위다. 자전거 응답도 같은 모양이다.
FAKE_WALK_RESPONSE = {
    "status": "OK",
    "route": {
        "properties": {"totalDistance": 1500, "totalTime": 1200, "landingUrl": "https://map.kakao.com/"},
        "legs": [
            {
                "properties": {"distance": 1500, "time": 1200},
                "steps": [
                    {
                        "properties": {"distance": 1000, "time": 800, "guidance": "직진", "x": 127.0, "y": 37.5},
                        "path": {"points": [[127.0, 37.5], [127.005, 37.505], [127.01, 37.51]]},
                    },
                    {
                        "properties": {"distance": 500, "time": 400, "guidance": "도착", "x": 127.01, "y": 37.51},
                        "path": {"points": [[127.01, 37.51], [127.015, 37.515]]},
                    },
                ],
            }
        ],
    },
}


def test_parse_routing_summary_reads_total_distance_and_time():
    assert parse_routing_summary(FAKE_WALK_RESPONSE) == {"total_distance_m": 1500, "total_duration_sec": 1200}


def test_parse_routing_points_accumulates_time_across_steps():
    points = parse_routing_points(FAKE_WALK_RESPONSE)

    assert (points[0]["lat"], points[0]["lng"]) == (37.5, 127.0)
    assert points[0]["cumulative_time_sec"] == 0
    # 첫 단계 안의 중간 점은 그 단계 시간(800초)의 절반쯤, 끝점은 800초.
    assert points[1]["cumulative_time_sec"] == pytest.approx(400, rel=0.01)
    assert points[2]["cumulative_time_sec"] == pytest.approx(800)
    # 둘째 단계는 앞 단계의 누적 위에 이어진다.
    assert points[-1]["cumulative_time_sec"] == pytest.approx(1200)
    assert points[-1]["cumulative_distance_m"] > points[2]["cumulative_distance_m"] > 0
    times = [p["cumulative_time_sec"] for p in points]
    assert times == sorted(times)


def test_parse_routing_points_skips_malformed_coordinates():
    response = {
        "status": "OK",
        "route": {
            "properties": {"totalDistance": 100, "totalTime": 60},
            "legs": [{"steps": [{"properties": {"distance": 100, "time": 60}, "path": {"points": [[127.0, 37.5], ["x", None], [127.001, 37.501]]}}]}],
        },
    }
    points = parse_routing_points(response)
    assert [(p["lng"], p["lat"]) for p in points] == [(127.0, 37.5), (127.001, 37.501)]


@pytest.mark.parametrize("status", ["TOO_FAR_AWAY", "START_LINK_NOT_FOUND", "ROUTE_RESULT_NOT_FOUND", "SOMETHING_NEW", None])
def test_non_ok_status_raises_route_error_with_status(status):
    with pytest.raises(KakaoRoutingStatusError) as excinfo:
        parse_routing_points({"status": status} if status else {})
    assert excinfo.value.status == status
    assert excinfo.value.result_msg


def test_fetch_routing_sends_lng_lat_as_x_y_and_auth_header():
    fake = Mock(ok=True, status_code=200)
    fake.json.return_value = FAKE_WALK_RESPONSE
    with patch("app.kakao.routing.requests.get", return_value=fake) as get:
        assert fetch_routing("walk", 37.5, 127.0, 37.6, 127.1, "key") == FAKE_WALK_RESPONSE

    url = get.call_args.args[0]
    kwargs = get.call_args.kwargs
    assert url == "https://dapi.kakao.com/v2/routing/walk"
    assert kwargs["params"] == {"start_x": "127.0", "start_y": "37.5", "end_x": "127.1", "end_y": "37.6"}
    assert kwargs["headers"] == {"Authorization": "KakaoAK key"}


def test_fetch_routing_keeps_status_body_from_http_error_so_the_reason_survives():
    fake = Mock(ok=False, status_code=400)
    fake.json.return_value = {"status": "TOO_FAR_AWAY"}
    with patch("app.kakao.routing.requests.get", return_value=fake):
        body = fetch_routing("bicycle", 37.5, 127.0, 35.1, 129.0, "key")
    with pytest.raises(KakaoRoutingStatusError):
        parse_routing_points(body)


def test_fetch_routing_raises_directions_error_for_http_error_without_status():
    fake = Mock(ok=False, status_code=401)
    fake.json.return_value = {"errorType": "AccessDeniedError", "message": "wrong appKey"}
    with patch("app.kakao.routing.requests.get", return_value=fake):
        with pytest.raises(KakaoDirectionsError) as excinfo:
            fetch_routing("walk", 37.5, 127.0, 37.6, 127.1, "key")
    # 콘솔 설정 문제를 바로 알 수 있게 카카오가 준 사유를 오류 메시지에 남긴다.
    assert "HTTP 401" in str(excinfo.value)
    assert "AccessDeniedError: wrong appKey" in str(excinfo.value)


def test_fetch_routing_raises_directions_error_on_network_failure():
    with patch("app.kakao.routing.requests.get", side_effect=requests.ConnectionError("down")):
        with pytest.raises(KakaoDirectionsError):
            fetch_routing("walk", 37.5, 127.0, 37.6, 127.1, "key")


def test_fetch_routing_rejects_unknown_mode():
    with pytest.raises(ValueError):
        fetch_routing("car", 37.5, 127.0, 37.6, 127.1, "key")
