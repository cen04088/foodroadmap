import logging
import time

from app.crawler.fetch import fetch_url
from app.crawler.parser import (
    parse_broadcasts_list_page,
    parse_broadcast_list_page,
    parse_place_detail_page,
)
from app.db import make_engine, init_db, make_session_factory
from app.models import Restaurant, Broadcast

BASE_URL = "https://www.matzipmap.com"
REQUEST_DELAY_SECONDS = 1.0
MAX_PAGES = 100

# 서비스에서 완전히 제외하기로 한 방송 (예: 쯔양 몇끼) — 재크롤링해도 다시
# 추가되지 않도록 프로그램 목록 단계에서 걸러낸다.
EXCLUDED_BROADCAST_SLUGS = {"myeotkki"}

logger = logging.getLogger(__name__)


def upsert_broadcast(session, slug: str, name: str) -> Broadcast:
    broadcast = session.get(Broadcast, slug)
    if broadcast is None:
        broadcast = Broadcast(id=slug, name=name)
        session.add(broadcast)
    else:
        broadcast.name = name
    return broadcast


def upsert_restaurant(session, data: dict) -> Restaurant:
    restaurant = session.get(Restaurant, data["external_id"])
    if restaurant is None:
        restaurant = Restaurant(id=data["external_id"])
        session.add(restaurant)

    # Only overwrite an existing name with a non-empty one: a markup change
    # that makes name extraction silently fail to "" must not blank out a
    # previously-good name on rerun (empty string passes the DB's
    # nullable=False constraint, so this would otherwise go unnoticed).
    if data.get("name"):
        restaurant.name = data["name"]
    restaurant.category = data.get("category")
    restaurant.address = data.get("address")
    restaurant.phone = data.get("phone")
    restaurant.hours = data.get("hours")
    if data.get("latitude") is not None:
        restaurant.latitude = data["latitude"]
        restaurant.longitude = data["longitude"]
    if data.get("youtube_url") is not None:
        restaurant.youtube_url = data["youtube_url"]

    return restaurant


def collect_program_restaurants(slug: str) -> list[dict]:
    all_items = []
    page = 1

    while True:
        if page > MAX_PAGES:
            logger.warning(
                "reached MAX_PAGES (%d) for %s, stopping pagination for this program "
                "(already-collected items are kept)",
                MAX_PAGES,
                slug,
            )
            break

        url = f"{BASE_URL}/broadcast/{slug}?page={page}"
        # Sleep before every request (including the first) so the delay always
        # separates this request from whatever request preceded it, regardless
        # of which loop or phase boundary it falls on.
        time.sleep(REQUEST_DELAY_SECONDS)
        try:
            html = fetch_url(url)
            result = parse_broadcast_list_page(html)
        except Exception:
            logger.warning(
                "failed to fetch/parse page %d for %s, stopping pagination for this program "
                "(already-collected items are kept): %s",
                page,
                slug,
                url,
                exc_info=True,
            )
            break

        if not result["items"]:
            # An empty page is never legitimately followed by more real data,
            # even if the pager link claims otherwise (e.g. a markup change
            # that makes has_next_page unconditionally true).
            logger.warning(
                "page %d for %s returned zero items, stopping pagination for this program "
                "(already-collected items are kept)",
                page,
                slug,
            )
            break

        all_items.extend(result["items"])

        if not result["has_next_page"]:
            break

        page += 1

    return all_items


def run_crawl(session_factory=None) -> None:
    # Only a session_factory created here (the default-engine branch) is ours
    # to dispose of; when the caller (e.g. a test) injects its own
    # session_factory, it owns that engine's lifecycle and we must not touch it.
    engine = None
    if session_factory is None:
        engine = make_engine()
        init_db(engine)
        session_factory = make_session_factory(engine)

    try:
        time.sleep(REQUEST_DELAY_SECONDS)
        programs_html = fetch_url(f"{BASE_URL}/broadcasts")
        programs = [
            p for p in parse_broadcasts_list_page(programs_html) if p["slug"] not in EXCLUDED_BROADCAST_SLUGS
        ]

        if not programs:
            logger.error(
                "matzipmap.com programs index returned zero programs - "
                "site structure may have changed"
            )

        # external_ids whose detail page has already been fetched during this
        # run, so a restaurant listed under multiple programs is only fetched
        # once while still getting every program's broadcast association.
        fetched_external_ids: set[str] = set()

        with session_factory() as session:
            for program in programs:
                upsert_broadcast(session, program["slug"], program["name"])

                try:
                    items = collect_program_restaurants(program["slug"])
                except Exception:
                    logger.warning(
                        "failed to process program, skipping: %s", program["slug"], exc_info=True
                    )
                    # Persist whatever this run has done so far (at minimum
                    # the broadcast upsert above) so a crash later in the
                    # run doesn't discard it.
                    session.commit()
                    continue

                if not items:
                    logger.warning(
                        "program %s returned zero restaurants - list page may be "
                        "empty or site structure may have changed",
                        program["slug"],
                    )

                for item in items:
                    external_id = item["external_id"]

                    if external_id not in fetched_external_ids:
                        fetched_external_ids.add(external_id)
                        time.sleep(REQUEST_DELAY_SECONDS)
                        try:
                            detail_html = fetch_url(f"{BASE_URL}/place/{external_id}")
                            detail = parse_place_detail_page(detail_html)
                        except Exception:
                            logger.warning(
                                "failed to fetch/parse detail page, skipping geo: %s",
                                external_id,
                                exc_info=True,
                            )
                            detail = None

                        merged = {**item}
                        if detail:
                            merged["latitude"] = detail.get("latitude")
                            merged["longitude"] = detail.get("longitude")
                            merged["youtube_url"] = detail.get("youtube_url")

                        upsert_restaurant(session, merged)

                    restaurant = session.get(Restaurant, external_id)
                    broadcast = session.get(Broadcast, program["slug"])
                    if broadcast is None:
                        # Not reachable today (the broadcast is always upserted
                        # earlier in this same session, above), but guard
                        # against it defensively.
                        continue
                    if broadcast not in restaurant.broadcasts:
                        restaurant.broadcasts.append(broadcast)

                # Commit once this program's restaurants + associations are
                # upserted, so an interruption partway through the (possibly
                # multi-hour) crawl only loses the in-flight program, not
                # everything already done.
                session.commit()

        logger.info(
            "crawl complete: %d restaurants across %d programs",
            len(fetched_external_ids),
            len(programs),
        )
    finally:
        if engine is not None:
            engine.dispose()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    run_crawl()
