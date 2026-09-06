from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool

from app.api.main import app
from app.api.routes import get_session
from app.db import init_db, make_session_factory
from app.models import Broadcast, Restaurant


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


def test_get_broadcasts_returns_counts_of_restaurants_with_coordinates():
    session_factory = make_test_session_factory()
    with session_factory() as session:
        ttoganjib = Broadcast(id="ttoganjib", name="또간집")
        session.add(ttoganjib)

        with_coords = Restaurant(id="with-coords", name="WithCoords", latitude=37.5, longitude=127.0)
        with_coords.broadcasts.append(ttoganjib)
        without_coords = Restaurant(id="without-coords", name="WithoutCoords", latitude=None, longitude=None)
        without_coords.broadcasts.append(ttoganjib)

        session.add_all([with_coords, without_coords])
        session.commit()

    app.dependency_overrides[get_session] = override_get_session_factory(session_factory)
    client = TestClient(app)
    try:
        response = client.get("/api/broadcasts")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    body = response.json()
    by_slug = {b["slug"]: b for b in body["broadcasts"]}
    assert by_slug["ttoganjib"] == {"slug": "ttoganjib", "name": "또간집", "count": 1}


def test_get_broadcasts_sets_cache_control_header():
    session_factory = make_test_session_factory()
    app.dependency_overrides[get_session] = override_get_session_factory(session_factory)
    client = TestClient(app)
    try:
        response = client.get("/api/broadcasts")
    finally:
        app.dependency_overrides.clear()

    assert response.headers["cache-control"] == "public, max-age=300"
