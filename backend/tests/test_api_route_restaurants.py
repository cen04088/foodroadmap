from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool

from app.api.main import app
from app.api.routes import get_session
from app.db import init_db, make_session_factory
from app.models import Broadcast, Restaurant

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
            id="near", name="Near Restaurant", latitude=37.55, longitude=127.05, category="한식"
        )
        near.broadcasts.append(ttoganjib)

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
