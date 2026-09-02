import requests

from app.geo import haversine_km

KAKAO_DIRECTIONS_URL = "https://apis-navi.kakaomobility.com/v1/directions"


class KakaoDirectionsError(Exception):
    pass


def fetch_route(
    origin_lat: float,
    origin_lng: float,
    dest_lat: float,
    dest_lng: float,
    api_key: str,
    *,
    timeout: float = 10.0,
) -> dict:
    params = {
        "origin": f"{origin_lng},{origin_lat}",
        "destination": f"{dest_lng},{dest_lat}",
    }
    headers = {"Authorization": f"KakaoAK {api_key}"}

    try:
        response = requests.get(KAKAO_DIRECTIONS_URL, params=params, headers=headers, timeout=timeout)
        response.raise_for_status()
    except requests.RequestException as exc:
        raise KakaoDirectionsError(f"Kakao Directions API request failed: {exc}") from exc

    return response.json()


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
            if len(coords) < 2:
                continue

            road_duration_sec = road.get("duration", 0)

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
        raise KakaoDirectionsError("Kakao Directions API returned no routes")

    route = routes[0]
    if route.get("result_code", 0) != 0:
        raise KakaoDirectionsError(f"Kakao Directions API error: {route.get('result_msg')}")

    return route
