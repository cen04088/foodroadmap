import logging
import time

from app.crawler.fetch import fetch_url
from app.crawler.parser import parse_place_detail_page
from app.db import make_engine, make_session_factory
from app.models import Restaurant

BASE_URL = "https://www.matzipmap.com"
REQUEST_DELAY_SECONDS = 1.0

logger = logging.getLogger(__name__)


def backfill_youtube_urls(session_factory=None) -> None:
    """One-off backfill for restaurants crawled before youtube_url existed.

    Re-fetches each restaurant's place detail page (already-known external_id,
    no list-page pagination needed) and fills in youtube_url where matzipmap
    has one. Safe to re-run: only touches rows still missing a youtube_url.
    """
    engine = None
    if session_factory is None:
        engine = make_engine()
        session_factory = make_session_factory(engine)

    try:
        with session_factory() as session:
            external_ids = [
                r.id for r in session.query(Restaurant).filter(Restaurant.youtube_url.is_(None)).all()
            ]

        logger.info("backfilling youtube_url for %d restaurants", len(external_ids))
        updated = 0

        for external_id in external_ids:
            time.sleep(REQUEST_DELAY_SECONDS)
            try:
                detail_html = fetch_url(f"{BASE_URL}/place/{external_id}")
                detail = parse_place_detail_page(detail_html)
            except Exception:
                logger.warning("failed to fetch/parse detail page for %s", external_id, exc_info=True)
                continue

            youtube_url = detail.get("youtube_url") if detail else None
            if not youtube_url:
                continue

            with session_factory() as session:
                restaurant = session.get(Restaurant, external_id)
                if restaurant is not None:
                    restaurant.youtube_url = youtube_url
                    session.commit()
                    updated += 1

        logger.info("youtube backfill complete: %d/%d restaurants updated", updated, len(external_ids))
    finally:
        if engine is not None:
            engine.dispose()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    backfill_youtube_urls()
