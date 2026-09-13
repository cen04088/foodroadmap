from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool

from app.api.main import app
from app.api.routes import get_session
from app.db import init_db, make_session_factory
from app.models import Broadcast, MenuItem, Restaurant

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
