from datetime import timedelta

import pytest
from fastapi.testclient import TestClient

from app.api.main import app
from app.api.routes import get_session
from app.meal_context import CONTEXT_REQUEST_LIMIT, save_context, utcnow
from app.models import MealRouteContext
from tests.test_api_route_restaurants import make_test_session_factory, override_get_session_factory, seed, FAKE_KAKAO_RESPONSE
from tests.test_meal_planner import preferences, restaurant


@pytest.fixture
def setup(monkeypatch):
    factory = make_test_session_factory()
    with factory() as session:
        token = save_context(session, [restaurant()])
    app.dependency_overrides[get_session] = override_get_session_factory(factory)
    monkeypatch.setattr("app.api.routes.interpret_preferences", lambda message, previous, candidates: preferences(max_price_won=20000))
    try:
        yield TestClient(app), factory, token
    finally:
        app.dependency_overrides.pop(get_session, None)


def test_api_uses_server_context_and_returns_evidence(setup):
    client, _, token = setup
    response = client.post("/api/meal-recommendations", json={"route_context_id": token, "message": "2만원 이하"})
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    assert response.json()["recommendations"][0]["restaurant_id"] == "a"


def test_client_cannot_inject_restaurant_facts(setup):
    client, _, token = setup
    response = client.post("/api/meal-recommendations", json={"route_context_id": token, "message": "한식", "restaurants": [restaurant("forged")]})
    assert response.status_code == 422


@pytest.mark.parametrize("message", ["", "   ", "x" * 1001])
def test_invalid_message_rejected(setup, message):
    client, _, token = setup
    assert client.post("/api/meal-recommendations", json={"route_context_id": token, "message": message}).status_code == 422


def test_expired_context_requires_new_route(setup):
    client, factory, token = setup
    with factory() as session:
        session.get(MealRouteContext, token).expires_at = utcnow() - timedelta(seconds=1)
        session.commit()
    assert client.post("/api/meal-recommendations", json={"route_context_id": token, "message": "한식"}).status_code == 410
    assert client.post("/api/meal-recommendations", json={"route_context_id": "0" * 48, "message": "한식"}).status_code == 410


def test_request_limit_is_enforced(setup):
    client, factory, token = setup
    with factory() as session:
        session.get(MealRouteContext, token).request_count = CONTEXT_REQUEST_LIMIT
        session.commit()
    assert client.post("/api/meal-recommendations", json={"route_context_id": token, "message": "한식"}).status_code == 429


def test_route_search_creates_usable_context(setup, monkeypatch):
    client, factory, _ = setup
    seed(factory)
    monkeypatch.setenv("KAKAO_REST_API_KEY", "test-key")
    monkeypatch.setattr("app.api.routes.fetch_route", lambda *args: FAKE_KAKAO_RESPONSE)
    route = client.get("/api/route-restaurants", params={"origin": "37.5,127.0", "destination": "37.6,127.1"})
    assert route.status_code == 200
    result = client.post("/api/meal-recommendations", json={"route_context_id": route.json()["meal_context_id"], "message": "2만원 이하"})
    assert result.status_code == 200
    assert result.json()["recommendations"][0]["restaurant_id"] == "near"
