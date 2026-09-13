import pytest

from app.geo import haversine_km
from app.kakao.directions import KakaoDirectionsError, KakaoRouteError
from app.kakao.route_fallback import BEARINGS_DEG, OFFSET_RINGS_M, offset_point, resolve_route

OK_RESPONSE = {"routes": [{"result_code": 0, "result_msg": "", "summary": {"distance": 1000, "duration": 120}, "sections": []}]}
ORIGIN = (37.5547, 126.9707)
DEST = (35.8151, 127.1531)


def failing(msg: str, code: int = 302) -> dict:
    return {"routes": [{"result_code": code, "result_msg": msg}]}


def same(a, b) -> bool:
    return abs(a[0] - b[0]) < 1e-9 and abs(a[1] - b[1]) < 1e-9


def make_fetch(decide):
    calls = []

    def fetch(o_lat, o_lng, d_lat, d_lng, api_key, **kwargs):
        calls.append({"origin": (o_lat, o_lng), "destination": (d_lat, d_lng), "roadevent": kwargs.get("roadevent")})
        return decide((o_lat, o_lng), (d_lat, d_lng), kwargs.get("roadevent"))

    return fetch, calls


def test_offset_point_moves_roughly_the_requested_distance():
    moved = offset_point(37.5, 127.0, 200, 45)
    assert abs(haversine_km(37.5, 127.0, *moved) * 1000 - 200) < 2


def test_route_without_problems_is_returned_untouched():
    fetch, calls = make_fetch(lambda o, d, roadevent: OK_RESPONSE)
    response, adjustments = resolve_route(*ORIGIN, *DEST, "key", fetch=fetch)
    assert response == OK_RESPONSE
    assert adjustments == {"origin": None, "destination": None}
    assert len(calls) == 1


def test_destination_is_snapped_to_the_first_working_offset_in_the_first_ring():
    good = offset_point(*DEST, OFFSET_RINGS_M[0], 90)  # 200m east

    def decide(o, d, roadevent):
        return OK_RESPONSE if same(d, good) else failing("도착 지점 주변의 도로에 자동차 진입 불가")

    fetch, calls = make_fetch(decide)
    response, adjustments = resolve_route(*ORIGIN, *DEST, "key", fetch=fetch)

    assert response == OK_RESPONSE
    assert adjustments["origin"] is None
    adjusted = adjustments["destination"]
    assert adjusted.offset_m == OFFSET_RINGS_M[0]
    assert same((adjusted.lat, adjusted.lng), good)
    assert "진입 불가" in adjusted.reason
    assert all(same(c["origin"], ORIGIN) for c in calls)  # 출발지는 건드리지 않는다
    assert len(calls) == 1 + len(BEARINGS_DEG)  # 원본 1회 + 첫 링만


def test_second_ring_is_used_when_the_first_ring_fails_everywhere():
    good = offset_point(*DEST, OFFSET_RINGS_M[1], 180)  # 450m south

    def decide(o, d, roadevent):
        return OK_RESPONSE if same(d, good) else failing("도착 지점 주변의 도로를 탐색할 수 없음", 103)

    fetch, calls = make_fetch(decide)
    _, adjustments = resolve_route(*ORIGIN, *DEST, "key", fetch=fetch)
    assert adjustments["destination"].offset_m == OFFSET_RINGS_M[1]
    assert len(calls) == 1 + 2 * len(BEARINGS_DEG)


def test_origin_failure_snaps_the_origin_and_keeps_the_destination():
    good = offset_point(*ORIGIN, OFFSET_RINGS_M[0], 0)  # 200m north

    def decide(o, d, roadevent):
        return OK_RESPONSE if same(o, good) else failing("시작 지점 주변의 도로를 탐색할 수 없음", 102)

    fetch, calls = make_fetch(decide)
    _, adjustments = resolve_route(*ORIGIN, *DEST, "key", fetch=fetch)
    assert adjustments["destination"] is None
    assert same((adjustments["origin"].lat, adjustments["origin"].lng), good)
    assert all(same(c["destination"], DEST) for c in calls)


def test_all_offsets_failing_reraises_the_original_error_after_both_rings():
    fetch, calls = make_fetch(lambda o, d, roadevent: failing("도착 지점 주변의 도로에 자동차 진입 불가"))
    with pytest.raises(KakaoRouteError) as info:
        resolve_route(*ORIGIN, *DEST, "key", fetch=fetch)
    assert info.value.result_msg == "도착 지점 주변의 도로에 자동차 진입 불가"
    assert len(calls) == 1 + len(OFFSET_RINGS_M) * len(BEARINGS_DEG)


def test_failures_unrelated_to_the_endpoints_are_not_retried():
    fetch, calls = make_fetch(lambda o, d, roadevent: failing("길찾기 결과를 찾을 수 없음", 1))
    with pytest.raises(KakaoRouteError):
        resolve_route(*ORIGIN, *DEST, "key", fetch=fetch)
    assert len(calls) == 1


def test_road_event_failure_is_retried_without_road_events_before_moving_anything():
    def decide(o, d, roadevent):
        return OK_RESPONSE if roadevent == 2 else failing("도착 지점 주변의 도로에 유고 정보(교통 장애)가 있음", 106)

    fetch, calls = make_fetch(decide)
    response, adjustments = resolve_route(*ORIGIN, *DEST, "key", fetch=fetch)
    assert response == OK_RESPONSE
    assert len(calls) == 2
    assert calls[0]["roadevent"] is None and calls[1]["roadevent"] == 2
    adjusted = adjustments["destination"]
    assert adjusted.offset_m == 0 and same((adjusted.lat, adjusted.lng), DEST)
    assert "유고" in adjusted.reason


def test_transport_errors_propagate_instead_of_being_swallowed_by_snapping():
    state = {"n": 0}

    def decide(o, d, roadevent):
        state["n"] += 1
        if state["n"] == 1:
            return failing("도착 지점 주변의 도로에 자동차 진입 불가")
        raise KakaoDirectionsError("network down")

    fetch, _ = make_fetch(decide)
    with pytest.raises(KakaoDirectionsError) as info:
        resolve_route(*ORIGIN, *DEST, "key", fetch=fetch)
    assert not isinstance(info.value, KakaoRouteError)
