from pathlib import Path

from app.crawler.parser import parse_broadcast_list_page

FIXTURES = Path(__file__).parent / "fixtures"


def test_parse_broadcast_list_page_extracts_items():
    html = (FIXTURES / "broadcast_list_page1.html").read_text(encoding="utf-8")

    result = parse_broadcast_list_page(html)

    by_id = {item["external_id"]: item for item in result["items"]}
    kakushita = by_id["215f440f-4392-4490-9b85-c6f52209e924"]
    assert kakushita["name"] == "카쿠시타"
    assert kakushita["category"] == "일식"
    assert kakushita["address"] == "서울 마포구 연남동 390-30"
    assert kakushita["phone"] == "0507-1348-8793"
    assert "월~목 12:00~23:00" in kakushita["hours"]


def test_parse_broadcast_list_page_handles_missing_phone():
    html = (FIXTURES / "broadcast_list_page1.html").read_text(encoding="utf-8")

    result = parse_broadcast_list_page(html)

    seongsu = next(
        item for item in result["items"] if item["name"] == "성수부두"
    )
    assert seongsu["phone"] is None
    assert "월~토 17:00~24:00" in seongsu["hours"]


def test_parse_broadcast_list_page_detects_next_page():
    html = (FIXTURES / "broadcast_list_page1.html").read_text(encoding="utf-8")

    result = parse_broadcast_list_page(html)

    assert result["has_next_page"] is True
