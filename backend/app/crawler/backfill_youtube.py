import logging
import os
import threading
import time

from app.crawler.fetch import fetch_url
from app.crawler.parser import parse_place_detail_page
from app.db import make_engine, make_session_factory
from app.models import Restaurant

BASE_URL = "https://www.matzipmap.com"
REQUEST_DELAY_SECONDS = 1.0
FETCH_DEADLINE_SECONDS = 15.0
DEFAULT_PROGRESS_FILE = "backfill_youtube_checked.txt"

logger = logging.getLogger(__name__)


def _fetch_with_deadline(url: str, timeout: float = FETCH_DEADLINE_SECONDS) -> str:
    """Enforces a hard wall-clock deadline around fetch_url.

    requests' own timeout only bounds a single socket read/connect -- a
    server that keeps a connection alive by trickling bytes slowly enough
    to keep resetting that per-read timer can otherwise hang indefinitely.
    Runs the fetch in a daemon thread and abandons it (never blocking on
    it) if it doesn't return in time, so a stuck connection can't stall
    the whole crawl or the process's own exit.
    """
    outcome: dict = {}

    def worker() -> None:
        try:
            outcome["html"] = fetch_url(url)
        except Exception as exc:  # noqa: BLE001 - re-raised on the caller's thread below
            outcome["error"] = exc

    thread = threading.Thread(target=worker, daemon=True)
    thread.start()
    thread.join(timeout=timeout)
    if thread.is_alive():
        raise TimeoutError(f"fetch exceeded {timeout}s deadline: {url}")
    if "error" in outcome:
        raise outcome["error"]
    return outcome["html"]


def _load_checked_ids(progress_file: str | None) -> set[str]:
    if not progress_file or not os.path.exists(progress_file):
        return set()
    with open(progress_file, "r", encoding="utf-8") as f:
        return {line.strip() for line in f if line.strip()}


def backfill_youtube_urls(
    session_factory=None, limit: int | None = None, progress_file: str | None = DEFAULT_PROGRESS_FILE
) -> None:
    """One-off backfill for restaurants crawled before youtube_url existed.

    Re-fetches each restaurant's place detail page (already-known external_id,
    no list-page pagination needed) and fills in youtube_url where matzipmap
    has one. Safe to re-run: only touches rows still missing a youtube_url.

    A restaurant genuinely without a video stays youtube_url=NULL forever
    (that's the correct end state), so it can't be excluded from future runs
    via the DB alone. `progress_file` persists the set of ids already
    confirmed empty across separate invocations, so `limit`-ed batches
    actually advance through the list instead of re-checking the same
    leading restaurants every time (a real bug hit while running this: many
    batches in a row all landed on the same never-changing leading slice).
    """
    engine = None
    if session_factory is None:
        engine = make_engine()
        session_factory = make_session_factory(engine)

    already_checked = _load_checked_ids(progress_file)

    try:
        with session_factory() as session:
            external_ids = [
                r.id
                for r in session.query(Restaurant).filter(Restaurant.youtube_url.is_(None)).all()
                if r.id not in already_checked
            ]

        if limit is not None:
            external_ids = external_ids[:limit]

        total = len(external_ids)
        logger.info("backfilling youtube_url for %d restaurants", total)
        updated = 0
        progress_fh = open(progress_file, "a", encoding="utf-8") if progress_file else None

        try:
            for i, external_id in enumerate(external_ids):
                time.sleep(REQUEST_DELAY_SECONDS)
                try:
                    detail_html = _fetch_with_deadline(f"{BASE_URL}/place/{external_id}", FETCH_DEADLINE_SECONDS)
                    detail = parse_place_detail_page(detail_html)
                except Exception:
                    logger.warning("failed to fetch/parse detail page for %s", external_id, exc_info=True)
                    if progress_fh:
                        progress_fh.write(f"{external_id}\n")
                        progress_fh.flush()
                    continue

                youtube_url = detail.get("youtube_url") if detail else None
                if not youtube_url:
                    if progress_fh:
                        progress_fh.write(f"{external_id}\n")
                        progress_fh.flush()
                    continue

                with session_factory() as session:
                    restaurant = session.get(Restaurant, external_id)
                    if restaurant is not None:
                        restaurant.youtube_url = youtube_url
                        session.commit()
                        updated += 1

                if (i + 1) % 10 == 0:
                    logger.info("progress: %d/%d checked, %d matched so far", i + 1, total, updated)
        finally:
            if progress_fh:
                progress_fh.close()

        logger.info("youtube backfill complete: %d/%d restaurants updated", updated, total)
    finally:
        if engine is not None:
            engine.dispose()


if __name__ == "__main__":
    import sys

    logging.basicConfig(level=logging.INFO)
    cli_limit = int(sys.argv[1]) if len(sys.argv) > 1 else None
    backfill_youtube_urls(limit=cli_limit)
