import json
import re

from bs4 import BeautifulSoup


def parse_broadcasts_list_page(html: str) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    programs = []
    seen_slugs = set()

    for card in soup.select("a.lp-net__card[href^='/broadcast/']"):
        slug = card["href"].removeprefix("/broadcast/")
        if slug in seen_slugs:
            continue

        name_el = card.select_one(".lp-net__name")
        if not name_el:
            continue

        seen_slugs.add(slug)
        programs.append({"slug": slug, "name": name_el.get_text(strip=True)})

    return programs


def parse_broadcast_list_page(html: str) -> dict:
    soup = BeautifulSoup(html, "html.parser")
    items = []

    for item in soup.select("a.bc-item[href^='/place/']"):
        external_id = item["href"].removeprefix("/place/")
        name_el = item.select_one(".bc-item__name")
        if not name_el or not external_id:
            continue

        name = next(iter(name_el.stripped_strings), "")
        cat_el = name_el.select_one(".bc-item__cat")
        category = cat_el.get_text(strip=True) if cat_el else None

        addr_el = item.select_one(".bc-item__addr")
        address = addr_el.get_text(strip=True) if addr_el else None

        phone = None
        hours = None
        for span in item.select(".bc-item__meta > span"):
            text = span.get_text(strip=True)
            if text.startswith("📞"):
                phone = text.removeprefix("📞").strip()
            elif text.startswith("🕘"):
                hours = text.removeprefix("🕘").strip()

        items.append(
            {
                "external_id": external_id,
                "name": name,
                "category": category,
                "address": address,
                "phone": phone,
                "hours": hours,
            }
        )

    has_next_page = soup.select_one("a.bc-pager__nav[rel='next']") is not None
    return {"items": items, "has_next_page": has_next_page}


def _find_restaurant_entity(data) -> dict | None:
    """Locate the Restaurant entity within a parsed JSON-LD block.

    Handles three shapes seen in the wild: a single object (the primary,
    expected case), a top-level array of entities (`[{...}, {...}]`), and a
    dict wrapping entities in an `"@graph"` list (`{"@graph": [...]}`).
    """
    if isinstance(data, dict):
        if data.get("@type") == "Restaurant":
            return data

        graph = data.get("@graph")
        if isinstance(graph, list):
            for entity in graph:
                if isinstance(entity, dict) and entity.get("@type") == "Restaurant":
                    return entity

        return None

    if isinstance(data, list):
        for entity in data:
            if isinstance(entity, dict) and entity.get("@type") == "Restaurant":
                return entity
        return None

    return None


def _parse_menu_items(soup: BeautifulSoup) -> list[dict]:
    """가게가 직접 <b class="pd-menu__tag">대표</b>로 표시해둔 메뉴만 is_representative=True —
    사이트에 이미 있는 사장님 큐레이션 신호라, 그냥 목록 순서로 "대표 메뉴"를 추측하지 않는다."""
    menu = soup.select_one(".pd-menu")
    if not menu:
        return []

    items = []
    for position, el in enumerate(menu.select(".pd-menu__item")):
        name_el = el.select_one(".pd-menu__name")
        if not name_el:
            continue

        tag_el = name_el.select_one(".pd-menu__tag")
        is_representative = tag_el is not None
        if tag_el:
            tag_el.extract()
        name = name_el.get_text(strip=True)
        if not name:
            continue

        price_el = el.select_one(".pd-menu__price")
        price_digits = re.sub(r"[^\d]", "", price_el.get_text(strip=True)) if price_el else ""
        price_won = int(price_digits) if price_digits else None

        items.append(
            {
                "name": name,
                "price_won": price_won,
                "is_representative": is_representative,
                "position": position,
            }
        )

    return items


def parse_place_detail_page(html: str) -> dict | None:
    soup = BeautifulSoup(html, "html.parser")

    for script in soup.select('script[type="application/ld+json"]'):
        try:
            data = json.loads(script.string or "")
        except (json.JSONDecodeError, TypeError):
            continue

        entity = _find_restaurant_entity(data)
        if entity is None:
            continue

        geo = entity.get("geo") or {}
        youtube_link = soup.select_one('a.pgal__cell[href*="youtube.com/watch"]')
        return {
            "name": entity.get("name"),
            "address": entity.get("address"),
            "latitude": geo.get("latitude"),
            "longitude": geo.get("longitude"),
            "phone": entity.get("telephone"),
            "category": entity.get("servesCuisine"),
            "youtube_url": youtube_link["href"] if youtube_link else None,
            "menu": _parse_menu_items(soup),
        }

    return None
