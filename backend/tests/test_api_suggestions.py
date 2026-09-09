from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool

from app.api.main import app
from app.api.routes import SUGGESTION_RATE_LIMIT, get_session
from app.db import init_db, make_session_factory
from app.models import Suggestion


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


def make_client(session_factory):
    app.dependency_overrides[get_session] = override_get_session_factory(session_factory)
    return TestClient(app)


def teardown_function():
    app.dependency_overrides.clear()


def test_post_suggestion_stores_it_and_returns_the_id():
    session_factory = make_test_session_factory()
    client = make_client(session_factory)

    response = client.post(
        "/api/suggestions",
        json={"kind": "broadcast", "body": "성시경의 먹을텐데 추가해주세요", "contact": "me@example.com"},
    )

    assert response.status_code == 201
    assert response.json()["id"] > 0

    with session_factory() as session:
        stored = session.query(Suggestion).one()
        assert stored.kind == "broadcast"
        assert stored.body == "성시경의 먹을텐데 추가해주세요"
        assert stored.contact == "me@example.com"


def test_post_suggestion_accepts_a_missing_contact():
    session_factory = make_test_session_factory()
    client = make_client(session_factory)

    response = client.post("/api/suggestions", json={"kind": "improvement", "body": "지도가 느려요"})

    assert response.status_code == 201
    with session_factory() as session:
        assert session.query(Suggestion).one().contact is None


def test_post_suggestion_treats_a_blank_contact_as_missing():
    session_factory = make_test_session_factory()
    client = make_client(session_factory)

    client.post("/api/suggestions", json={"kind": "improvement", "body": "좋아요", "contact": "   "})

    with session_factory() as session:
        assert session.query(Suggestion).one().contact is None


def test_post_suggestion_rejects_a_blank_body():
    client = make_client(make_test_session_factory())

    # min_length=1은 통과하지만 내용이 없는 요청 — 별도 검증이 필요하다.
    response = client.post("/api/suggestions", json={"kind": "improvement", "body": "   "})

    assert response.status_code == 422


def test_post_suggestion_rejects_an_unknown_kind():
    client = make_client(make_test_session_factory())

    response = client.post("/api/suggestions", json={"kind": "spam", "body": "내용"})

    assert response.status_code == 422


def test_post_suggestion_rejects_a_body_over_the_length_cap():
    client = make_client(make_test_session_factory())

    response = client.post("/api/suggestions", json={"kind": "improvement", "body": "가" * 2001})

    assert response.status_code == 422


def test_post_suggestion_rate_limits_one_ip():
    session_factory = make_test_session_factory()
    client = make_client(session_factory)

    for i in range(SUGGESTION_RATE_LIMIT):
        assert (
            client.post(
                "/api/suggestions",
                json={"kind": "improvement", "body": f"의견 {i}"},
                headers={"X-Forwarded-For": "203.0.113.9"},
            ).status_code
            == 201
        )

    blocked = client.post(
        "/api/suggestions",
        json={"kind": "improvement", "body": "한 건 더"},
        headers={"X-Forwarded-For": "203.0.113.9"},
    )

    assert blocked.status_code == 429


def test_rate_limit_is_scoped_to_the_ip_and_to_the_window():
    session_factory = make_test_session_factory()
    client = make_client(session_factory)

    # 창을 넘긴 오래된 기록은 한도에 안 들어간다.
    with session_factory() as session:
        old = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(hours=2)
        for i in range(SUGGESTION_RATE_LIMIT):
            session.add(
                Suggestion(
                    kind="improvement", body=f"옛 의견 {i}", client_ip="203.0.113.9", created_at=old
                )
            )
        session.commit()

    assert (
        client.post(
            "/api/suggestions",
            json={"kind": "improvement", "body": "새 의견"},
            headers={"X-Forwarded-For": "203.0.113.9"},
        ).status_code
        == 201
    )

    # 다른 IP는 남의 한도에 영향받지 않는다.
    assert (
        client.post(
            "/api/suggestions",
            json={"kind": "improvement", "body": "다른 사람"},
            headers={"X-Forwarded-For": "198.51.100.4"},
        ).status_code
        == 201
    )


def test_get_suggestions_requires_the_admin_token(monkeypatch):
    monkeypatch.setenv("ADMIN_TOKEN", "secret-token")
    session_factory = make_test_session_factory()
    client = make_client(session_factory)
    client.post("/api/suggestions", json={"kind": "improvement", "body": "비공개 의견"})

    assert client.get("/api/suggestions").status_code == 401
    assert client.get("/api/suggestions", headers={"X-Admin-Token": "wrong"}).status_code == 401

    ok = client.get("/api/suggestions", headers={"X-Admin-Token": "secret-token"})
    assert ok.status_code == 200
    assert [s["body"] for s in ok.json()["suggestions"]] == ["비공개 의견"]


def test_get_suggestions_refuses_to_serve_when_no_token_is_configured(monkeypatch):
    # 토큰을 안 걸어두면 열어주는 게 아니라 닫혀 있어야 한다.
    monkeypatch.delenv("ADMIN_TOKEN", raising=False)
    client = make_client(make_test_session_factory())

    assert client.get("/api/suggestions").status_code == 503


def test_get_suggestions_returns_newest_first(monkeypatch):
    monkeypatch.setenv("ADMIN_TOKEN", "secret-token")
    session_factory = make_test_session_factory()
    client = make_client(session_factory)

    with session_factory() as session:
        base = datetime(2026, 9, 1, 12, 0, 0)
        session.add(Suggestion(kind="improvement", body="먼저", created_at=base))
        session.add(Suggestion(kind="broadcast", body="나중", created_at=base + timedelta(hours=1)))
        session.commit()

    body = client.get("/api/suggestions", headers={"X-Admin-Token": "secret-token"}).json()

    assert [s["body"] for s in body["suggestions"]] == ["나중", "먼저"]
