import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool

from app.api.main import app
from app.api.routes import get_session
from app.db import init_db, make_session_factory
from app.models import Broadcast, MenuItem, Restaurant


@pytest.mark.parametrize("origin", ["nan,127", "37,inf", "91,127", "37,181"])
def test_invalid_coordinate_range_rejected_before_external_call(origin, monkeypatch):
    def unexpected(*args, **kwargs):
        pytest.fail("Invalid coordinates must not reach the route provider")
    monkeypatch.setattr("app.api.routes.resolve_route", unexpected)
    response = TestClient(app).get("/api/route-restaurants", params={"origin": origin, "destination": "37,127"})
    assert response.status_code == 400

# 실제 카카오모빌리티 API로 라이브 검증된 구조의 합성 응답 (test_kakao_directions.py의 FAKE_RESPONSE와 동일한 구조).
FAKE_KAKAO_RESPONSE = {
    "routes": [
        {
            "result_code": 0,
            "result_msg": "",
            "summary": {"distance": 15000, "duration": 1200},
            "sections": [
                {
                    "distance": 15000,
                    "duration": 1200,
                    "roads": [
                        {
                            "name": "Road A",
                            "distance": 15000,
                            "duration": 1200,
                            "vertexes": [127.0, 37.5, 127.05, 37.55, 127.1, 37.6],
                        }
                    ],
                }
            ],
        }
    ]
}


def make_test_session_factory():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    init_db(engine)
    return make_session_factory(engine)


def seed(session_factory):
    with session_factory() as session:
        ttoganjib = Broadcast(id="ttoganjib", name="또간집")
        session.add(ttoganjib)

        near = Restaurant(
            id="near",
            name="Near Restaurant",
            latitude=37.55,
            longitude=127.05,
            category="한식",
            youtube_url="https://www.youtube.com/watch?v=abc123",
        )
        near.broadcasts.append(ttoganjib)
        near.menu_items = [MenuItem(name="대표 메뉴", price_won=12000, is_representative=True, position=0)]

        far = Restaurant(id="far", name="Far Restaurant", latitude=38.5, longitude=128.5, category="한식")

        # ~1.5km perpendicular from the route line (see test_radius_km_* tests below):
        # excluded at radius_km=1.0, included at radius_km=3.0 (and at the 2.0 default).
        medium = Restaurant(
            id="medium",
            name="Medium Restaurant",
            latitude=37.558384,
            longitude=127.036679,
            category="한식",
        )

        session.add_all([near, far, medium])
        session.commit()


def override_get_session_factory(session_factory):
    def _override():
        with session_factory() as session:
            yield session

    return _override


def test_get_route_restaurants_returns_nearby_restaurant_with_expected_shape(monkeypatch):
    monkeypatch.setenv("KAKAO_REST_API_KEY", "test-key")
    monkeypatch.setattr(
        "app.api.routes.fetch_route", lambda *args, **kwargs: FAKE_KAKAO_RESPONSE
    )

    session_factory = make_test_session_factory()
    seed(session_factory)
    app.dependency_overrides[get_session] = override_get_session_factory(session_factory)

    client = TestClient(app)
    try:
        response = client.get(
            "/api/route-restaurants",
            params={"origin": "37.5,127.0", "destination": "37.6,127.1"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    body = response.json()

    assert body["route"]["total_distance_m"] == 15000
    assert body["route"]["total_duration_sec"] == 1200

    names = [r["name"] for r in body["restaurants"]]
    assert "Near Restaurant" in names
    assert "Far Restaurant" not in names

    near_result = next(r for r in body["restaurants"] if r["name"] == "Near Restaurant")
    assert near_result["broadcasts"] == ["또간집"]
    assert "distance_from_route_km" in near_result
    assert "cumulative_time_sec" in near_result
    assert near_result["youtube_url"] == "https://www.youtube.com/watch?v=abc123"
    assert near_result["menu"] == [{"name": "대표 메뉴", "price_won": 12000, "is_representative": True}]
    assert body["adjustments"] == {"origin": None, "destination": None}


def test_get_route_restaurants_snaps_a_blocked_destination_and_reports_the_adjustment(monkeypatch):
    from app.kakao.route_fallback import offset_point

    monkeypatch.setenv("KAKAO_REST_API_KEY", "test-key")
    good = offset_point(37.6, 127.1, 200, 0)

    def fake_fetch(o_lat, o_lng, d_lat, d_lng, api_key, **kwargs):
        if abs(d_lat - good[0]) < 1e-9 and abs(d_lng - good[1]) < 1e-9:
            return FAKE_KAKAO_RESPONSE
        return {"routes": [{"result_code": 302, "result_msg": "도착 지점 주변의 도로에 자동차 진입 불가"}]}

    monkeypatch.setattr("app.api.routes.fetch_route", fake_fetch)
    session_factory = make_test_session_factory()
    seed(session_factory)
    app.dependency_overrides[get_session] = override_get_session_factory(session_factory)

    client = TestClient(app)
    try:
        response = client.get(
            "/api/route-restaurants",
            params={"origin": "37.5,127.0", "destination": "37.6,127.1"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    body = response.json()
    assert body["adjustments"]["origin"] is None
    adjusted = body["adjustments"]["destination"]
    assert adjusted["offset_m"] == 200
    assert "진입 불가" in adjusted["reason"]
    assert abs(adjusted["lat"] - good[0]) < 1e-9 and abs(adjusted["lng"] - good[1]) < 1e-9
    assert [r["name"] for r in body["restaurants"]] and "Near Restaurant" in [r["name"] for r in body["restaurants"]]


def test_get_route_restaurants_filters_by_broadcast_query_param(monkeypatch):
    monkeypatch.setenv("KAKAO_REST_API_KEY", "test-key")
    monkeypatch.setattr(
        "app.api.routes.fetch_route", lambda *args, **kwargs: FAKE_KAKAO_RESPONSE
    )

    session_factory = make_test_session_factory()
    seed(session_factory)
    app.dependency_overrides[get_session] = override_get_session_factory(session_factory)

    client = TestClient(app)
    try:
        response = client.get(
            "/api/route-restaurants",
            params={
                "origin": "37.5,127.0",
                "destination": "37.6,127.1",
                "broadcast": "no-such-program",
            },
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["restaurants"] == []


def test_get_route_restaurants_filters_by_broadcast_display_name(monkeypatch):
    monkeypatch.setenv("KAKAO_REST_API_KEY", "test-key")
    monkeypatch.setattr(
        "app.api.routes.fetch_route", lambda *args, **kwargs: FAKE_KAKAO_RESPONSE
    )

    session_factory = make_test_session_factory()
    seed(session_factory)
    app.dependency_overrides[get_session] = override_get_session_factory(session_factory)

    client = TestClient(app)
    try:
        response = client.get(
            "/api/route-restaurants",
            params={
                "origin": "37.5,127.0",
                "destination": "37.6,127.1",
                "broadcast": "또간집",
            },
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    names = [r["name"] for r in response.json()["restaurants"]]
    assert names == ["Near Restaurant"]


def test_get_route_restaurants_radius_km_override_changes_included_restaurants(monkeypatch):
    monkeypatch.setenv("KAKAO_REST_API_KEY", "test-key")
    monkeypatch.setattr(
        "app.api.routes.fetch_route", lambda *args, **kwargs: FAKE_KAKAO_RESPONSE
    )

    session_factory = make_test_session_factory()
    seed(session_factory)
    app.dependency_overrides[get_session] = override_get_session_factory(session_factory)

    client = TestClient(app)
    try:
        small_radius_response = client.get(
            "/api/route-restaurants",
            params={"origin": "37.5,127.0", "destination": "37.6,127.1", "radius_km": 1.0},
        )
        large_radius_response = client.get(
            "/api/route-restaurants",
            params={"origin": "37.5,127.0", "destination": "37.6,127.1", "radius_km": 3.0},
        )
    finally:
        app.dependency_overrides.clear()

    assert small_radius_response.status_code == 200
    assert large_radius_response.status_code == 200

    small_names = [r["name"] for r in small_radius_response.json()["restaurants"]]
    large_names = [r["name"] for r in large_radius_response.json()["restaurants"]]

    assert "Medium Restaurant" not in small_names
    assert "Medium Restaurant" in large_names


def test_get_route_restaurants_returns_422_when_radius_km_exceeds_max(monkeypatch):
    monkeypatch.setenv("KAKAO_REST_API_KEY", "test-key")

    client = TestClient(app)
    response = client.get(
        "/api/route-restaurants",
        params={"origin": "37.5,127.0", "destination": "37.6,127.1", "radius_km": 51},
    )

    assert response.status_code == 422


def test_get_route_restaurants_returns_400_for_malformed_origin(monkeypatch):
    monkeypatch.setenv("KAKAO_REST_API_KEY", "test-key")

    client = TestClient(app)
    response = client.get(
        "/api/route-restaurants",
        params={"origin": "not-a-coordinate", "destination": "37.6,127.1"},
    )

    assert response.status_code == 400


def test_get_route_restaurants_returns_500_when_kakao_api_key_missing(monkeypatch):
    monkeypatch.delenv("KAKAO_REST_API_KEY", raising=False)

    client = TestClient(app)
    response = client.get(
        "/api/route-restaurants",
        params={"origin": "37.5,127.0", "destination": "37.6,127.1"},
    )

    assert response.status_code == 500


def test_get_route_restaurants_returns_502_when_kakao_api_fails(monkeypatch):
    monkeypatch.setenv("KAKAO_REST_API_KEY", "test-key")

    def raise_error(*args, **kwargs):
        from app.kakao.directions import KakaoDirectionsError

        raise KakaoDirectionsError("boom")

    monkeypatch.setattr("app.api.routes.fetch_route", raise_error)

    client = TestClient(app)
    response = client.get(
        "/api/route-restaurants",
        params={"origin": "37.5,127.0", "destination": "37.6,127.1"},
    )

    assert response.status_code == 502


def test_get_route_restaurants_returns_422_when_kakao_cannot_find_road_near_point(monkeypatch):
    monkeypatch.setenv("KAKAO_REST_API_KEY", "test-key")

    def raise_error(*args, **kwargs):
        from app.kakao.directions import KakaoRouteError

        raise KakaoRouteError(102, "시작 지점 주변의 도로를 탐색할 수 없음")

    monkeypatch.setattr("app.api.routes.fetch_route", raise_error)

    client = TestClient(app)
    response = client.get(
        "/api/route-restaurants",
        params={"origin": "37.5,127.0", "destination": "37.6,127.1"},
    )

    assert response.status_code == 422
    detail = response.json()["detail"]
    assert "다른 장소를 선택" in detail
    assert "시작 지점 주변의 도로를 탐색할 수 없음" in detail


def test_get_route_restaurants_returns_422_with_kakao_reason_for_any_nonzero_result_code(monkeypatch):
    # 카카오가 응답은 했지만 result_code != 0 — 진입 불가·거리 제한 등 어떤 사유든 재시도가 아니라 장소 변경 안내.
    monkeypatch.setenv("KAKAO_REST_API_KEY", "test-key")
    monkeypatch.setattr(
        "app.api.routes.fetch_route",
        lambda *args, **kwargs: {"routes": [{"result_code": 302, "result_msg": "도착 지점 주변의 도로에 자동차 진입 불가"}]},
    )

    client = TestClient(app)
    response = client.get(
        "/api/route-restaurants",
        params={"origin": "37.5,127.0", "destination": "37.6,127.1"},
    )

    assert response.status_code == 422
    assert "도착 지점 주변의 도로에 자동차 진입 불가" in response.json()["detail"]


# 카카오맵 도보 경로 응답(test_kakao_routing.py의 FAKE_WALK_RESPONSE와 같은 구조). 자동차 테스트와 같은 직선 경로.
FAKE_WALK_RESPONSE = {
    "status": "OK",
    "route": {
        "properties": {"totalDistance": 15000, "totalTime": 12000},
        "legs": [
            {
                "steps": [
                    {
                        "properties": {"distance": 15000, "time": 12000},
                        "path": {"points": [[127.0, 37.5], [127.05, 37.55], [127.1, 37.6]]},
                    }
                ]
            }
        ],
    },
}


def _get_with_seeded_db(params):
    session_factory = make_test_session_factory()
    seed(session_factory)
    app.dependency_overrides[get_session] = override_get_session_factory(session_factory)
    try:
        return TestClient(app).get("/api/route-restaurants", params=params)
    finally:
        app.dependency_overrides.clear()


def test_walk_mode_uses_kakao_map_routing_with_a_walking_radius(monkeypatch):
    monkeypatch.setenv("KAKAO_REST_API_KEY", "test-key")
    calls = []

    def fake_routing(mode, *args, **kwargs):
        calls.append(mode)
        return FAKE_WALK_RESPONSE

    def unexpected(*args, **kwargs):
        pytest.fail("walk mode must not call the car directions API")

    monkeypatch.setattr("app.api.routes.fetch_routing", fake_routing)
    monkeypatch.setattr("app.api.routes.fetch_route", unexpected)

    response = _get_with_seeded_db({"origin": "37.5,127.0", "destination": "37.6,127.1", "mode": "walk"})

    assert response.status_code == 200
    body = response.json()
    assert calls == ["walk"]
    assert body["mode"] == "walk"
    assert body["radius_km"] == 0.5
    assert body["route"]["total_duration_sec"] == 12000
    assert body["adjustments"] == {"origin": None, "destination": None}
    names = [r["name"] for r in body["restaurants"]]
    # Medium(경로에서 ~1.5km)은 자동차 기본 반경 2km에는 들지만 도보 500m에는 안 든다.
    assert "Near Restaurant" in names
    assert "Medium Restaurant" not in names


def test_bicycle_mode_defaults_to_one_km_and_explicit_radius_still_wins(monkeypatch):
    monkeypatch.setenv("KAKAO_REST_API_KEY", "test-key")
    monkeypatch.setattr("app.api.routes.fetch_routing", lambda *args, **kwargs: FAKE_WALK_RESPONSE)

    default = _get_with_seeded_db({"origin": "37.5,127.0", "destination": "37.6,127.1", "mode": "bicycle"})
    widened = _get_with_seeded_db({"origin": "37.5,127.0", "destination": "37.6,127.1", "mode": "bicycle", "radius_km": 3})

    assert default.json()["radius_km"] == 1.0
    assert widened.json()["radius_km"] == 3
    assert "Medium Restaurant" in [r["name"] for r in widened.json()["restaurants"]]


def test_car_mode_is_the_default_and_reports_its_radius(monkeypatch):
    monkeypatch.setenv("KAKAO_REST_API_KEY", "test-key")
    monkeypatch.setattr("app.api.routes.fetch_route", lambda *args, **kwargs: FAKE_KAKAO_RESPONSE)

    response = _get_with_seeded_db({"origin": "37.5,127.0", "destination": "37.6,127.1"})

    assert response.json()["mode"] == "car"
    assert response.json()["radius_km"] == 2.0


def test_walk_too_far_away_suggests_switching_to_car(monkeypatch):
    monkeypatch.setenv("KAKAO_REST_API_KEY", "test-key")
    monkeypatch.setattr("app.api.routes.fetch_routing", lambda *args, **kwargs: {"status": "TOO_FAR_AWAY"})

    response = TestClient(app).get(
        "/api/route-restaurants", params={"origin": "37.55,126.97", "destination": "37.76,128.90", "mode": "walk"}
    )

    assert response.status_code == 422
    assert response.json()["detail"] == "도보로 가기엔 너무 먼 거리예요. 자동차로 검색해보세요"


def test_walk_route_failure_names_the_mode_and_reason(monkeypatch):
    monkeypatch.setenv("KAKAO_REST_API_KEY", "test-key")
    monkeypatch.setattr("app.api.routes.fetch_routing", lambda *args, **kwargs: {"status": "END_LINK_NOT_FOUND"})

    response = TestClient(app).get(
        "/api/route-restaurants", params={"origin": "37.5,127.0", "destination": "37.6,127.1", "mode": "walk"}
    )

    assert response.status_code == 422
    detail = response.json()["detail"]
    assert "도보 경로를 찾을 수 없어요" in detail
    assert "도착지 주변에서 길을 찾을 수 없어요" in detail


def test_unknown_mode_is_rejected(monkeypatch):
    monkeypatch.setenv("KAKAO_REST_API_KEY", "test-key")
    response = TestClient(app).get(
        "/api/route-restaurants", params={"origin": "37.5,127.0", "destination": "37.6,127.1", "mode": "train"}
    )
    assert response.status_code == 422
