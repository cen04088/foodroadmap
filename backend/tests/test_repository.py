from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool

from app.db import init_db, make_session_factory
from app.models import Broadcast, MenuItem, Restaurant
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


def seed_priced(session):
    """기준 가격 = 가격이 있는 메뉴를 (대표 우선, position 순)으로 세운 첫 번째."""
    # 대표 표시가 있으면 position을 무시하고 대표가 먼저다.
    representative_later = Restaurant(id="rep-later", name="RepLater", latitude=37.55, longitude=127.05)
    representative_later.menu_items = [
        MenuItem(name="공기밥", price_won=1000, is_representative=False, position=0),
        MenuItem(name="한우 코스", price_won=25000, is_representative=True, position=1),
    ]

    # 대표 표시가 없으면 목록의 첫 메뉴 — 뒤에 있는 공기밥 1,000원에 끌려가지 않는다.
    no_representative = Restaurant(id="no-rep", name="NoRep", latitude=37.55, longitude=127.05)
    no_representative.menu_items = [
        MenuItem(name="파스타", price_won=15000, is_representative=False, position=0),
        MenuItem(name="음료", price_won=3000, is_representative=False, position=1),
    ]

    # 첫 메뉴가 "시가"처럼 가격이 없으면 가격이 적힌 것 중 첫 번째로 넘어간다.
    unpriced_first = Restaurant(id="unpriced-first", name="UnpricedFirst", latitude=37.55, longitude=127.05)
    unpriced_first.menu_items = [
        MenuItem(name="오마카세 (시가)", price_won=None, is_representative=False, position=0),
        MenuItem(name="점심 정식", price_won=18000, is_representative=False, position=1),
    ]

    no_price = Restaurant(id="no-price", name="NoPrice", latitude=37.55, longitude=127.05)
    no_price.menu_items = [MenuItem(name="시가", price_won=None, is_representative=True, position=0)]

    # 크롤링 시점에 메뉴가 아예 안 잡힌 가게.
    no_menu = Restaurant(id="no-menu", name="NoMenu", latitude=37.55, longitude=127.05)

    session.add_all([representative_later, no_representative, unpriced_first, no_price, no_menu])
    session.commit()


def test_price_filter_prefers_representative_menu_over_list_order():
    session_factory = make_session_factory_in_memory()
    with session_factory() as session:
        seed_priced(session)

        ids = {r.id for r in list_all_restaurants(session, min_price=20000, max_price=30000)}

        assert ids == {"rep-later"}, "대표 메뉴는 목록에서 뒤에 있어도 기준이 된다"
        assert "rep-later" not in {
            r.id for r in list_all_restaurants(session, max_price=10000)
        }, "공기밥 1,000원이 있는 가게가 1만원 이하로 잡히면 안 된다"


def test_price_filter_uses_first_listed_menu_when_no_representative():
    session_factory = make_session_factory_in_memory()
    with session_factory() as session:
        seed_priced(session)

        ids = {r.id for r in list_all_restaurants(session, min_price=10000, max_price=20000)}

        assert "no-rep" in ids, "대표 표시가 없으면 목록 첫 메뉴(15,000원)를 기준으로 삼는다"
        assert "no-rep" not in {
            r.id for r in list_all_restaurants(session, max_price=10000)
        }, "뒤에 있는 음료 3,000원에 끌려가면 안 된다"


def test_price_filter_skips_menu_items_without_a_price():
    session_factory = make_session_factory_in_memory()
    with session_factory() as session:
        seed_priced(session)

        ids = {r.id for r in list_all_restaurants(session, min_price=10000, max_price=20000)}

        assert "unpriced-first" in ids, "첫 메뉴가 시가면 가격이 적힌 다음 메뉴로 넘어간다"


def test_price_filter_excludes_restaurants_whose_price_is_unknown():
    session_factory = make_session_factory_in_memory()
    with session_factory() as session:
        seed_priced(session)

        # 구간을 안 고르면 가격을 모르는 가게도 그대로 보인다.
        assert {r.id for r in list_all_restaurants(session)} >= {"no-price", "no-menu"}

        # 구간을 고르는 순간, 어떤 구간이든 제외된다 — 모른다고 해서 범위 안에 있다고
        # 말할 수는 없다.
        wide = {r.id for r in list_all_restaurants(session, max_price=1000000)}
        assert "no-price" not in wide
        assert "no-menu" not in wide


def test_price_filter_applies_to_route_candidates_too():
    session_factory = make_session_factory_in_memory()
    with session_factory() as session:
        seed_priced(session)

        results = query_candidate_restaurants(
            session, 37.0, 38.0, 126.5, 127.5, min_price=20000, max_price=30000
        )

        assert {r.id for r in results} == {"rep-later"}
