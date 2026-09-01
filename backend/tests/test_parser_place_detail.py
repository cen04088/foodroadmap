from pathlib import Path

from app.crawler.parser import parse_place_detail_page

FIXTURES = Path(__file__).parent / "fixtures"


def test_parse_place_detail_page_extracts_geo_and_fields():
    html = (FIXTURES / "place_detail.html").read_text(encoding="utf-8")

    result = parse_place_detail_page(html)

    assert result is not None
    assert result["name"] == "경양카츠 연남점"
    assert result["address"] == "서울 마포구 연남동 260-29"
    assert result["latitude"] == 37.5612032
    assert result["longitude"] == 126.9244277
    assert result["phone"] == "070-7543-5445"
    assert result["category"] == "일식"


def test_parse_place_detail_page_returns_none_without_restaurant_jsonld():
    result = parse_place_detail_page("<html><body>no data here</body></html>")

    assert result is None
