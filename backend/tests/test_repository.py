from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool

from app.db import init_db, make_session_factory
from app.models import Broadcast, Restaurant
from app.repository import query_candidate_restaurants


def make_session_factory_in_memory():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    init_db(engine)
    return make_session_factory(engine)


def seed(session):
    ttoganjib = Broadcast(id="ttoganjib", name="또간집")
    session.add(ttoganjib)

    inside = Restaurant(
        id="inside", name="Inside", latitude=37.55, longitude=127.05, category="한식"
    )
    inside.broadcasts.append(ttoganjib)

    outside = Restaurant(id="outside", name="Outside", latitude=38.5, longitude=128.5, category="한식")
    no_coords = Restaurant(id="no-coords", name="NoCoords", latitude=None, longitude=None)
    wrong_category = Restaurant(
        id="wrong-category", name="WrongCategory", latitude=37.55, longitude=127.05, category="양식"
    )

    session.add_all([inside, outside, no_coords, wrong_category])
    session.commit()


def test_query_candidate_restaurants_filters_by_bounding_box():
    session_factory = make_session_factory_in_memory()
    with session_factory() as session:
        seed(session)

        results = query_candidate_restaurants(session, 37.0, 38.0, 126.5, 127.5)

        ids = {r.id for r in results}
        assert "inside" in ids
        assert "outside" not in ids
        assert "no-coords" not in ids


def test_query_candidate_restaurants_filters_by_category():
    session_factory = make_session_factory_in_memory()
    with session_factory() as session:
        seed(session)

        results = query_candidate_restaurants(session, 37.0, 38.0, 126.5, 127.5, category="한식")

        ids = {r.id for r in results}
        assert "inside" in ids
        assert "wrong-category" not in ids


def test_query_candidate_restaurants_filters_by_broadcast_slug():
    session_factory = make_session_factory_in_memory()
    with session_factory() as session:
        seed(session)

        results = query_candidate_restaurants(
            session, 37.0, 38.0, 126.5, 127.5, broadcast_slug="ttoganjib"
        )

        ids = {r.id for r in results}
        assert ids == {"inside"}


def test_query_candidate_restaurants_filters_by_broadcast_display_name():
    session_factory = make_session_factory_in_memory()
    with session_factory() as session:
        seed(session)

        by_name = query_candidate_restaurants(
            session, 37.0, 38.0, 126.5, 127.5, broadcast_slug="또간집"
        )
        by_slug = query_candidate_restaurants(
            session, 37.0, 38.0, 126.5, 127.5, broadcast_slug="ttoganjib"
        )

        assert {r.id for r in by_name} == {"inside"}
        assert {r.id for r in by_name} == {r.id for r in by_slug}
