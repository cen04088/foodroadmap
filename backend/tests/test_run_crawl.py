from unittest.mock import patch

from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool

from app.crawler import parser as real_parser
from app.db import init_db, make_session_factory
from app.models import Restaurant, Broadcast
from app.crawler.run_crawl import run_crawl, BASE_URL

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
"""


def fake_fetch_url(url, **kwargs):
    if url == f"{BASE_URL}/broadcasts":
        return BROADCASTS_HTML
    if url.startswith(f"{BASE_URL}/broadcast/ttoganjib"):
        return LIST_PAGE_HTML
    if url == f"{BASE_URL}/place/place-1":
        return DETAIL_HTML
    raise AssertionError(f"unexpected url: {url}")


def make_in_memory_session_factory():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    init_db(engine)
    return make_session_factory(engine)


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
