from pathlib import Path

from app.crawler.parser import parse_broadcasts_list_page

FIXTURES = Path(__file__).parent / "fixtures"


def test_parse_broadcasts_list_page_extracts_slug_and_name():
    html = (FIXTURES / "broadcasts_list.html").read_text(encoding="utf-8")

    programs = parse_broadcasts_list_page(html)

    slugs = {p["slug"] for p in programs}
    assert "ttoganjib" in slugs
    assert "jeonhyeonmu" in slugs

    ttoganjib = next(p for p in programs if p["slug"] == "ttoganjib")
    assert ttoganjib["name"] == "또간집"


def test_parse_broadcasts_list_page_has_no_duplicate_slugs():
    html = (FIXTURES / "broadcasts_list.html").read_text(encoding="utf-8")

    programs = parse_broadcasts_list_page(html)

    slugs = [p["slug"] for p in programs]
    assert len(slugs) == len(set(slugs))
