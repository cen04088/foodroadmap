# 데이터 파운데이션 (DB 스키마 + matzipmap.com 크롤러) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** matzipmap.com(맛집여지도)을 크롤링해 방송 맛집 데이터(좌표 포함)를 PostgreSQL/SQLite DB에 채워 넣는, 독립적으로 실행 가능한 크롤러를 만든다.

**Architecture:** Python 크롤러가 matzipmap.com의 (1) 프로그램 목록 페이지, (2) 프로그램별 맛집 목록 페이지(페이지네이션), (3) 맛집 상세 페이지(좌표 포함 JSON-LD)를 순서대로 순회해 파싱하고, SQLAlchemy 모델을 통해 DB에 upsert한다. 파서/HTTP fetch/오케스트레이션을 별도 모듈로 분리해 각각 독립적으로 테스트한다.

**Tech Stack:** Python 3.11+, requests, beautifulsoup4, SQLAlchemy 2.0, pytest, SQLite(테스트/로컬)·PostgreSQL(운영, psycopg2-binary)

**Spec:** [docs/superpowers/specs/2026-09-01-route-restaurant-service-design.md](../specs/2026-09-01-route-restaurant-service-design.md) — 이 계획은 스펙의 §2.2(데이터 소스), §3.1(크롤러/DB 컴포넌트) 부분을 구현한다.

## Global Constraints

- matzipmap.com 요청 사이에는 최소 1초 딜레이를 둔다 (스펙 §2.2 크롤러 예의 요청).
- 좌표(위경도)는 matzipmap.com 맛집 상세 페이지의 JSON-LD에서 그대로 가져온다. 별도 지오코딩(카카오 로컬 API 등)은 사용하지 않는다 (스펙 §2.2).
- 맛집 레코드의 기본키는 matzipmap.com의 `/place/{uuid}` 경로에서 얻는 `external_id`(matzipmap 고유 uuid)로 한다.
- DB 연결 문자열은 `DATABASE_URL` 환경변수로 설정하며, 기본값은 `sqlite:///./foodmap.db` (스펙 §3.1: 운영은 PostgreSQL, 로컬 기본값은 SQLite로 시작해도 무방).
- 크롤러가 matzipmap.com 구조 변경으로 특정 페이지 파싱에 실패해도 예외로 전체 크롤링을 중단시키지 않고, 해당 항목만 건너뛰고 계속 진행한다(스펙 §6 에러 처리).

---

## 프로젝트 구조

```
backend/
  requirements.txt
  pytest.ini
  app/
    __init__.py
    db.py
    models.py
    crawler/
      __init__.py
      fetch.py
      parser.py
      run_crawl.py
  tests/
    __init__.py
    fixtures/
      broadcasts_list.html       # 이미 존재 (실제 matzipmap.com에서 수집)
      broadcast_list_page1.html  # 이미 존재
      place_detail.html          # 이미 존재
    test_db.py
    test_parser_broadcasts.py
    test_parser_broadcast_list.py
    test_parser_place_detail.py
    test_fetch.py
    test_run_crawl.py
```

`tests/fixtures/`의 세 HTML 파일은 이 계획을 세우면서 matzipmap.com에 직접 요청해 받아온 실제 페이지 내용이다 (2026-09-01 기준 마크업). 파서는 이 파일들을 대상으로 테스트한다.

---

### Task 1: 프로젝트 스캐폴딩 + DB 모델

**Files:**
- Create: `backend/requirements.txt`
- Create: `backend/pytest.ini`
- Create: `backend/app/__init__.py`
- Create: `backend/app/models.py`
- Create: `backend/app/db.py`
- Create: `backend/tests/__init__.py`
- Test: `backend/tests/test_db.py`

**Interfaces:**
- Produces: `app.models.Base` (SQLAlchemy declarative base), `app.models.Restaurant`, `app.models.Broadcast` (컬럼: 아래 참고), `app.db.make_engine(url: str | None = None) -> Engine`, `app.db.init_db(engine) -> None`, `app.db.make_session_factory(engine) -> sessionmaker`

- [ ] **Step 1: 디렉토리와 의존성 파일 생성**

`backend/requirements.txt`:
```
requests==2.32.3
beautifulsoup4==4.12.3
SQLAlchemy==2.0.35
psycopg2-binary==2.9.9
pytest==8.3.3
```

`backend/pytest.ini`:
```ini
[pytest]
pythonpath = .
```

`backend/app/__init__.py` (빈 파일), `backend/tests/__init__.py` (빈 파일)을 생성한다.

- [ ] **Step 2: 의존성 설치**

Run: `cd backend && pip install -r requirements.txt`
Expected: 에러 없이 설치 완료

- [ ] **Step 3: 실패하는 DB 테스트 작성**

`backend/tests/test_db.py`:
```python
from sqlalchemy import inspect

from app.db import make_engine, init_db, make_session_factory
from app.models import Restaurant, Broadcast


def test_init_db_creates_tables_and_roundtrips_data():
    engine = make_engine("sqlite:///:memory:")
    init_db(engine)

    table_names = set(inspect(engine).get_table_names())
    assert {"restaurants", "broadcasts", "restaurant_broadcasts"} <= table_names

    session_factory = make_session_factory(engine)
    with session_factory() as session:
        broadcast = Broadcast(id="ttoganjib", name="또간집")
        restaurant = Restaurant(
            id="baccbc42-f664-444a-8b73-951e2cf9eaa9",
            name="경양카츠 연남점",
            category="일식",
            address="서울 마포구 연남동 260-29",
            phone="070-7543-5445",
            hours="월~일 11:30~21:00",
            latitude=37.5612032,
            longitude=126.9244277,
        )
        restaurant.broadcasts.append(broadcast)
        session.add(restaurant)
        session.commit()

    with session_factory() as session:
        loaded = session.get(Restaurant, "baccbc42-f664-444a-8b73-951e2cf9eaa9")
        assert loaded.name == "경양카츠 연남점"
        assert loaded.latitude == 37.5612032
        assert [b.id for b in loaded.broadcasts] == ["ttoganjib"]
```

- [ ] **Step 4: 테스트 실행 → 실패 확인**

Run: `cd backend && pytest tests/test_db.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.db'` (아직 구현 전이므로)

- [ ] **Step 5: DB 모델 구현**

`backend/app/models.py`:
```python
from sqlalchemy import Column, String, Float, ForeignKey, Table
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()

restaurant_broadcasts = Table(
    "restaurant_broadcasts",
    Base.metadata,
    Column("restaurant_id", String, ForeignKey("restaurants.id"), primary_key=True),
    Column("broadcast_id", String, ForeignKey("broadcasts.id"), primary_key=True),
)


class Restaurant(Base):
    __tablename__ = "restaurants"

    id = Column(String, primary_key=True)
    name = Column(String, nullable=False)
    category = Column(String, nullable=True)
    address = Column(String, nullable=True)
    phone = Column(String, nullable=True)
    hours = Column(String, nullable=True)
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)

    broadcasts = relationship(
        "Broadcast", secondary=restaurant_broadcasts, back_populates="restaurants"
    )


class Broadcast(Base):
    __tablename__ = "broadcasts"

    id = Column(String, primary_key=True)
    name = Column(String, nullable=False)

    restaurants = relationship(
        "Restaurant", secondary=restaurant_broadcasts, back_populates="broadcasts"
    )
```

`backend/app/db.py`:
```python
import os

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models import Base

DEFAULT_DATABASE_URL = "sqlite:///./foodmap.db"


def make_engine(url: str | None = None):
    url = url or os.environ.get("DATABASE_URL", DEFAULT_DATABASE_URL)
    connect_args = {"check_same_thread": False} if url.startswith("sqlite") else {}
    return create_engine(url, connect_args=connect_args)


def init_db(engine) -> None:
    Base.metadata.create_all(engine)


def make_session_factory(engine):
    return sessionmaker(bind=engine)
```

- [ ] **Step 6: 테스트 실행 → 통과 확인**

Run: `cd backend && pytest tests/test_db.py -v`
Expected: PASS

- [ ] **Step 7: 커밋**

```bash
git add backend/requirements.txt backend/pytest.ini backend/app/__init__.py backend/app/models.py backend/app/db.py backend/tests/__init__.py backend/tests/test_db.py
git commit -m "feat: add DB models and engine setup for restaurant data"
```

---

### Task 2: 방송 프로그램 목록 파서

**Files:**
- Create: `backend/app/crawler/__init__.py`
- Create: `backend/app/crawler/parser.py`
- Test: `backend/tests/test_parser_broadcasts.py`

**Interfaces:**
- Consumes: 없음 (순수 HTML 문자열 입력)
- Produces: `app.crawler.parser.parse_broadcasts_list_page(html: str) -> list[dict]`, 각 dict는 `{"slug": str, "name": str}`

- [ ] **Step 1: 실패하는 테스트 작성**

`backend/tests/test_parser_broadcasts.py`:
```python
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
```

- [ ] **Step 2: 테스트 실행 → 실패 확인**

Run: `cd backend && pytest tests/test_parser_broadcasts.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.crawler'`

- [ ] **Step 3: 파서 구현**

`backend/app/crawler/__init__.py` (빈 파일)

`backend/app/crawler/parser.py`:
```python
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
```

- [ ] **Step 4: 테스트 실행 → 통과 확인**

Run: `cd backend && pytest tests/test_parser_broadcasts.py -v`
Expected: PASS

- [ ] **Step 5: 커밋**

```bash
git add backend/app/crawler/__init__.py backend/app/crawler/parser.py backend/tests/test_parser_broadcasts.py
git commit -m "feat: add matzipmap broadcasts index page parser"
```

---

### Task 3: 방송별 맛집 목록 파서 (페이지네이션 포함)

**Files:**
- Modify: `backend/app/crawler/parser.py`
- Test: `backend/tests/test_parser_broadcast_list.py`

**Interfaces:**
- Consumes: 없음 (순수 HTML 문자열 입력)
- Produces: `app.crawler.parser.parse_broadcast_list_page(html: str) -> dict`, 반환값은
  `{"items": list[dict], "has_next_page": bool}`. 각 item dict는
  `{"external_id": str, "name": str, "category": str | None, "address": str | None, "phone": str | None, "hours": str | None}`

- [ ] **Step 1: 실패하는 테스트 작성**

`backend/tests/test_parser_broadcast_list.py`:
```python
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
```

- [ ] **Step 2: 테스트 실행 → 실패 확인**

Run: `cd backend && pytest tests/test_parser_broadcast_list.py -v`
Expected: FAIL — `ImportError: cannot import name 'parse_broadcast_list_page'`

- [ ] **Step 3: 파서 구현 (parser.py에 추가)**

`backend/app/crawler/parser.py`에 다음 함수를 추가한다:
```python
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
```

- [ ] **Step 4: 테스트 실행 → 통과 확인**

Run: `cd backend && pytest tests/test_parser_broadcast_list.py -v`
Expected: PASS

- [ ] **Step 5: 커밋**

```bash
git add backend/app/crawler/parser.py backend/tests/test_parser_broadcast_list.py
git commit -m "feat: add matzipmap broadcast restaurant list page parser"
```

---

### Task 4: 맛집 상세 페이지 파서 (좌표 추출)

**Files:**
- Modify: `backend/app/crawler/parser.py`
- Test: `backend/tests/test_parser_place_detail.py`

**Interfaces:**
- Consumes: 없음 (순수 HTML 문자열 입력)
- Produces: `app.crawler.parser.parse_place_detail_page(html: str) -> dict | None`, 성공 시
  `{"name": str, "address": str | None, "latitude": float | None, "longitude": float | None, "phone": str | None, "category": str | None}`,
  `@type: "Restaurant"` JSON-LD 블록을 찾지 못하면 `None`

- [ ] **Step 1: 실패하는 테스트 작성**

`backend/tests/test_parser_place_detail.py`:
```python
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
```

- [ ] **Step 2: 테스트 실행 → 실패 확인**

Run: `cd backend && pytest tests/test_parser_place_detail.py -v`
Expected: FAIL — `ImportError: cannot import name 'parse_place_detail_page'`

- [ ] **Step 3: 파서 구현 (parser.py에 추가)**

`backend/app/crawler/parser.py` 상단에 `import json`을 추가하고, 다음 함수를 추가한다:
```python
def parse_place_detail_page(html: str) -> dict | None:
    soup = BeautifulSoup(html, "html.parser")

    for script in soup.select('script[type="application/ld+json"]'):
        try:
            data = json.loads(script.string or "")
        except (json.JSONDecodeError, TypeError):
            continue

        if data.get("@type") != "Restaurant":
            continue

        geo = data.get("geo") or {}
        return {
            "name": data.get("name"),
            "address": data.get("address"),
            "latitude": geo.get("latitude"),
            "longitude": geo.get("longitude"),
            "phone": data.get("telephone"),
            "category": data.get("servesCuisine"),
        }

    return None
```

- [ ] **Step 4: 테스트 실행 → 통과 확인**

Run: `cd backend && pytest tests/test_parser_place_detail.py -v`
Expected: PASS

- [ ] **Step 5: 커밋**

```bash
git add backend/app/crawler/parser.py backend/tests/test_parser_place_detail.py
git commit -m "feat: add matzipmap place detail page parser for geo coordinates"
```

---

### Task 5: HTTP fetch 유틸 (재시도 + 딜레이)

**Files:**
- Create: `backend/app/crawler/fetch.py`
- Test: `backend/tests/test_fetch.py`

**Interfaces:**
- Consumes: 없음
- Produces: `app.crawler.fetch.fetch_url(url: str, *, timeout: float = 10.0, max_retries: int = 3, backoff_seconds: float = 1.0) -> str`
  (실패 시 `RuntimeError` 발생)

- [ ] **Step 1: 실패하는 테스트 작성**

`backend/tests/test_fetch.py`:
```python
from unittest.mock import patch, Mock

import pytest
import requests

from app.crawler.fetch import fetch_url


def test_fetch_url_returns_response_text_on_success():
    fake_response = Mock(text="<html>ok</html>")
    fake_response.raise_for_status = Mock()

    with patch("app.crawler.fetch.requests.get", return_value=fake_response) as mock_get:
        result = fetch_url("https://www.matzipmap.com/broadcasts")

    assert result == "<html>ok</html>"
    mock_get.assert_called_once()
    assert mock_get.call_args.args[0] == "https://www.matzipmap.com/broadcasts"


def test_fetch_url_retries_then_raises_after_exhausting_attempts():
    with patch("app.crawler.fetch.requests.get", side_effect=requests.ConnectionError("boom")) as mock_get, \
         patch("app.crawler.fetch.time.sleep") as mock_sleep:
        with pytest.raises(RuntimeError):
            fetch_url("https://www.matzipmap.com/broadcasts", max_retries=3, backoff_seconds=0.01)

    assert mock_get.call_count == 3
    assert mock_sleep.call_count == 3


def test_fetch_url_recovers_after_one_failed_attempt():
    fake_response = Mock(text="<html>ok</html>")
    fake_response.raise_for_status = Mock()

    with patch(
        "app.crawler.fetch.requests.get",
        side_effect=[requests.ConnectionError("boom"), fake_response],
    ) as mock_get, patch("app.crawler.fetch.time.sleep"):
        result = fetch_url("https://www.matzipmap.com/broadcasts", max_retries=3, backoff_seconds=0.01)

    assert result == "<html>ok</html>"
    assert mock_get.call_count == 2
```

- [ ] **Step 2: 테스트 실행 → 실패 확인**

Run: `cd backend && pytest tests/test_fetch.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.crawler.fetch'`

- [ ] **Step 3: 구현**

`backend/app/crawler/fetch.py`:
```python
import time

import requests

USER_AGENT = "foodmap-crawler/0.1 (+contact: cen04088@gmail.com)"


def fetch_url(
    url: str,
    *,
    timeout: float = 10.0,
    max_retries: int = 3,
    backoff_seconds: float = 1.0,
) -> str:
    last_error: Exception | None = None

    for _attempt in range(max_retries):
        try:
            response = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=timeout)
            response.raise_for_status()
            return response.text
        except requests.RequestException as exc:
            last_error = exc
            time.sleep(backoff_seconds)

    raise RuntimeError(f"Failed to fetch {url} after {max_retries} attempts") from last_error
```

- [ ] **Step 4: 테스트 실행 → 통과 확인**

Run: `cd backend && pytest tests/test_fetch.py -v`
Expected: PASS

- [ ] **Step 5: 커밋**

```bash
git add backend/app/crawler/fetch.py backend/tests/test_fetch.py
git commit -m "feat: add HTTP fetch utility with retry and backoff"
```

---

### Task 6: 크롤러 오케스트레이션 + DB upsert + CLI 진입점

**Files:**
- Create: `backend/app/crawler/run_crawl.py`
- Test: `backend/tests/test_run_crawl.py`

**Interfaces:**
- Consumes:
  - `app.crawler.fetch.fetch_url(url, ...) -> str` (Task 5)
  - `app.crawler.parser.parse_broadcasts_list_page(html) -> list[dict]` (Task 2)
  - `app.crawler.parser.parse_broadcast_list_page(html) -> dict` (Task 3)
  - `app.crawler.parser.parse_place_detail_page(html) -> dict | None` (Task 4)
  - `app.db.make_engine`, `app.db.init_db`, `app.db.make_session_factory` (Task 1)
  - `app.models.Restaurant`, `app.models.Broadcast` (Task 1)
- Produces: `app.crawler.run_crawl.run_crawl(session_factory=None) -> None` (CLI entry via `python -m app.crawler.run_crawl`)

- [ ] **Step 1: 실패하는 통합 테스트 작성**

이 테스트는 `fetch_url`을 모킹해 작은 합성 HTML(Task 2~4에서 검증된 실제 CSS 클래스/JSON-LD 구조를 그대로 사용)을 반환하도록 하고, 인메모리 SQLite에 대해 오케스트레이션 전체를 검증한다.

`backend/tests/test_run_crawl.py`:
```python
from unittest.mock import patch

from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool

from app.db import init_db, make_session_factory
from app.models import Restaurant, Broadcast
from app.crawler.run_crawl import run_crawl, BASE_URL

BROADCASTS_HTML = """
<a class="lp-net__card" href="/broadcast/ttoganjib">
  <span class="lp-net__meta"><span class="lp-net__name">또간집</span></span>
</a>
"""

LIST_PAGE_HTML = """
<li><a class="bc-item" href="/place/place-1">
  <span class="bc-item__body">
    <span class="bc-item__name">경양카츠 연남점<span class="bc-item__cat">일식</span></span>
    <span class="bc-item__addr">서울 마포구 연남동 260-29</span>
    <span class="bc-item__meta">
      <span>📞 070-7543-5445</span>
      <span>🕘 월~일 11:30~21:00</span>
    </span>
  </span>
</a></li>
"""

DETAIL_HTML = """
<script type="application/ld+json">
{"@type": "Restaurant", "name": "경양카츠 연남점", "address": "서울 마포구 연남동 260-29",
 "geo": {"latitude": 37.5612032, "longitude": 126.9244277},
 "telephone": "070-7543-5445", "servesCuisine": "일식"}
</script>
"""


def fake_fetch_url(url, **kwargs):
    if url == f"{BASE_URL}/broadcasts":
        return BROADCASTS_HTML
    if url.startswith(f"{BASE_URL}/broadcast/ttoganjib"):
        return LIST_PAGE_HTML
    if url == f"{BASE_URL}/place/place-1":
        return DETAIL_HTML
    raise AssertionError(f"unexpected url: {url}")


def make_in_memory_session_factory():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    init_db(engine)
    return make_session_factory(engine)


def test_run_crawl_populates_restaurants_and_broadcasts():
    session_factory = make_in_memory_session_factory()

    with patch("app.crawler.run_crawl.fetch_url", side_effect=fake_fetch_url), \
         patch("app.crawler.run_crawl.time.sleep"):
        run_crawl(session_factory=session_factory)

    with session_factory() as session:
        restaurant = session.get(Restaurant, "place-1")
        assert restaurant is not None
        assert restaurant.name == "경양카츠 연남점"
        assert restaurant.latitude == 37.5612032
        assert restaurant.longitude == 126.9244277
        assert [b.id for b in restaurant.broadcasts] == ["ttoganjib"]

        broadcast = session.get(Broadcast, "ttoganjib")
        assert broadcast.name == "또간집"


def test_run_crawl_is_idempotent_on_rerun():
    session_factory = make_in_memory_session_factory()

    with patch("app.crawler.run_crawl.fetch_url", side_effect=fake_fetch_url), \
         patch("app.crawler.run_crawl.time.sleep"):
        run_crawl(session_factory=session_factory)
        run_crawl(session_factory=session_factory)

    with session_factory() as session:
        restaurant = session.get(Restaurant, "place-1")
        assert restaurant is not None
        assert len(restaurant.broadcasts) == 1
```

주의: `LIST_PAGE_HTML`에서 `has_next_page`는 `bc-pager__nav[rel='next']`가 없으므로 자동으로 `False`가 되어 페이지네이션 루프가 1페이지 만에 종료된다 — Task 3 파서 로직 그대로 사용.

- [ ] **Step 2: 테스트 실행 → 실패 확인**

Run: `cd backend && pytest tests/test_run_crawl.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.crawler.run_crawl'`

- [ ] **Step 3: 오케스트레이션 구현**

`backend/app/crawler/run_crawl.py`:
```python
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
```

- [ ] **Step 4: 테스트 실행 → 통과 확인**

Run: `cd backend && pytest tests/test_run_crawl.py -v`
Expected: PASS

- [ ] **Step 5: 전체 테스트 스위트 실행**

Run: `cd backend && pytest -v`
Expected: 모든 테스트(Task 1~6) PASS

- [ ] **Step 6: 커밋**

```bash
git add backend/app/crawler/run_crawl.py backend/tests/test_run_crawl.py
git commit -m "feat: add crawler orchestration, upsert logic, and CLI entrypoint"
```

---

## 완료 후 수동 확인 (선택)

실제 matzipmap.com에 대해 전체 크롤링을 한 번 돌려보고 싶다면(네트워크 호출 발생, 프로그램 14개 순회로 수 분 소요될 수 있음):

```bash
cd backend && python -m app.crawler.run_crawl
```

`foodmap.db` (SQLite)가 생성되고 `restaurants`/`broadcasts` 테이블에 데이터가 채워진다.
