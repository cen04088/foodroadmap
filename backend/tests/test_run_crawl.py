import logging
from unittest.mock import patch, Mock, MagicMock

import pytest
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool

from app.crawler import parser as real_parser
from app.db import init_db, make_session_factory
from app.models import Restaurant, Broadcast
from app.crawler.run_crawl import (
    run_crawl,
    collect_program_restaurants,
    upsert_restaurant,
    BASE_URL,
    MAX_PAGES,
)

# Kept as a plain reference (not a module attribute lookup) so tests that
# patch app.crawler.run_crawl.upsert_restaurant can still delegate to the
# real implementation from inside their replacement.
REAL_UPSERT_RESTAURANT = upsert_restaurant

BROADCASTS_HTML = """
<a class="lp-net__card" href="/broadcast/ttoganjib">
  <span class="lp-net__meta"><span class="lp-net__name">또간집</span></span>
</a>
"""

LIST_PAGE_HTML = """
<li><a class="bc-item" href="/place/place-1">
  <span class="bc-item__body">
    <span class="bc-item__name">경양카츠 연남점<span class="bc-item__cat">일식</span></span>
    <span class="bc-item__addr">서울 마포구 연남동 260-29</span>
    <span class="bc-item__meta">
      <span>📞 070-7543-5445</span>
      <span>🕘 월~일 11:30~21:00</span>
    </span>
  </span>
</a></li>
"""

DETAIL_HTML = """
<script type="application/ld+json">
{"@type": "Restaurant", "name": "경양카츠 연남점", "address": "서울 마포구 연남동 260-29",
 "geo": {"latitude": 37.5612032, "longitude": 126.9244277},
 "telephone": "070-7543-5445", "servesCuisine": "일식"}
</script>
<a class="pgal__cell" href="https://www.youtube.com/watch?v=13fi46HgCKw" aria-label="유튜브 앱에서 영상 보기"></a>
"""


def fake_fetch_url(url, **kwargs):
    if url == f"{BASE_URL}/broadcasts":
        return BROADCASTS_HTML
    if url.startswith(f"{BASE_URL}/broadcast/ttoganjib"):
        return LIST_PAGE_HTML
    if url == f"{BASE_URL}/place/place-1":
        return DETAIL_HTML
    raise AssertionError(f"unexpected url: {url}")


# Engines created by make_in_memory_session_factory() below, disposed by the
# _dispose_test_engines autouse fixture after each test. These are test-owned
# engines (the injected session_factory path), separate from the engine
# run_crawl() creates and disposes for itself, which is covered directly by
# the dispose-related tests further down.
_test_engines: list = []


def make_in_memory_session_factory():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    _test_engines.append(engine)
    init_db(engine)
    return make_session_factory(engine)


@pytest.fixture(autouse=True)
def _dispose_test_engines():
    yield
    while _test_engines:
        _test_engines.pop().dispose()


BROADCASTS_HTML_WITH_EXCLUDED = """
<a class="lp-net__card" href="/broadcast/ttoganjib">
  <span class="lp-net__meta"><span class="lp-net__name">또간집</span></span>
</a>
<a class="lp-net__card" href="/broadcast/myeotkki">
  <span class="lp-net__meta"><span class="lp-net__name">쯔양 몇끼</span></span>
</a>
"""


def test_run_crawl_skips_permanently_excluded_broadcasts():
    session_factory = make_in_memory_session_factory()

    def fake_fetch(url, **kwargs):
        if url == f"{BASE_URL}/broadcasts":
            return BROADCASTS_HTML_WITH_EXCLUDED
        if url.startswith(f"{BASE_URL}/broadcast/ttoganjib"):
            return LIST_PAGE_HTML
        if url == f"{BASE_URL}/place/place-1":
            return DETAIL_HTML
        raise AssertionError(f"excluded broadcast should never be fetched: {url}")

    with patch("app.crawler.run_crawl.fetch_url", side_effect=fake_fetch), patch(
        "app.crawler.run_crawl.time.sleep"
    ):
        run_crawl(session_factory=session_factory)

    with session_factory() as session:
        assert session.get(Broadcast, "ttoganjib") is not None
        assert session.get(Broadcast, "myeotkki") is None


def test_run_crawl_populates_restaurants_and_broadcasts():
    session_factory = make_in_memory_session_factory()

    with patch("app.crawler.run_crawl.fetch_url", side_effect=fake_fetch_url), \
         patch("app.crawler.run_crawl.time.sleep"):
        run_crawl(session_factory=session_factory)

    with session_factory() as session:
        restaurant = session.get(Restaurant, "place-1")
        assert restaurant is not None
        assert restaurant.name == "경양카츠 연남점"
        assert restaurant.latitude == 37.5612032
        assert restaurant.longitude == 126.9244277
        assert restaurant.youtube_url == "https://www.youtube.com/watch?v=13fi46HgCKw"
        assert [b.id for b in restaurant.broadcasts] == ["ttoganjib"]

        broadcast = session.get(Broadcast, "ttoganjib")
        assert broadcast.name == "또간집"


def test_run_crawl_is_idempotent_on_rerun():
    session_factory = make_in_memory_session_factory()

    with patch("app.crawler.run_crawl.fetch_url", side_effect=fake_fetch_url), \
         patch("app.crawler.run_crawl.time.sleep"):
        run_crawl(session_factory=session_factory)
        run_crawl(session_factory=session_factory)

    with session_factory() as session:
        restaurant = session.get(Restaurant, "place-1")
        assert restaurant is not None
        assert len(restaurant.broadcasts) == 1


# --- Resilience: a fetch/parse failure on one item must not abort the crawl ---

BROADCASTS_HTML_TWO_PROGRAMS = """
<a class="lp-net__card" href="/broadcast/ttoganjib">
  <span class="lp-net__meta"><span class="lp-net__name">또간집</span></span>
</a>
<a class="lp-net__card" href="/broadcast/broken-program">
  <span class="lp-net__meta"><span class="lp-net__name">고장난프로그램</span></span>
</a>
"""

LIST_PAGE_HTML_TWO_ITEMS = """
<li><a class="bc-item" href="/place/place-1">
  <span class="bc-item__body">
    <span class="bc-item__name">경양카츠 연남점<span class="bc-item__cat">일식</span></span>
    <span class="bc-item__addr">서울 마포구 연남동 260-29</span>
    <span class="bc-item__meta">
      <span>📞 070-7543-5445</span>
      <span>🕘 월~일 11:30~21:00</span>
    </span>
  </span>
</a></li>
<li><a class="bc-item" href="/place/place-2">
  <span class="bc-item__body">
    <span class="bc-item__name">두번째식당<span class="bc-item__cat">한식</span></span>
    <span class="bc-item__addr">서울 마포구 동교동 1-1</span>
    <span class="bc-item__meta">
      <span>📞 02-000-0000</span>
      <span>🕘 매일 10:00~22:00</span>
    </span>
  </span>
</a></li>
"""

# Contains a sentinel comment so the mocked parser below can single it out and
# raise a non-RuntimeError exception, even though fetching it succeeds.
DETAIL_HTML_PLACE2 = """
<!-- place-2-sentinel -->
<script type="application/ld+json">
{"@type": "Restaurant", "name": "두번째식당", "address": "서울 마포구 동교동 1-1",
 "geo": {"latitude": 37.1, "longitude": 126.1},
 "telephone": "02-000-0000", "servesCuisine": "한식"}
</script>
"""


def fake_fetch_url_with_failures(url, **kwargs):
    if url == f"{BASE_URL}/broadcasts":
        return BROADCASTS_HTML_TWO_PROGRAMS
    if url.startswith(f"{BASE_URL}/broadcast/ttoganjib"):
        return LIST_PAGE_HTML_TWO_ITEMS
    if url.startswith(f"{BASE_URL}/broadcast/broken-program"):
        # Simulates a list-page fetch failure for an entire program.
        raise RuntimeError("simulated list page fetch failure")
    if url == f"{BASE_URL}/place/place-1":
        return DETAIL_HTML
    if url == f"{BASE_URL}/place/place-2":
        # Fetch succeeds, but the mocked parser below raises on this HTML.
        return DETAIL_HTML_PLACE2
    raise AssertionError(f"unexpected url: {url}")


def flaky_parse_place_detail_page(html):
    if "place-2-sentinel" in html:
        # Simulates a *parse* failure (not a fetch failure) that is not a
        # RuntimeError, to prove the broadened except clause catches it too.
        raise ValueError("simulated parse failure")
    return real_parser.parse_place_detail_page(html)


def test_run_crawl_skips_failed_items_and_persists_the_rest():
    session_factory = make_in_memory_session_factory()

    with patch("app.crawler.run_crawl.fetch_url", side_effect=fake_fetch_url_with_failures), \
         patch(
             "app.crawler.run_crawl.parse_place_detail_page",
             side_effect=flaky_parse_place_detail_page,
         ), \
         patch("app.crawler.run_crawl.time.sleep"):
        run_crawl(session_factory=session_factory)

    with session_factory() as session:
        # place-1: everything succeeded, including geo from its detail page.
        restaurant1 = session.get(Restaurant, "place-1")
        assert restaurant1 is not None
        assert restaurant1.name == "경양카츠 연남점"
        assert restaurant1.latitude == 37.5612032
        assert [b.id for b in restaurant1.broadcasts] == ["ttoganjib"]

        # place-2: detail fetch succeeded but parsing it raised a non-RuntimeError
        # exception. The restaurant must still be persisted from list-page data,
        # just without geo coordinates.
        restaurant2 = session.get(Restaurant, "place-2")
        assert restaurant2 is not None
        assert restaurant2.name == "두번째식당"
        assert restaurant2.latitude is None
        assert restaurant2.longitude is None
        assert [b.id for b in restaurant2.broadcasts] == ["ttoganjib"]

        # ttoganjib's list page succeeded normally.
        ttoganjib = session.get(Broadcast, "ttoganjib")
        assert ttoganjib is not None
        assert ttoganjib.name == "또간집"

        # broken-program: its list-page fetch raised RuntimeError, so it has no
        # restaurants, but the broadcast row itself (upserted before the fetch)
        # is still present and the crawl did not abort because of it.
        broken = session.get(Broadcast, "broken-program")
        assert broken is not None
        assert broken.name == "고장난프로그램"
        assert broken.restaurants == []


# --- Incremental commits: earlier programs must survive a later crash ---

BROADCASTS_HTML_CRASH_TEST = """
<a class="lp-net__card" href="/broadcast/ttoganjib">
  <span class="lp-net__meta"><span class="lp-net__name">또간집</span></span>
</a>
<a class="lp-net__card" href="/broadcast/second-program">
  <span class="lp-net__meta"><span class="lp-net__name">두번째프로그램</span></span>
</a>
"""

LIST_PAGE_HTML_PLACE2_ONLY = """
<li><a class="bc-item" href="/place/place-2">
  <span class="bc-item__body">
    <span class="bc-item__name">두번째식당<span class="bc-item__cat">한식</span></span>
    <span class="bc-item__addr">서울 마포구 동교동 1-1</span>
    <span class="bc-item__meta">
      <span>📞 02-000-0000</span>
      <span>🕘 매일 10:00~22:00</span>
    </span>
  </span>
</a></li>
"""


def fake_fetch_url_for_crash_test(url, **kwargs):
    if url == f"{BASE_URL}/broadcasts":
        return BROADCASTS_HTML_CRASH_TEST
    if url.startswith(f"{BASE_URL}/broadcast/ttoganjib"):
        return LIST_PAGE_HTML
    if url.startswith(f"{BASE_URL}/broadcast/second-program"):
        return LIST_PAGE_HTML_PLACE2_ONLY
    if url == f"{BASE_URL}/place/place-1":
        return DETAIL_HTML
    if url == f"{BASE_URL}/place/place-2":
        return DETAIL_HTML  # content doesn't matter; upsert is what crashes below
    raise AssertionError(f"unexpected url: {url}")


def crashing_upsert_restaurant(session, data):
    """Stands in for upsert_restaurant, but raises an *uncaught* exception the
    moment the second program's restaurant is reached -- simulating a crash
    partway through a multi-hour crawl (e.g. Ctrl-C, a dropped connection, an
    unhandled bug) after the first program has already been fully processed.
    """
    if data["external_id"] == "place-2":
        raise RuntimeError("simulated crash mid-crawl")
    return REAL_UPSERT_RESTAURANT(session, data)


def test_run_crawl_persists_earlier_programs_when_a_later_program_crashes():
    session_factory = make_in_memory_session_factory()

    with patch("app.crawler.run_crawl.fetch_url", side_effect=fake_fetch_url_for_crash_test), \
         patch(
             "app.crawler.run_crawl.upsert_restaurant",
             side_effect=crashing_upsert_restaurant,
         ), \
         patch("app.crawler.run_crawl.time.sleep"):
        with pytest.raises(RuntimeError, match="simulated crash mid-crawl"):
            run_crawl(session_factory=session_factory)

    # Query back with a brand-new session (not the one run_crawl used) to
    # prove the first program's work was genuinely committed to the database,
    # not merely held in memory in the session that then crashed.
    with session_factory() as fresh_session:
        ttoganjib = fresh_session.get(Broadcast, "ttoganjib")
        assert ttoganjib is not None
        assert ttoganjib.name == "또간집"

        restaurant1 = fresh_session.get(Restaurant, "place-1")
        assert restaurant1 is not None
        assert restaurant1.name == "경양카츠 연남점"
        assert [b.id for b in restaurant1.broadcasts] == ["ttoganjib"]

        # The second program's work never reached its commit, so none of it
        # should have leaked into the database.
        assert fresh_session.get(Restaurant, "place-2") is None
        assert fresh_session.get(Broadcast, "second-program") is None


# --- Loud failure on total selector breakage (Important 3) ---


def test_run_crawl_logs_error_when_zero_programs_found(caplog):
    session_factory = make_in_memory_session_factory()

    with patch(
        "app.crawler.run_crawl.fetch_url", return_value="<html>no programs here</html>"
    ), patch("app.crawler.run_crawl.time.sleep"), caplog.at_level(
        logging.ERROR, logger="app.crawler.run_crawl"
    ):
        run_crawl(session_factory=session_factory)

    error_records = [r for r in caplog.records if r.levelno == logging.ERROR]
    assert any("zero programs" in r.message for r in error_records)

    # Nothing should have been written to the database.
    with session_factory() as session:
        assert session.get(Broadcast, "ttoganjib") is None


def test_run_crawl_logs_warning_when_a_program_has_zero_restaurants(caplog):
    session_factory = make_in_memory_session_factory()

    broadcasts_html = """
    <a class="lp-net__card" href="/broadcast/empty-program">
      <span class="lp-net__meta"><span class="lp-net__name">빈프로그램</span></span>
    </a>
    """

    def fake_fetch(url, **kwargs):
        if url == f"{BASE_URL}/broadcasts":
            return broadcasts_html
        if url.startswith(f"{BASE_URL}/broadcast/empty-program"):
            return "<html>no items here</html>"
        raise AssertionError(f"unexpected url: {url}")

    with patch("app.crawler.run_crawl.fetch_url", side_effect=fake_fetch), \
         patch("app.crawler.run_crawl.time.sleep"), \
         caplog.at_level(logging.WARNING, logger="app.crawler.run_crawl"):
        run_crawl(session_factory=session_factory)

    warning_records = [r for r in caplog.records if r.levelno == logging.WARNING]
    assert any("empty-program" in r.message for r in warning_records)

    # The broadcast row is still created; it just has no restaurants -- the
    # DB is correctly left untouched for the (nonexistent) restaurant data.
    with session_factory() as session:
        broadcast = session.get(Broadcast, "empty-program")
        assert broadcast is not None
        assert broadcast.restaurants == []


# --- Pagination safety guards (Important 4) ---


def test_collect_program_restaurants_stops_on_empty_page_even_if_has_next_page_claims_true():
    empty_page_with_next = {"items": [], "has_next_page": True}

    with patch(
        "app.crawler.run_crawl.fetch_url", return_value="<html></html>"
    ) as mock_fetch, patch(
        "app.crawler.run_crawl.parse_broadcast_list_page", return_value=empty_page_with_next
    ), patch("app.crawler.run_crawl.time.sleep"):
        items = collect_program_restaurants("some-program")

    assert items == []
    # Must not have followed the (bogus) has_next_page and fetched a second page.
    mock_fetch.assert_called_once()


def test_collect_program_restaurants_stops_at_max_pages():
    single_item_page_with_next = {
        "items": [
            {
                "external_id": "x",
                "name": "n",
                "category": None,
                "address": None,
                "phone": None,
                "hours": None,
            }
        ],
        "has_next_page": True,
    }

    with patch(
        "app.crawler.run_crawl.fetch_url", return_value="<html></html>"
    ) as mock_fetch, patch(
        "app.crawler.run_crawl.parse_broadcast_list_page",
        return_value=single_item_page_with_next,
    ), patch("app.crawler.run_crawl.time.sleep"):
        items = collect_program_restaurants("infinite-program")

    # An always-has-next-page pathological pager must not be followed forever.
    assert mock_fetch.call_count == MAX_PAGES
    assert len(items) == MAX_PAGES


# --- upsert_restaurant must not blank out a good name (Minor 2) ---


def test_upsert_restaurant_does_not_blank_out_existing_name_when_new_name_is_empty():
    session_factory = make_in_memory_session_factory()

    with session_factory() as session:
        session.add(Restaurant(id="place-1", name="경양카츠 연남점"))
        session.commit()

        # Simulates a markup change that made name extraction silently
        # fail to "" on a rerun.
        upsert_restaurant(
            session,
            {
                "external_id": "place-1",
                "name": "",
                "category": "일식",
                "address": "서울 마포구 연남동 260-29",
                "phone": "070-7543-5445",
                "hours": "월~일 11:30~21:00",
            },
        )
        session.commit()

    with session_factory() as session:
        restaurant = session.get(Restaurant, "place-1")
        assert restaurant.name == "경양카츠 연남점"
        # Other fields still update normally.
        assert restaurant.category == "일식"
        assert restaurant.phone == "070-7543-5445"


# --- The engine run_crawl creates for itself must be disposed (Minor 6) ---


def test_run_crawl_disposes_its_own_engine_when_no_session_factory_is_injected():
    fake_engine = Mock()
    fake_session = MagicMock()
    fake_session.__enter__ = Mock(return_value=fake_session)
    fake_session.__exit__ = Mock(return_value=False)

    with patch(
        "app.crawler.run_crawl.make_engine", return_value=fake_engine
    ) as mock_make_engine, patch("app.crawler.run_crawl.init_db"), patch(
        "app.crawler.run_crawl.make_session_factory", return_value=Mock(return_value=fake_session)
    ), patch(
        "app.crawler.run_crawl.fetch_url", return_value="<html>no programs here</html>"
    ), patch("app.crawler.run_crawl.time.sleep"):
        run_crawl()  # session_factory=None triggers the own-engine branch

    mock_make_engine.assert_called_once()
    fake_engine.dispose.assert_called_once()


def test_run_crawl_disposes_its_own_engine_even_when_the_crawl_raises():
    fake_engine = Mock()

    with patch("app.crawler.run_crawl.make_engine", return_value=fake_engine), patch(
        "app.crawler.run_crawl.init_db"
    ), patch("app.crawler.run_crawl.make_session_factory", return_value=Mock()), patch(
        "app.crawler.run_crawl.fetch_url", side_effect=RuntimeError("boom")
    ), patch("app.crawler.run_crawl.time.sleep"):
        with pytest.raises(RuntimeError, match="boom"):
            run_crawl()

    fake_engine.dispose.assert_called_once()


def test_run_crawl_does_not_dispose_an_injected_session_factorys_engine():
    # When a session_factory is injected (as tests do), run_crawl does not
    # own that engine's lifecycle and must leave it alone.
    session_factory = make_in_memory_session_factory()

    with patch("app.crawler.run_crawl.fetch_url", side_effect=fake_fetch_url), patch(
        "app.crawler.run_crawl.time.sleep"
    ):
        run_crawl(session_factory=session_factory)

    # The injected session_factory must still be usable afterwards -- proof
    # its underlying engine/connection was left open by run_crawl.
    with session_factory() as session:
        assert session.get(Restaurant, "place-1") is not None
