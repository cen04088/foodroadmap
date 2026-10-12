"""카카오맵 도보·자전거 경로 조회 (GET dapi.kakao.com/v2/routing/{walk,bicycle}).

자동차 길찾기(카카오모빌리티, directions.py)와 응답 모양이 달라 따로 파싱하지만, 결과는 같은 모양
(경로 점마다 누적 거리·누적 시간)으로 돌려줘 매칭·식사 플래너 코드를 그대로 쓴다.
자동차의 도로 지점 보정(route_fallback.py)은 쓰지 않는다 — 걸어서는 차도가 아니어도 갈 수 있다.
"""

import requests

from app.kakao.directions import KakaoDirectionsError, KakaoRouteError, build_route_points

KAKAO_ROUTING_URL = "https://dapi.kakao.com/v2/routing/{mode}"
ROUTING_MODES = ("walk", "bicycle")

# 카카오 문서의 status 설명을 화면에 그대로 보여줄 수 있는 문구로 옮긴 것.
STATUS_MESSAGES = {
    "SAME_POINT": "출발지와 도착지가 같아요",
    "START_LINK_NOT_FOUND": "출발지 주변에서 길을 찾을 수 없어요",
    "END_LINK_NOT_FOUND": "도착지 주변에서 길을 찾을 수 없어요",
    "TOO_MANY_SEARCH_LINK": "경로가 너무 복잡해요",
    "TOO_FAR_AWAY": "출발지와 도착지가 너무 멀어요",
    "ROUTE_RESULT_NOT_FOUND": "경로 결과가 없어요",
}


class KakaoRoutingStatusError(KakaoRouteError):
    """카카오가 OK가 아닌 status로 답한 경우. 같은 좌표로 다시 불러도 결과가 같다."""

    def __init__(self, status: str | None):
        super().__init__(None, STATUS_MESSAGES.get(status or "", "경로 결과가 없어요"))
        self.status = status


def fetch_routing(
    mode: str,
    origin_lat: float,
    origin_lng: float,
    dest_lat: float,
    dest_lng: float,
    api_key: str,
    *,
    timeout: float | tuple[float, float] = (5.0, 20.0),
) -> dict:
    if mode not in ROUTING_MODES:
        raise ValueError(f"unsupported routing mode: {mode}")
    params = {
        "start_x": str(origin_lng),
        "start_y": str(origin_lat),
        "end_x": str(dest_lng),
        "end_y": str(dest_lat),
    }
    headers = {"Authorization": f"KakaoAK {api_key}"}

    try:
        response = requests.get(KAKAO_ROUTING_URL.format(mode=mode), params=params, headers=headers, timeout=timeout)
    except requests.RequestException as exc:
        raise KakaoDirectionsError(f"Kakao routing request failed: {exc}") from exc

    # 경로를 못 만든 사유(status)가 HTTP 오류 코드와 함께 올 수도 있다 — 그때도 사유를 살려 422로 안내한다.
    # 사유가 없는 HTTP 오류(키 오류, 할당량 초과 등)는 일시적/설정 문제로 보고 그대로 올린다.
    body = _json_or_none(response)
    if not isinstance(body, dict):
        raise KakaoDirectionsError(f"Kakao routing returned a non-JSON response: HTTP {response.status_code}")
    if response.ok or body.get("status") in STATUS_MESSAGES:
        return body
    raise KakaoDirectionsError(f"Kakao routing request failed: HTTP {response.status_code}")


def parse_routing_summary(response: dict) -> dict:
    properties = _route(response).get("properties") or {}
    return {
        "total_distance_m": properties.get("totalDistance"),
        "total_duration_sec": properties.get("totalTime"),
    }


def parse_routing_points(response: dict) -> list[dict]:
    route = _route(response)

    def steps():
        for leg in route.get("legs") or []:
            for step in leg.get("steps") or []:
                properties = step.get("properties") or {}
                raw_points = (step.get("path") or {}).get("points") or []
                coords = [(p[0], p[1]) for p in raw_points if _is_coordinate(p)]  # [x, y] = (lng, lat)
                yield coords, properties.get("distance") or 0, properties.get("time") or 0

    return build_route_points(steps())


def _route(response: dict) -> dict:
    status = response.get("status")
    if status != "OK":
        raise KakaoRoutingStatusError(status)
    route = response.get("route")
    if not isinstance(route, dict):
        raise KakaoRoutingStatusError(None)
    return route


def _is_coordinate(value) -> bool:
    return (
        isinstance(value, (list, tuple))
        and len(value) >= 2
        and all(isinstance(v, (int, float)) and not isinstance(v, bool) for v in value[:2])
    )


def _json_or_none(response: requests.Response):
    try:
        return response.json()
    except ValueError:
        return None
