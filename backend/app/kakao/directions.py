import requests

from app.geo import haversine_km

KAKAO_DIRECTIONS_URL = "https://apis-navi.kakaomobility.com/v1/directions"


class KakaoDirectionsError(Exception):
    """길찾기 호출 자체가 실패한 경우(네트워크, HTTP 오류, JSON 아님). 재시도하면 될 수도 있다."""


class KakaoRouteError(KakaoDirectionsError):
    """카카오가 응답은 했지만 경로를 만들지 못한 경우(출발/도착지 주변 도로 없음, 자동차 진입 불가,
    결과 없음 등). 같은 좌표로 재시도해도 결과가 같으므로 호출자는 사용자에게 장소를 바꾸라고 안내한다."""

    def __init__(self, result_code: int | None, result_msg: str | None):
        super().__init__(f"Kakao Directions API error [{result_code}]: {result_msg}")
        self.result_code = result_code
        self.result_msg = result_msg or ""


def fetch_route(
    origin_lat: float,
    origin_lng: float,
    dest_lat: float,
    dest_lng: float,
    api_key: str,
    *,
    # (연결, 응답) 초. 서울→부산처럼 긴 경로는 응답 본문이 수 MB라 읽기 시간을 넉넉히 준다.
    timeout: float | tuple[float, float] = (5.0, 20.0),
    # 카카오 유고(교통 통제) 정보 반영 옵션. 2면 전체 미반영 — 통제 때문에 경로가 안 나올 때 재시도용.
    roadevent: int | None = None,
) -> dict:
    params = {
        "origin": f"{origin_lng},{origin_lat}",
        "destination": f"{dest_lng},{dest_lat}",
    }
    if roadevent is not None:
        params["roadevent"] = str(roadevent)
    headers = {"Authorization": f"KakaoAK {api_key}"}

    try:
        response = requests.get(KAKAO_DIRECTIONS_URL, params=params, headers=headers, timeout=timeout)
        response.raise_for_status()
        return response.json()
    except requests.RequestException as exc:
        raise KakaoDirectionsError(f"Kakao Directions API request failed: {exc}") from exc


def parse_route_summary(response: dict) -> dict:
    route = _first_route(response)
    summary = route.get("summary", {})
    return {
        "total_distance_m": summary.get("distance"),
        "total_duration_sec": summary.get("duration"),
    }


def parse_route_points(response: dict) -> list[dict]:
    route = _first_route(response)

    points: list[dict] = []
    cumulative_distance_m = 0.0
    cumulative_time_sec = 0.0

    for section in route.get("sections", []):
        for road in section.get("roads", []):
            vertexes = road.get("vertexes") or []
            coords = list(zip(vertexes[0::2], vertexes[1::2]))  # (lng, lat) pairs

            road_duration_sec = road.get("duration", 0)

            if len(coords) < 2:
                # Degenerate road with < 2 vertexes: skip point emission but still advance cumulative totals
                cumulative_distance_m += road.get("distance", 0)
                cumulative_time_sec += road_duration_sec
                continue

            seg_lengths_m = []
            for (lng1, lat1), (lng2, lat2) in zip(coords, coords[1:]):
                seg_lengths_m.append(haversine_km(lat1, lng1, lat2, lng2) * 1000)
            total_len_m = sum(seg_lengths_m)

            if not points:
                lng0, lat0 = coords[0]
                points.append(
                    {
                        "lat": lat0,
                        "lng": lng0,
                        "cumulative_distance_m": 0.0,
                        "cumulative_time_sec": 0.0,
                    }
                )

            running_len_m = 0.0
            for (lng, lat), seg_len_m in zip(coords[1:], seg_lengths_m):
                running_len_m += seg_len_m
                fraction = (running_len_m / total_len_m) if total_len_m > 0 else 1.0
                points.append(
                    {
                        "lat": lat,
                        "lng": lng,
                        "cumulative_distance_m": cumulative_distance_m + running_len_m,
                        "cumulative_time_sec": cumulative_time_sec + fraction * road_duration_sec,
                    }
                )

            cumulative_distance_m += total_len_m
            cumulative_time_sec += road_duration_sec

    return points


def _first_route(response: dict) -> dict:
    routes = response.get("routes") or []
    if not routes:
        raise KakaoRouteError(None, "경로 결과가 없습니다")

    route = routes[0]
    if route.get("result_code", 0) != 0:
        raise KakaoRouteError(route.get("result_code"), route.get("result_msg"))

    return route
