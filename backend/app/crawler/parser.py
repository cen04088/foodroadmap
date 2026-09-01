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
