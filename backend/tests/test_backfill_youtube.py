from unittest.mock import patch

from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool

from app.crawler.backfill_youtube import backfill_youtube_urls, BASE_URL
from app.db import init_db, make_session_factory
from app.models import Restaurant

DETAIL_HTML_WITH_VIDEO = """
<script type="application/ld+json">
{"@type": "Restaurant", "name": "경양카츠 연남점"}
</script>
<a class="pgal__cell" href="https://www.youtube.com/watch?v=13fi46HgCKw" aria-label="유튜브 앱에서 영상 보기"></a>
"""

DETAIL_HTML_WITHOUT_VIDEO = """
<script type="application/ld+json">
{"@type": "Restaurant", "name": "두번째식당"}
</script>
"""


def make_test_session_factory():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    init_db(engine)
    return make_session_factory(engine)


def test_backfill_youtube_urls_fills_in_missing_urls_and_skips_restaurants_already_set():
    session_factory = make_test_session_factory()

    with session_factory() as session:
        session.add_all(
            [
                Restaurant(id="place-1", name="경양카츠 연남점"),
                Restaurant(id="place-2", name="두번째식당"),
                Restaurant(id="place-3", name="이미채워짐", youtube_url="https://www.youtube.com/watch?v=already"),
            ]
        )
        session.commit()

    def fake_fetch(url, **kwargs):
        if url == f"{BASE_URL}/place/place-1":
            return DETAIL_HTML_WITH_VIDEO
        if url == f"{BASE_URL}/place/place-2":
            return DETAIL_HTML_WITHOUT_VIDEO
        raise AssertionError(f"unexpected url (place-3 should be skipped entirely): {url}")

    with patch("app.crawler.backfill_youtube.fetch_url", side_effect=fake_fetch), patch(
        "app.crawler.backfill_youtube.time.sleep"
    ):
        backfill_youtube_urls(session_factory=session_factory)

    with session_factory() as session:
        assert session.get(Restaurant, "place-1").youtube_url == "https://www.youtube.com/watch?v=13fi46HgCKw"
        assert session.get(Restaurant, "place-2").youtube_url is None
        assert session.get(Restaurant, "place-3").youtube_url == "https://www.youtube.com/watch?v=already"


def test_backfill_youtube_urls_skips_restaurant_on_fetch_failure():
    session_factory = make_test_session_factory()

    with session_factory() as session:
        session.add(Restaurant(id="place-1", name="경양카츠 연남점"))
        session.commit()

    def raise_error(*args, **kwargs):
        raise RuntimeError("network error")

    with patch("app.crawler.backfill_youtube.fetch_url", side_effect=raise_error), patch(
        "app.crawler.backfill_youtube.time.sleep"
    ):
        backfill_youtube_urls(session_factory=session_factory)

    with session_factory() as session:
        assert session.get(Restaurant, "place-1").youtube_url is None
