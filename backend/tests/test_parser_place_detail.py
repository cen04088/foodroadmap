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
    assert result["youtube_url"] == "https://www.youtube.com/watch?v=13fi46HgCKw"


def test_parse_place_detail_page_youtube_url_is_none_when_no_video_gallery_cell():
    html = """
    <html>
    <body>
    <script type="application/ld+json">
    {"@type": "Restaurant", "name": "경양카츠 연남점", "address": "서울 마포구 연남동 260-29",
     "geo": {"latitude": 37.5612032, "longitude": 126.9244277},
     "telephone": "070-7543-5445", "servesCuisine": "일식"}
    </script>
    </body>
    </html>
    """

    result = parse_place_detail_page(html)

    assert result is not None
    assert result["youtube_url"] is None


def test_parse_place_detail_page_returns_none_without_restaurant_jsonld():
    result = parse_place_detail_page("<html><body>no data here</body></html>")

    assert result is None


def test_parse_place_detail_page_skips_non_dict_jsonld():
    html = """
    <html>
    <body>
    <script type="application/ld+json">["not", "a", "dict"]</script>
    <script type="application/ld+json">{"@type": "WebSite", "name": "example"}</script>
    </body>
    </html>
    """

    result = parse_place_detail_page(html)

    assert result is None


def test_parse_place_detail_page_extracts_restaurant_from_array_of_entities():
    # Some sites wrap JSON-LD blocks in a top-level array of entities rather
    # than a single object -- the Restaurant entity must still be found.
    html = """
    <html>
    <body>
    <script type="application/ld+json">
    [{"@type": "WebSite", "name": "matzipmap"},
     {"@type": "Restaurant", "name": "경양카츠 연남점", "address": "서울 마포구 연남동 260-29",
      "geo": {"latitude": 37.5612032, "longitude": 126.9244277},
      "telephone": "070-7543-5445", "servesCuisine": "일식"}]
    </script>
    </body>
    </html>
    """

    result = parse_place_detail_page(html)

    assert result is not None
    assert result["name"] == "경양카츠 연남점"
    assert result["latitude"] == 37.5612032
    assert result["longitude"] == 126.9244277
    assert result["phone"] == "070-7543-5445"
    assert result["category"] == "일식"


def test_parse_place_detail_page_extracts_restaurant_from_graph_wrapper():
    # Some sites wrap JSON-LD entities in a {"@graph": [...]} object instead
    # of a bare array -- the Restaurant entity must still be found there too.
    html = """
    <html>
    <body>
    <script type="application/ld+json">
    {"@context": "https://schema.org", "@graph": [
      {"@type": "WebSite", "name": "matzipmap"},
      {"@type": "Restaurant", "name": "경양카츠 연남점", "address": "서울 마포구 연남동 260-29",
       "geo": {"latitude": 37.5612032, "longitude": 126.9244277},
       "telephone": "070-7543-5445", "servesCuisine": "일식"}
    ]}
    </script>
    </body>
    </html>
    """

    result = parse_place_detail_page(html)

    assert result is not None
    assert result["name"] == "경양카츠 연남점"
    assert result["latitude"] == 37.5612032
    assert result["longitude"] == 126.9244277
