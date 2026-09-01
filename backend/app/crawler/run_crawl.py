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

    restaurant.name = data["name"]
    restaurant.category = data.get("category")
    restaurant.address = data.get("address")
    restaurant.phone = data.get("phone")
    restaurant.hours = data.get("hours")
    if data.get("latitude") is not None:
        restaurant.latitude = data["latitude"]
        restaurant.longitude = data["longitude"]

    return restaurant


def collect_program_restaurants(slug: str) -> list[dict]:
    all_items = []
    page = 1

    while True:
        url = f"{BASE_URL}/broadcast/{slug}?page={page}"
        try:
            html = fetch_url(url)
        except RuntimeError:
            logger.warning("failed to fetch list page, skipping: %s", url)
            break

        result = parse_broadcast_list_page(html)
        all_items.extend(result["items"])

        if not result["has_next_page"]:
            break

        page += 1
        time.sleep(REQUEST_DELAY_SECONDS)

    return all_items


def run_crawl(session_factory=None) -> None:
    if session_factory is None:
        engine = make_engine()
        init_db(engine)
        session_factory = make_session_factory(engine)

    programs_html = fetch_url(f"{BASE_URL}/broadcasts")
    programs = parse_broadcasts_list_page(programs_html)

    restaurant_data: dict[str, dict] = {}
    restaurant_programs: dict[str, list[str]] = {}

    with session_factory() as session:
        for program in programs:
            upsert_broadcast(session, program["slug"], program["name"])
            time.sleep(REQUEST_DELAY_SECONDS)

            for item in collect_program_restaurants(program["slug"]):
                restaurant_data.setdefault(item["external_id"], item)
                restaurant_programs.setdefault(item["external_id"], []).append(program["slug"])

        for external_id, base_data in restaurant_data.items():
            try:
                detail_html = fetch_url(f"{BASE_URL}/place/{external_id}")
                detail = parse_place_detail_page(detail_html)
            except RuntimeError:
                logger.warning("failed to fetch detail page, skipping geo: %s", external_id)
                detail = None
            time.sleep(REQUEST_DELAY_SECONDS)

            merged = {**base_data}
            if detail:
                merged["latitude"] = detail.get("latitude")
                merged["longitude"] = detail.get("longitude")

            restaurant = upsert_restaurant(session, merged)
            for slug in restaurant_programs[external_id]:
                broadcast = session.get(Broadcast, slug)
                if broadcast not in restaurant.broadcasts:
                    restaurant.broadcasts.append(broadcast)

        session.commit()

    logger.info(
        "crawl complete: %d restaurants across %d programs",
        len(restaurant_data),
        len(programs),
    )


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    run_crawl()
