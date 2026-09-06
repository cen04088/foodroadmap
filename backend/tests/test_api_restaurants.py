from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool

from app.api.main import app
from app.api.routes import get_session
from app.db import init_db, make_session_factory
from app.models import Broadcast, MenuItem, Restaurant


def make_test_session_factory():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    init_db(engine)
    return make_session_factory(engine)


def override_get_session_factory(session_factory):
    def _override():
        with session_factory() as session:
            yield session

    return _override


def test_get_restaurants_returns_all_restaurants_with_coordinates():
    session_factory = make_test_session_factory()
    with session_factory() as session:
        ttoganjib = Broadcast(id="ttoganjib", name="또간집")
        session.add(ttoganjib)

        with_coords = Restaurant(
            id="with-coords",
            name="WithCoords",
            latitude=37.5,
            longitude=127.0,
            category="한식",
            youtube_url="https://www.youtube.com/watch?v=abc",
        )
        with_coords.broadcasts.append(ttoganjib)
        without_coords = Restaurant(id="without-coords", name="WithoutCoords", latitude=None, longitude=None)

        session.add_all([with_coords, without_coords])
        session.commit()

    app.dependency_overrides[get_session] = override_get_session_factory(session_factory)
    client = TestClient(app)
    try:
        response = client.get("/api/restaurants")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    body = response.json()
    ids = {r["id"] for r in body["restaurants"]}
    assert ids == {"with-coords"}

    result = body["restaurants"][0]
    assert result["name"] == "WithCoords"
    assert result["category"] == "한식"
    assert result["youtube_url"] == "https://www.youtube.com/watch?v=abc"
    assert result["broadcasts"] == ["또간집"]
    assert result["menu"] == []
    assert "distance_from_route_km" not in result
    assert "cumulative_time_sec" not in result


def test_get_restaurants_prioritizes_representative_menu_items_up_to_three():
    session_factory = make_test_session_factory()
    with session_factory() as session:
        restaurant = Restaurant(id="r1", name="Restaurant", latitude=37.5, longitude=127.0)
        restaurant.menu_items = [
            MenuItem(name="일반메뉴1", price_won=5000, is_representative=False, position=0),
            MenuItem(name="대표메뉴1", price_won=9000, is_representative=True, position=1),
            MenuItem(name="일반메뉴2", price_won=6000, is_representative=False, position=2),
            MenuItem(name="대표메뉴2", price_won=10000, is_representative=True, position=3),
            MenuItem(name="일반메뉴3", price_won=7000, is_representative=False, position=4),
        ]
        session.add(restaurant)
        session.commit()

    app.dependency_overrides[get_session] = override_get_session_factory(session_factory)
    client = TestClient(app)
    try:
        response = client.get("/api/restaurants")
    finally:
        app.dependency_overrides.clear()

    menu = response.json()["restaurants"][0]["menu"]
    assert len(menu) == 3
    # 대표 메뉴 두 개가 먼저, 그 다음 일반 메뉴가 순서대로 하나 채워진다.
    assert [m["name"] for m in menu] == ["대표메뉴1", "대표메뉴2", "일반메뉴1"]
    assert menu[0] == {"name": "대표메뉴1", "price_won": 9000, "is_representative": True}
    assert menu[2] == {"name": "일반메뉴1", "price_won": 5000, "is_representative": False}


def test_get_restaurants_filters_by_broadcast_query_param():
    session_factory = make_test_session_factory()
    with session_factory() as session:
        ttoganjib = Broadcast(id="ttoganjib", name="또간집")
        other = Broadcast(id="other", name="다른방송")
        session.add_all([ttoganjib, other])

        matching = Restaurant(id="matching", name="Matching", latitude=37.5, longitude=127.0)
        matching.broadcasts.append(ttoganjib)
        not_matching = Restaurant(id="not-matching", name="NotMatching", latitude=37.6, longitude=127.1)
        not_matching.broadcasts.append(other)

        session.add_all([matching, not_matching])
        session.commit()

    app.dependency_overrides[get_session] = override_get_session_factory(session_factory)
    client = TestClient(app)
    try:
        response = client.get("/api/restaurants", params={"broadcast": "또간집"})
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    ids = {r["id"] for r in response.json()["restaurants"]}
    assert ids == {"matching"}


def test_get_restaurants_filters_by_category_query_param():
    session_factory = make_test_session_factory()
    with session_factory() as session:
        korean = Restaurant(id="korean", name="Korean", latitude=37.5, longitude=127.0, category="한식")
        japanese = Restaurant(id="japanese", name="Japanese", latitude=37.6, longitude=127.1, category="일식")
        session.add_all([korean, japanese])
        session.commit()

    app.dependency_overrides[get_session] = override_get_session_factory(session_factory)
    client = TestClient(app)
    try:
        response = client.get("/api/restaurants", params={"category": "한식"})
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    ids = {r["id"] for r in response.json()["restaurants"]}
    assert ids == {"korean"}


def test_get_restaurants_filters_by_bounding_box_query_params():
    session_factory = make_test_session_factory()
    with session_factory() as session:
        inside = Restaurant(id="inside", name="Inside", latitude=37.55, longitude=127.05)
        outside = Restaurant(id="outside", name="Outside", latitude=38.5, longitude=128.5)
        session.add_all([inside, outside])
        session.commit()

    app.dependency_overrides[get_session] = override_get_session_factory(session_factory)
    client = TestClient(app)
    try:
        response = client.get(
            "/api/restaurants",
            params={"min_lat": 37.0, "max_lat": 38.0, "min_lng": 126.5, "max_lng": 127.5},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    ids = {r["id"] for r in response.json()["restaurants"]}
    assert ids == {"inside"}


def test_get_restaurants_ignores_bbox_when_only_some_params_given():
    session_factory = make_test_session_factory()
    with session_factory() as session:
        restaurant = Restaurant(id="somewhere", name="Somewhere", latitude=37.55, longitude=127.05)
        session.add(restaurant)
        session.commit()

    app.dependency_overrides[get_session] = override_get_session_factory(session_factory)
    client = TestClient(app)
    try:
        response = client.get("/api/restaurants", params={"min_lat": 37.0})
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    ids = {r["id"] for r in response.json()["restaurants"]}
    assert ids == {"somewhere"}


def test_get_restaurants_sets_cache_control_header():
    session_factory = make_test_session_factory()
    app.dependency_overrides[get_session] = override_get_session_factory(session_factory)
    client = TestClient(app)
    try:
        response = client.get("/api/restaurants")
    finally:
        app.dependency_overrides.clear()

    assert response.headers["cache-control"] == "public, max-age=300"
