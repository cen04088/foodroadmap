"""카카오 길찾기가 출발/도착 지점 주변 도로 문제로 실패하면 가장 가까운 도로 지점으로 보정해 다시 시도한다.

보행자 전용 거리·공원·섬처럼 차가 못 들어가는 곳을 목적지로 고르는 일은 흔하다. 그때 오류로 끝내지 않고
그 지점을 8방향으로 200m, 이어서 450m 옮긴 좌표 중 경로가 만들어지는 첫 지점을 쓰고, 보정 사실을
adjustments로 돌려줘 화면에서 "약 200m 떨어진 도로 지점까지 안내" 식으로 알린다.
주차장 검색 같은 의미 기반 보정은 쓰지 않는다 — 목표는 가장 가까운 도로다.
"""

import logging
import math
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from typing import Callable

from app.kakao.directions import KakaoRouteError, fetch_route, parse_route_summary

logger = logging.getLogger(__name__)

# 보정 링(미터)과 방위. 링 하나(8지점)는 병렬로 호출하고, 성공한 지점이 여러 개면 북쪽부터 시계 방향으로 첫 것을 쓴다.
OFFSET_RINGS_M: tuple[int, ...] = (200, 450)
BEARINGS_DEG: tuple[int, ...] = (0, 45, 90, 135, 180, 225, 270, 315)
MAX_WORKERS = 8

# 카카오 result_msg 문구로 어느 끝점이 문제인지 가른다. 결과 코드 표는 문서 버전마다 달라 문구를 우선한다.
ORIGIN_KEYWORDS = ("시작", "출발")
DESTINATION_KEYWORDS = ("도착", "목적")
ROAD_PROBLEM_KEYWORDS = ("도로", "진입")
ROAD_EVENT_KEYWORDS = ("유고", "장애", "통제")

Endpoint = str  # "origin" | "destination"
Point = tuple[float, float]  # (lat, lng)


@dataclass
class EndpointAdjustment:
    lat: float
    lng: float
    # 0이면 좌표는 그대로 두고 교통 통제(유고) 정보만 제외해 계산했다는 뜻.
    offset_m: int
    reason: str


def offset_point(lat: float, lng: float, distance_m: float, bearing_deg: float) -> Point:
    """lat/lng에서 bearing 방향으로 distance_m 떨어진 좌표. 수백 m 규모라 평면 근사로 충분하다."""
    rad = math.radians(bearing_deg)
    dlat = (distance_m * math.cos(rad)) / 111_320
    dlng = (distance_m * math.sin(rad)) / (111_320 * max(math.cos(math.radians(lat)), 1e-9))
    return lat + dlat, lng + dlng


def failed_endpoint(exc: KakaoRouteError) -> Endpoint | None:
    msg = exc.result_msg
    if any(k in msg for k in ORIGIN_KEYWORDS):
        return "origin"
    if any(k in msg for k in DESTINATION_KEYWORDS):
        return "destination"
    return None


def resolve_route(
    origin_lat: float,
    origin_lng: float,
    dest_lat: float,
    dest_lng: float,
    api_key: str,
    *,
    fetch: Callable[..., dict] = fetch_route,
) -> tuple[dict, dict[Endpoint, EndpointAdjustment | None]]:
    """경로 응답과 끝점 보정 내역을 돌려준다. 보정으로도 안 되면 처음 받은 KakaoRouteError를 그대로 올린다.

    fetch를 주입받는 이유: 라우트 핸들러가 자기 모듈의 fetch_route 이름을 넘기므로, 테스트가 그 이름만
    monkeypatch해도 여기까지 적용된다. 네트워크/HTTP 실패(KakaoDirectionsError)는 보정 대상이 아니라 그대로 올린다.
    양 끝점이 동시에 문제인 경우는 지원하지 않는다 — 한 끝점을 옮겨도 다른 끝점 때문에 전부 실패하면 원래 오류가 난다.
    """
    points: dict[Endpoint, Point] = {"origin": (origin_lat, origin_lng), "destination": (dest_lat, dest_lng)}
    adjustments: dict[Endpoint, EndpointAdjustment | None] = {"origin": None, "destination": None}
    roadevent: int | None = None

    try:
        return _call(fetch, points, api_key, roadevent), adjustments
    except KakaoRouteError as exc:
        # except 절의 as 변수는 블록이 끝나면 지워지므로 따로 이름을 잡아 둔다.
        error = exc
    first_error = error

    # 1) 유고(교통 통제) 때문이면 좌표는 그대로 두고 유고 미반영(roadevent=2)으로 한 번 더 시도한다.
    if any(k in error.result_msg for k in ROAD_EVENT_KEYWORDS):
        roadevent = 2
        try:
            response = _call(fetch, points, api_key, roadevent)
        except KakaoRouteError as exc:
            error = exc
        else:
            endpoint = failed_endpoint(first_error) or "destination"
            lat, lng = points[endpoint]
            adjustments[endpoint] = EndpointAdjustment(lat, lng, 0, first_error.result_msg)
            logger.info("route recomputed without road events: %s", first_error.result_msg)
            return response, adjustments

    # 2) 어느 끝점의 도로 문제인지 알면 그 끝점만, 모르지만 도로 문제로 보이면 도착지→출발지 순으로 보정한다.
    #    "길찾기 결과를 찾을 수 없음"처럼 좌표와 무관한 실패는 옮겨도 소용없으니 바로 올린다.
    endpoint = failed_endpoint(error)
    if endpoint is not None:
        order = [endpoint]
    elif any(k in error.result_msg for k in ROAD_PROBLEM_KEYWORDS):
        order = ["destination", "origin"]
    else:
        raise error

    for endpoint in order:
        snapped = _snap_to_road(fetch, points, endpoint, api_key, roadevent)
        if snapped is None:
            continue
        response, new_point, offset_m = snapped
        adjustments[endpoint] = EndpointAdjustment(new_point[0], new_point[1], offset_m, error.result_msg)
        logger.info("route endpoint snapped %s by %dm: %s", endpoint, offset_m, error.result_msg)
        return response, adjustments

    raise error


def _call(fetch: Callable[..., dict], points: dict[Endpoint, Point], api_key: str, roadevent: int | None) -> dict:
    origin, destination = points["origin"], points["destination"]
    kwargs = {"roadevent": roadevent} if roadevent is not None else {}
    response = fetch(origin[0], origin[1], destination[0], destination[1], api_key, **kwargs)
    parse_route_summary(response)  # result_code != 0 이면 여기서 KakaoRouteError가 난다
    return response


def _snap_to_road(
    fetch: Callable[..., dict],
    points: dict[Endpoint, Point],
    endpoint: Endpoint,
    api_key: str,
    roadevent: int | None,
) -> tuple[dict, Point, int] | None:
    base_lat, base_lng = points[endpoint]
    for ring_m in OFFSET_RINGS_M:
        candidates = [offset_point(base_lat, base_lng, ring_m, bearing) for bearing in BEARINGS_DEG]

        def attempt(candidate: Point) -> dict | None:
            trial = {**points, endpoint: candidate}
            try:
                return _call(fetch, trial, api_key, roadevent)
            except KakaoRouteError:
                return None

        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
            responses = list(pool.map(attempt, candidates))
        for candidate, response in zip(candidates, responses):
            if response is not None:
                return response, candidate, ring_m
    return None
