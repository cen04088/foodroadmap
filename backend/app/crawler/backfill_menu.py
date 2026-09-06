import logging
import os
import threading
import time

from app.crawler.fetch import fetch_url
from app.crawler.parser import parse_place_detail_page
from app.db import make_engine, make_session_factory
from app.models import MenuItem, Restaurant

BASE_URL = "https://www.matzipmap.com"
REQUEST_DELAY_SECONDS = 1.0
FETCH_DEADLINE_SECONDS = 15.0
DEFAULT_PROGRESS_FILE = "backfill_menu_checked.txt"

logger = logging.getLogger(__name__)


def _fetch_with_deadline(url: str, timeout: float = FETCH_DEADLINE_SECONDS) -> str:
    """Enforces a hard wall-clock deadline around fetch_url — see backfill_youtube.py's
    identical helper for the full rationale (a slowly-trickling connection can otherwise
    keep resetting requests' own per-read timeout and hang indefinitely)."""
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


def backfill_menus(
    session_factory=None, limit: int | None = None, progress_file: str | None = DEFAULT_PROGRESS_FILE
) -> None:
    """One-off backfill for restaurants crawled before menu scraping existed.

    Re-fetches each restaurant's place detail page and fills in menu_items where
    matzipmap has a menu section. Only touches menu_items -- never overwrites
    name/category/address/etc, unlike run_crawl.upsert_restaurant which expects a
    full record.

    A restaurant genuinely without a menu section stays with no menu_items forever
    (correct end state), so -- same as backfill_youtube.py -- `progress_file`
    persists every checked id (found or not) across invocations so limited batches
    actually advance instead of re-checking the same leading restaurants forever.
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
                for r in session.query(Restaurant).filter(~Restaurant.menu_items.any()).all()
                if r.id not in already_checked
            ]

        if limit is not None:
            external_ids = external_ids[:limit]

        total = len(external_ids)
        logger.info("backfilling menu for %d restaurants", total)
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

                menu = detail.get("menu") if detail else None
                if not menu:
                    if progress_fh:
                        progress_fh.write(f"{external_id}\n")
                        progress_fh.flush()
                    continue

                try:
                    with session_factory() as session:
                        restaurant = session.get(Restaurant, external_id)
                        if restaurant is not None:
                            restaurant.menu_items = [
                                MenuItem(
                                    name=item["name"],
                                    price_won=item.get("price_won"),
                                    is_representative=item.get("is_representative", False),
                                    position=item.get("position", 0),
                                )
                                for item in menu
                            ]
                            session.commit()
                            updated += 1
                except Exception:
                    # 개별 가게의 이상한 데이터(예: 실제로 한 번 겪은 가격 범위 오버플로우) 하나
                    # 때문에 몇 시간짜리 백필 전체가 죽어서는 안 된다 — 기록하고 다음으로 넘어간다.
                    logger.warning("failed to save menu for %s", external_id, exc_info=True)

                if progress_fh:
                    progress_fh.write(f"{external_id}\n")
                    progress_fh.flush()

                if (i + 1) % 10 == 0:
                    logger.info("progress: %d/%d checked, %d matched so far", i + 1, total, updated)
        finally:
            if progress_fh:
                progress_fh.close()

        logger.info("menu backfill complete: %d/%d restaurants updated", updated, total)
    finally:
        if engine is not None:
            engine.dispose()


if __name__ == "__main__":
    import sys

    logging.basicConfig(level=logging.INFO)
    cli_limit = int(sys.argv[1]) if len(sys.argv) > 1 else None
    backfill_menus(limit=cli_limit)
