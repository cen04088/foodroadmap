from unittest.mock import patch

from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool

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
