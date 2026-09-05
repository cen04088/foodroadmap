from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool

from app.db import init_db, make_session_factory
from app.models import Broadcast, Restaurant
from app.repository import list_all_restaurants, list_broadcasts_with_counts, query_candidate_restaurants


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


def test_list_all_restaurants_returns_every_restaurant_with_coordinates_regardless_of_location():
    session_factory = make_session_factory_in_memory()
    with session_factory() as session:
        seed(session)

        results = list_all_restaurants(session)

        ids = {r.id for r in results}
        assert "inside" in ids
        assert "outside" in ids
        assert "wrong-category" in ids
        assert "no-coords" not in ids


def test_list_all_restaurants_filters_by_category():
    session_factory = make_session_factory_in_memory()
    with session_factory() as session:
        seed(session)

        results = list_all_restaurants(session, category="한식")

        ids = {r.id for r in results}
        assert "inside" in ids
        assert "outside" in ids
        assert "wrong-category" not in ids


def test_list_all_restaurants_filters_by_broadcast_slug_or_name():
    session_factory = make_session_factory_in_memory()
    with session_factory() as session:
        seed(session)

        by_slug = list_all_restaurants(session, broadcast_slug="ttoganjib")
        by_name = list_all_restaurants(session, broadcast_slug="또간집")

        assert {r.id for r in by_slug} == {"inside"}
        assert {r.id for r in by_name} == {"inside"}


def test_list_broadcasts_with_counts_counts_only_restaurants_with_coordinates():
    session_factory = make_session_factory_in_memory()
    with session_factory() as session:
        ttoganjib = Broadcast(id="ttoganjib", name="또간집")
        empty_show = Broadcast(id="empty", name="텅빈방송")
        session.add_all([ttoganjib, empty_show])

        with_coords = Restaurant(id="with-coords", name="WithCoords", latitude=37.5, longitude=127.0)
        with_coords.broadcasts.append(ttoganjib)

        without_coords = Restaurant(id="without-coords", name="WithoutCoords", latitude=None, longitude=None)
        without_coords.broadcasts.append(ttoganjib)

        session.add_all([with_coords, without_coords])
        session.commit()

        results = list_broadcasts_with_counts(session)

        by_slug = {r["slug"]: r for r in results}
        assert by_slug["ttoganjib"]["name"] == "또간집"
        assert by_slug["ttoganjib"]["count"] == 1
        assert by_slug["empty"]["name"] == "텅빈방송"
        assert by_slug["empty"]["count"] == 0
