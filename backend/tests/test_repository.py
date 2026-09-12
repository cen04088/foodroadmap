from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool

from app.db import init_db, make_session_factory
from app.models import Broadcast, Restaurant
from app.repository import (
    list_all_restaurants,
    list_broadcasts_with_counts,
    query_candidate_restaurants,
    visible_broadcast_names,
)


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


def test_list_all_restaurants_filters_by_bbox():
    session_factory = make_session_factory_in_memory()
    with session_factory() as session:
        seed(session)

        results = list_all_restaurants(session, bbox=(37.0, 38.0, 126.5, 127.5))

        ids = {r.id for r in results}
        assert "inside" in ids
        assert "wrong-category" in ids
        assert "outside" not in ids
        assert "no-coords" not in ids


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


def seed_with_hidden_broadcast(session):
    ttoganjib = Broadcast(id="ttoganjib", name="또간집")
    hidden = Broadcast(id="kimyoungchul", name="동네한바퀴")
    session.add_all([ttoganjib, hidden])

    only_hidden = Restaurant(id="only-hidden", name="OnlyHidden", latitude=37.55, longitude=127.05)
    only_hidden.broadcasts.append(hidden)
    shared = Restaurant(id="shared", name="Shared", latitude=37.55, longitude=127.05)
    shared.broadcasts.extend([hidden, ttoganjib])
    visible = Restaurant(id="visible", name="Visible", latitude=37.55, longitude=127.05)
    visible.broadcasts.append(ttoganjib)
    no_broadcast = Restaurant(id="no-broadcast", name="NoBroadcast", latitude=37.55, longitude=127.05)

    session.add_all([only_hidden, shared, visible, no_broadcast])
    session.commit()


def test_restaurants_seen_only_on_a_hidden_broadcast_are_dropped():
    session_factory = make_session_factory_in_memory()
    with session_factory() as session:
        seed_with_hidden_broadcast(session)

        all_ids = {r.id for r in list_all_restaurants(session)}
        candidate_ids = {r.id for r in query_candidate_restaurants(session, 37.0, 38.0, 126.5, 127.5)}

        for ids in (all_ids, candidate_ids):
            assert "only-hidden" not in ids
            # 다른 방송에도 나온 식당과 방송 태그가 없는 식당은 그대로 남는다.
            assert {"shared", "visible", "no-broadcast"} <= ids


def test_hidden_broadcast_is_stripped_from_visible_names():
    session_factory = make_session_factory_in_memory()
    with session_factory() as session:
        seed_with_hidden_broadcast(session)

        shared = next(r for r in list_all_restaurants(session) if r.id == "shared")
        assert visible_broadcast_names(shared) == ["또간집"]


def test_filtering_by_a_hidden_broadcast_returns_nothing():
    session_factory = make_session_factory_in_memory()
    with session_factory() as session:
        seed_with_hidden_broadcast(session)

        assert list_all_restaurants(session, broadcast_slug="동네한바퀴") == []
        assert list_all_restaurants(session, broadcast_slug="kimyoungchul") == []
        assert query_candidate_restaurants(session, 37.0, 38.0, 126.5, 127.5, broadcast_slug="동네한바퀴") == []
        # 다른 방송 필터는 여전히 동작하고, 숨긴 방송과 공유된 식당도 포함한다.
        assert {r.id for r in list_all_restaurants(session, broadcast_slug="또간집")} == {"shared", "visible"}


def test_list_broadcasts_with_counts_omits_hidden_broadcast():
    session_factory = make_session_factory_in_memory()
    with session_factory() as session:
        seed_with_hidden_broadcast(session)

        by_name = {b["name"]: b["count"] for b in list_broadcasts_with_counts(session)}
        assert "동네한바퀴" not in by_name
        assert by_name["또간집"] == 2
