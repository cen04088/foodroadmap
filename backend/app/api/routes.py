from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.config import MissingKakaoApiKeyError, get_kakao_api_key
from app.db import make_engine, make_session_factory
from app.geo import bounding_box_with_margin
from app.kakao.directions import KakaoDirectionsError, fetch_route, parse_route_points, parse_route_summary
from app.matching import RestaurantMatch, match_restaurants_to_route
from app.repository import list_broadcasts_with_counts, query_candidate_restaurants

router = APIRouter()

DEFAULT_RADIUS_KM = 2.0

_ENGINE = make_engine()
_SESSION_FACTORY = make_session_factory(_ENGINE)


def get_session():
    with _SESSION_FACTORY() as session:
        yield session


def _parse_lat_lng(value: str) -> tuple[float, float]:
    try:
        lat_str, lng_str = value.split(",")
        return float(lat_str), float(lng_str)
    except (ValueError, AttributeError) as exc:
        raise HTTPException(status_code=400, detail=f"잘못된 좌표 형식입니다: {value}") from exc


def _serialize_match(match: RestaurantMatch) -> dict:
    restaurant = match.restaurant
    return {
        "id": restaurant.id,
        "name": restaurant.name,
        "category": restaurant.category,
        "address": restaurant.address,
        "latitude": restaurant.latitude,
        "longitude": restaurant.longitude,
        "phone": restaurant.phone,
        "hours": restaurant.hours,
        "distance_from_route_km": round(match.distance_from_route_km, 3),
        "cumulative_time_sec": round(match.cumulative_time_sec),
        "broadcasts": [b.name for b in restaurant.broadcasts],
    }


@router.get("/api/broadcasts")
def get_broadcasts(session: Session = Depends(get_session)):
    return {"broadcasts": list_broadcasts_with_counts(session)}


@router.get("/api/route-restaurants")
def get_route_restaurants(
    origin: str = Query(..., description="lat,lng"),
    destination: str = Query(..., description="lat,lng"),
    radius_km: float = Query(DEFAULT_RADIUS_KM, gt=0, le=50),
    broadcast: str | None = Query(None),
    category: str | None = Query(None),
    session: Session = Depends(get_session),
):
    origin_lat, origin_lng = _parse_lat_lng(origin)
    dest_lat, dest_lng = _parse_lat_lng(destination)

    try:
        api_key = get_kakao_api_key()
    except MissingKakaoApiKeyError as exc:
        raise HTTPException(status_code=500, detail="서버 설정 오류: 카카오 API 키가 설정되지 않았습니다") from exc

    try:
        raw_response = fetch_route(origin_lat, origin_lng, dest_lat, dest_lng, api_key)
        route_points = parse_route_points(raw_response)
        route_summary = parse_route_summary(raw_response)
    except KakaoDirectionsError as exc:
        if "탐색할 수 없음" in str(exc):
            # 출발/도착 좌표 주변에 카카오 도로 데이터가 없는 경우 (섬, 사유지 등) — 재시도해도 동일하게 실패하므로
            # 일시적 오류(502)와 구분해 다른 장소를 선택하라고 안내한다.
            raise HTTPException(
                status_code=422,
                detail="선택한 위치 근처에서 자동차 경로를 찾을 수 없어요. 다른 장소를 선택해보세요",
            ) from exc
        raise HTTPException(status_code=502, detail=f"경로를 가져오지 못했습니다: {exc}") from exc

    if len(route_points) < 2:
        raise HTTPException(status_code=502, detail="경로를 계산할 수 없습니다")

    min_lat, max_lat, min_lng, max_lng = bounding_box_with_margin(route_points, radius_km)
    candidates = query_candidate_restaurants(
        session, min_lat, max_lat, min_lng, max_lng, broadcast_slug=broadcast, category=category
    )
    matches = match_restaurants_to_route(route_points, candidates, radius_km)

    return {
        "route": {
            "total_distance_m": route_summary["total_distance_m"],
            "total_duration_sec": route_summary["total_duration_sec"],
            "points": route_points,
        },
        "restaurants": [_serialize_match(m) for m in matches],
    }
