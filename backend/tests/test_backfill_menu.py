import time
from unittest.mock import patch

from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool

from app.crawler.backfill_menu import _fetch_with_deadline, backfill_menus, BASE_URL
from app.db import init_db, make_session_factory
from app.models import Restaurant

DETAIL_HTML_WITH_MENU = """
<script type="application/ld+json">
{"@type": "Restaurant", "name": "경양카츠 연남점"}
</script>
<div class="pd-menu">
  <ul>
    <li class="pd-menu__item"><span class="pd-menu__name">안심카츠<b class="pd-menu__tag">대표</b></span><span class="pd-menu__price">16,400원</span></li>
    <li class="pd-menu__item"><span class="pd-menu__name">치즈카츠</span><span class="pd-menu__price">15,000원</span></li>
  </ul>
</div>
"""

DETAIL_HTML_WITHOUT_MENU = """
<script type="application/ld+json">
{"@type": "Restaurant", "name": "두번째식당"}
</script>
"""


def make_test_session_factory():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    init_db(engine)
    return make_session_factory(engine)


def test_backfill_menus_fills_in_missing_menus_and_skips_restaurants_already_set():
    session_factory = make_test_session_factory()

    with session_factory() as session:
        already_has_menu = Restaurant(id="place-3", name="이미채워짐")
        from app.models import MenuItem

        already_has_menu.menu_items = [MenuItem(name="기존메뉴", price_won=1000, is_representative=False, position=0)]
        session.add_all(
            [
                Restaurant(id="place-1", name="경양카츠 연남점"),
                Restaurant(id="place-2", name="두번째식당"),
                already_has_menu,
            ]
        )
        session.commit()

    def fake_fetch(url, **kwargs):
        if url == f"{BASE_URL}/place/place-1":
            return DETAIL_HTML_WITH_MENU
        if url == f"{BASE_URL}/place/place-2":
            return DETAIL_HTML_WITHOUT_MENU
        raise AssertionError(f"unexpected url (place-3 should be skipped entirely): {url}")

    with patch("app.crawler.backfill_menu.fetch_url", side_effect=fake_fetch), patch(
        "app.crawler.backfill_menu.time.sleep"
    ):
        backfill_menus(session_factory=session_factory, progress_file=None)

    with session_factory() as session:
        place1 = session.get(Restaurant, "place-1")
        assert [m.name for m in place1.menu_items] == ["안심카츠", "치즈카츠"]
        assert place1.menu_items[0].is_representative is True
        assert place1.menu_items[0].price_won == 16400

        assert session.get(Restaurant, "place-2").menu_items == []

        place3 = session.get(Restaurant, "place-3")
        assert [m.name for m in place3.menu_items] == ["기존메뉴"]


def test_backfill_menus_skips_restaurant_on_fetch_failure():
    session_factory = make_test_session_factory()

    with session_factory() as session:
        session.add(Restaurant(id="place-1", name="경양카츠 연남점"))
        session.commit()

    def raise_error(*args, **kwargs):
        raise RuntimeError("network error")

    with patch("app.crawler.backfill_menu.fetch_url", side_effect=raise_error), patch(
        "app.crawler.backfill_menu.time.sleep"
    ):
        backfill_menus(session_factory=session_factory, progress_file=None)

    with session_factory() as session:
        assert session.get(Restaurant, "place-1").menu_items == []


def test_backfill_menus_records_all_checked_ids_to_progress_file(tmp_path):
    session_factory = make_test_session_factory()
    progress_file = str(tmp_path / "checked.txt")

    with session_factory() as session:
        session.add_all(
            [
                Restaurant(id="place-1", name="경양카츠 연남점"),
                Restaurant(id="place-2", name="두번째식당"),
            ]
        )
        session.commit()

    def fake_fetch(url, **kwargs):
        if url == f"{BASE_URL}/place/place-1":
            return DETAIL_HTML_WITH_MENU
        return DETAIL_HTML_WITHOUT_MENU

    with patch("app.crawler.backfill_menu.fetch_url", side_effect=fake_fetch), patch(
        "app.crawler.backfill_menu.time.sleep"
    ):
        backfill_menus(session_factory=session_factory, progress_file=progress_file)

    # 메뉴를 찾은 것과 못 찾은 것 둘 다 기록돼서, 다음 배치가 이미 처리한 걸 또 재확인하지 않는다.
    checked_ids = {line.strip() for line in open(progress_file, encoding="utf-8")}
    assert checked_ids == {"place-1", "place-2"}


def test_backfill_menus_advances_past_empty_restaurants_across_batches_via_progress_file(tmp_path):
    session_factory = make_test_session_factory()
    progress_file = str(tmp_path / "checked.txt")

    with session_factory() as session:
        session.add_all(
            [
                Restaurant(id="place-1", name="빈가게1"),
                Restaurant(id="place-2", name="빈가게2"),
                Restaurant(id="place-3", name="경양카츠 연남점"),
            ]
        )
        session.commit()

    def fake_fetch(url, **kwargs):
        if url == f"{BASE_URL}/place/place-3":
            return DETAIL_HTML_WITH_MENU
        return DETAIL_HTML_WITHOUT_MENU

    with patch("app.crawler.backfill_menu.fetch_url", side_effect=fake_fetch), patch(
        "app.crawler.backfill_menu.time.sleep"
    ):
        backfill_menus(session_factory=session_factory, limit=1, progress_file=progress_file)
        backfill_menus(session_factory=session_factory, limit=1, progress_file=progress_file)
        backfill_menus(session_factory=session_factory, limit=1, progress_file=progress_file)

    with session_factory() as session:
        assert session.get(Restaurant, "place-1").menu_items == []
        assert session.get(Restaurant, "place-2").menu_items == []
        place3 = session.get(Restaurant, "place-3")
        assert [m.name for m in place3.menu_items] == ["안심카츠", "치즈카츠"]


def test_backfill_menus_respects_limit():
    session_factory = make_test_session_factory()

    with session_factory() as session:
        session.add_all(
            [
                Restaurant(id="place-1", name="경양카츠 연남점"),
                Restaurant(id="place-2", name="경양카츠 연남점"),
                Restaurant(id="place-3", name="경양카츠 연남점"),
            ]
        )
        session.commit()

    calls = []

    def fake_fetch(url, **kwargs):
        calls.append(url)
        return DETAIL_HTML_WITH_MENU

    with patch("app.crawler.backfill_menu.fetch_url", side_effect=fake_fetch), patch(
        "app.crawler.backfill_menu.time.sleep"
    ):
        backfill_menus(session_factory=session_factory, limit=2, progress_file=None)

    assert len(calls) == 2


def test_backfill_menus_treats_a_hung_fetch_as_a_recoverable_failure():
    session_factory = make_test_session_factory()

    with session_factory() as session:
        session.add_all(
            [
                Restaurant(id="place-1", name="멈춘가게"),
                Restaurant(id="place-2", name="경양카츠 연남점"),
            ]
        )
        session.commit()

    def fake_fetch(url, **kwargs):
        if url == f"{BASE_URL}/place/place-1":
            time.sleep(3600)
        if url == f"{BASE_URL}/place/place-2":
            return DETAIL_HTML_WITH_MENU
        raise AssertionError(f"unexpected url: {url}")

    with patch("app.crawler.backfill_menu.fetch_url", side_effect=fake_fetch), patch(
        "app.crawler.backfill_menu.time.sleep"
    ), patch("app.crawler.backfill_menu.FETCH_DEADLINE_SECONDS", 0.2):
        backfill_menus(session_factory=session_factory, progress_file=None)

    with session_factory() as session:
        assert session.get(Restaurant, "place-1").menu_items == []
        place2 = session.get(Restaurant, "place-2")
        assert [m.name for m in place2.menu_items] == ["안심카츠", "치즈카츠"]


def test_backfill_menus_continues_past_a_db_save_failure_for_one_restaurant():
    # Regression test: a price-range menu item once overflowed Postgres's Integer
    # column and crashed the entire multi-hour backfill run partway through. A
    # single restaurant's save failure must not stop the rest of the batch.
    session_factory = make_test_session_factory()

    with session_factory() as session:
        session.add_all(
            [
                Restaurant(id="place-1", name="문제가게"),
                Restaurant(id="place-2", name="경양카츠 연남점"),
            ]
        )
        session.commit()

    def fake_fetch(url, **kwargs):
        return DETAIL_HTML_WITH_MENU

    from app import models as models_module

    original_menu_item = models_module.MenuItem

    def raise_for_place_1(*args, **kwargs):
        raise RuntimeError("simulated DB save failure (e.g. integer out of range)")

    call_count = {"n": 0}

    def selective_menu_item(*args, **kwargs):
        call_count["n"] += 1
        if call_count["n"] == 1:
            raise_for_place_1()
        return original_menu_item(*args, **kwargs)

    with patch("app.crawler.backfill_menu.fetch_url", side_effect=fake_fetch), patch(
        "app.crawler.backfill_menu.time.sleep"
    ), patch("app.crawler.backfill_menu.MenuItem", side_effect=selective_menu_item):
        backfill_menus(session_factory=session_factory, progress_file=None)

    with session_factory() as session:
        # place-1's save failed and was skipped; place-2 (processed afterward) still succeeded.
        assert session.get(Restaurant, "place-1").menu_items == []
        place2 = session.get(Restaurant, "place-2")
        assert [m.name for m in place2.menu_items] == ["안심카츠", "치즈카츠"]


def test_fetch_with_deadline_raises_timeout_error_instead_of_hanging_forever():
    def hangs_forever(url, **kwargs):
        time.sleep(3600)

    with patch("app.crawler.backfill_menu.fetch_url", side_effect=hangs_forever):
        try:
            _fetch_with_deadline("https://www.matzipmap.com/place/place-1", timeout=0.2)
            raised = False
        except TimeoutError:
            raised = True

    assert raised
