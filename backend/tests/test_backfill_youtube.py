import time
from unittest.mock import patch

from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool

from app.crawler.backfill_youtube import _fetch_with_deadline, backfill_youtube_urls, BASE_URL
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
        backfill_youtube_urls(session_factory=session_factory, progress_file=None)

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
        backfill_youtube_urls(session_factory=session_factory, progress_file=None)

    with session_factory() as session:
        assert session.get(Restaurant, "place-1").youtube_url is None


def test_backfill_youtube_urls_records_fetch_failures_to_progress_file_too(tmp_path):
    # A 404 (restaurant removed from matzipmap) will never succeed on
    # retry -- it must be recorded just like a confirmed-empty result so
    # batched runs don't waste a request on it forever.
    session_factory = make_test_session_factory()
    progress_file = str(tmp_path / "checked.txt")

    with session_factory() as session:
        session.add(Restaurant(id="place-1", name="사라진가게"))
        session.commit()

    def raise_error(*args, **kwargs):
        raise RuntimeError("404")

    with patch("app.crawler.backfill_youtube.fetch_url", side_effect=raise_error), patch(
        "app.crawler.backfill_youtube.time.sleep"
    ):
        backfill_youtube_urls(session_factory=session_factory, progress_file=progress_file)

    checked_ids = {line.strip() for line in open(progress_file, encoding="utf-8")}
    assert checked_ids == {"place-1"}


def test_backfill_youtube_urls_respects_limit():
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
        return DETAIL_HTML_WITH_VIDEO

    with patch("app.crawler.backfill_youtube.fetch_url", side_effect=fake_fetch), patch(
        "app.crawler.backfill_youtube.time.sleep"
    ):
        backfill_youtube_urls(session_factory=session_factory, limit=2, progress_file=None)

    assert len(calls) == 2


def test_backfill_youtube_urls_advances_past_empty_restaurants_across_batches_via_progress_file(tmp_path):
    # Regression test: a restaurant with no video stays youtube_url=NULL
    # forever, so naive limit-slicing of a fresh "IS NULL" query re-selects
    # the exact same leading restaurants on every batched call instead of
    # advancing -- this actually happened while running the real backfill.
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
            return DETAIL_HTML_WITH_VIDEO
        return DETAIL_HTML_WITHOUT_VIDEO

    with patch("app.crawler.backfill_youtube.fetch_url", side_effect=fake_fetch), patch(
        "app.crawler.backfill_youtube.time.sleep"
    ):
        # First batch of 1: checks place-1, finds nothing, records it as checked.
        backfill_youtube_urls(session_factory=session_factory, limit=1, progress_file=progress_file)
        # Second batch of 1: must skip place-1 (already confirmed empty) and
        # move on to place-2, not re-check place-1 again.
        backfill_youtube_urls(session_factory=session_factory, limit=1, progress_file=progress_file)
        # Third batch: should reach place-3 and find its video.
        backfill_youtube_urls(session_factory=session_factory, limit=1, progress_file=progress_file)

    with session_factory() as session:
        assert session.get(Restaurant, "place-1").youtube_url is None
        assert session.get(Restaurant, "place-2").youtube_url is None
        assert session.get(Restaurant, "place-3").youtube_url == "https://www.youtube.com/watch?v=13fi46HgCKw"

    checked_ids = {line.strip() for line in open(progress_file, encoding="utf-8")}
    assert checked_ids == {"place-1", "place-2"}


def test_fetch_with_deadline_raises_timeout_error_instead_of_hanging_forever():
    def hangs_forever(url, **kwargs):
        time.sleep(3600)

    with patch("app.crawler.backfill_youtube.fetch_url", side_effect=hangs_forever):
        try:
            _fetch_with_deadline("https://www.matzipmap.com/place/place-1", timeout=0.2)
            raised = False
        except TimeoutError:
            raised = True

    assert raised


def test_fetch_with_deadline_reraises_the_underlying_exception_on_failure():
    def raise_error(url, **kwargs):
        raise RuntimeError("network error")

    with patch("app.crawler.backfill_youtube.fetch_url", side_effect=raise_error):
        try:
            _fetch_with_deadline("https://www.matzipmap.com/place/place-1", timeout=1.0)
            raised = None
        except RuntimeError as exc:
            raised = exc

    assert raised is not None
    assert str(raised) == "network error"


def test_fetch_with_deadline_returns_the_result_when_it_completes_in_time():
    with patch("app.crawler.backfill_youtube.fetch_url", return_value="<html>ok</html>"):
        result = _fetch_with_deadline("https://www.matzipmap.com/place/place-1", timeout=1.0)

    assert result == "<html>ok</html>"


def test_backfill_youtube_urls_treats_a_hung_fetch_as_a_recoverable_failure():
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
            return DETAIL_HTML_WITH_VIDEO
        raise AssertionError(f"unexpected url: {url}")

    with patch("app.crawler.backfill_youtube.fetch_url", side_effect=fake_fetch), patch(
        "app.crawler.backfill_youtube.time.sleep"
    ), patch("app.crawler.backfill_youtube.FETCH_DEADLINE_SECONDS", 0.2):
        backfill_youtube_urls(session_factory=session_factory, progress_file=None)

    with session_factory() as session:
        assert session.get(Restaurant, "place-1").youtube_url is None
        assert session.get(Restaurant, "place-2").youtube_url == "https://www.youtube.com/watch?v=13fi46HgCKw"
