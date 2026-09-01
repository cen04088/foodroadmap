# 백엔드 API (카카오 Directions 연동 + 경로-맛집 매칭) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 출발지/도착지를 받아 카카오모빌리티 Directions API로 경로를 구하고, 이미 크롤링되어 DB에 있는 맛집 중 경로상 반경 이내인 것을 찾아 "출발 후 몇 시간 지점"과 함께 반환하는 FastAPI 엔드포인트를 만든다.

**Architecture:** 순수 기하 계산(geo.py) → 카카오 API 클라이언트+파서(kakao/directions.py) → 매칭 알고리즘(matching.py) → DB 후보 조회(repository.py) → 이 넷을 엮는 FastAPI 엔드포인트(api/routes.py) 순으로 계층을 쌓는다. 각 계층은 이전 계층의 출력 타입만 소비하며 독립적으로 테스트한다.

**Tech Stack:** Python 3.11+, FastAPI, requests, SQLAlchemy 2.0(기존 [데이터 파운데이션 계획](2026-09-01-data-foundation.md)에서 구축된 `app.db`/`app.models` 재사용), pytest, httpx(FastAPI TestClient용)

**Spec:** [docs/superpowers/specs/2026-09-01-route-restaurant-service-design.md](../specs/2026-09-01-route-restaurant-service-design.md) — 이 계획은 스펙 §2.3(지도/경로 API), §2.4(반경 기준), §2.5(시간 계산), §3.1(백엔드 컴포넌트), §4(매칭 알고리즘), §5(API 설계), §6(에러 처리 중 카카오 API 관련) 부분을 구현한다.

## Global Constraints

- 카카오 Directions API 응답 스키마는 실제 REST API 키로 라이브 호출해 검증 완료했다(스펙 §2.3). 엔드포인트는 `https://apis-navi.kakaomobility.com/v1/directions`이며 (`/affiliate/v1/...`가 **아님** — 그 경로는 별도 제휴 승인이 필요해 403이 남), 일반 REST API 키만으로 정상 동작한다. 이 계획의 테스트는 실제 검증된 스키마로 만든 합성(synthetic) fixture를 사용한다.
- 카카오 API는 좌표를 `x=경도, y=위도` 순서로 받는다. 이 서비스의 공개 API(`origin`/`destination` 쿼리 파라미터)는 스펙 §5에 따라 `lat,lng` 순서를 유지하고, 카카오 API를 호출하는 지점에서만 `lng,lat`로 변환한다.
- 카카오 API 응답은 vertex 단위가 아니라 road(도로 구간) 단위로만 누적 거리/시간을 제공한다. vertex별 누적값은 road 내부 haversine 세그먼트 길이 비율로 그 road의 duration을 배분해 직접 계산한다(스펙 §4).
- "경로상 맛집" 반경은 기본값 2km이며, API의 `radius_km` 쿼리 파라미터로 오버라이드 가능하다(스펙 §2.4, §5).
- "출발 후 몇 시간 거리"는 맛집에서 경로선까지 가장 가까운 지점의 누적 주행시간이며, 맛집 방문을 위한 우회 시간은 계산하지 않는다(스펙 §2.5).
- 좌표(`latitude`/`longitude`)가 없는 맛집(크롤링 시 상세 페이지 파싱에 실패한 레코드)은 매칭 대상에서 제외한다.
- 카카오 API 키는 `KAKAO_REST_API_KEY` 환경변수로 주입한다. 미설정 시 명확한 에러를 반환한다.
- DB 접근은 [데이터 파운데이션 계획](2026-09-01-data-foundation.md)에서 만든 `app.db.make_engine`/`init_db`/`make_session_factory`와 `app.models.Restaurant`/`Broadcast`를 그대로 재사용한다. 이 계획에서 DB 스키마를 변경하지 않는다.

---

## 프로젝트 구조 (기존 backend/ 위에 추가)

```
backend/
  requirements.txt          # fastapi, uvicorn, httpx 추가 (Task 5)
  app/
    geo.py                  # 신규 — 순수 기하 함수
    config.py                # 신규 — 환경변수 기반 설정
    kakao/
      __init__.py             # 신규
      directions.py            # 신규 — 카카오 Directions API 클라이언트 + 파서
    matching.py               # 신규 — 경로-맛집 매칭 알고리즘
    repository.py              # 신규 — DB 후보 조회
    api/
      __init__.py               # 신규
      main.py                    # 신규 — FastAPI 앱
      routes.py                  # 신규 — GET /api/route-restaurants 엔드포인트
  tests/
    test_geo.py                # 신규
    test_kakao_directions.py    # 신규
    test_matching.py             # 신규
    test_repository.py            # 신규
    test_api_route_restaurants.py  # 신규
```

---

### Task 1: 순수 기하 함수 (haversine, 점-세그먼트 투영, 바운딩박스)

**Files:**
- Create: `backend/app/geo.py`
- Test: `backend/tests/test_geo.py`

**Interfaces:**
- Consumes: 없음
- Produces:
  - `app.geo.haversine_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float`
  - `app.geo.project_point_onto_segment(point: tuple[float, float], seg_start: tuple[float, float], seg_end: tuple[float, float]) -> tuple[float, float]` — 반환값 `(distance_km, t)`. `point`/`seg_start`/`seg_end`는 `(lat, lng)` 튜플. `t`는 `seg_start`→`seg_end` 사이에서 최근접점의 보간 비율(0~1로 클램프됨).
  - `app.geo.bounding_box_with_margin(points: list[dict], margin_km: float) -> tuple[float, float, float, float]` — 반환값 `(min_lat, max_lat, min_lng, max_lng)`. `points`의 각 원소는 `{"lat": float, "lng": float, ...}` 형태(다른 키가 있어도 무시).

- [ ] **Step 1: 실패하는 테스트 작성**

`backend/tests/test_geo.py`:
```python
import math

import pytest

from app.geo import haversine_km, project_point_onto_segment, bounding_box_with_margin


def test_haversine_km_zero_for_same_point():
    assert haversine_km(37.5, 127.0, 37.5, 127.0) == pytest.approx(0.0, abs=1e-9)


def test_haversine_km_known_distance():
    # 서울시청(37.5665, 126.9780) ~ 강남역(37.4979, 127.0276) 대략 8.4km 안팎
    distance = haversine_km(37.5665, 126.9780, 37.4979, 127.0276)
    assert 8.0 < distance < 9.0


def test_project_point_onto_segment_on_the_line_midpoint():
    distance_km, t = project_point_onto_segment(
        point=(37.5, 127.005),
        seg_start=(37.5, 127.0),
        seg_end=(37.5, 127.01),
    )
    assert distance_km == pytest.approx(0.0, abs=1e-6)
    assert t == pytest.approx(0.5, abs=1e-3)


def test_project_point_onto_segment_beyond_segment_end_clamps_to_endpoint():
    distance_km, t = project_point_onto_segment(
        point=(37.5, 127.02),
        seg_start=(37.5, 127.0),
        seg_end=(37.5, 127.01),
    )
    assert t == pytest.approx(1.0, abs=1e-9)
    expected_distance = haversine_km(37.5, 127.02, 37.5, 127.01)
    assert distance_km == pytest.approx(expected_distance, rel=1e-3)


def test_project_point_onto_segment_perpendicular_offset():
    # seg_start->seg_end runs east along the same latitude; point is ~1km north of the midpoint
    distance_km, t = project_point_onto_segment(
        point=(37.509, 127.005),
        seg_start=(37.5, 127.0),
        seg_end=(37.5, 127.01),
    )
    assert 0.9 < distance_km < 1.1
    assert t == pytest.approx(0.5, abs=1e-2)


def test_project_point_onto_segment_degenerate_segment():
    # seg_start == seg_end: distance is just point-to-point, t is 0
    distance_km, t = project_point_onto_segment(
        point=(37.51, 127.0),
        seg_start=(37.5, 127.0),
        seg_end=(37.5, 127.0),
    )
    assert distance_km == pytest.approx(haversine_km(37.51, 127.0, 37.5, 127.0), rel=1e-6)
    assert t == 0.0


def test_bounding_box_with_margin_expands_by_margin():
    points = [
        {"lat": 37.50, "lng": 127.00},
        {"lat": 37.55, "lng": 127.05},
    ]
    min_lat, max_lat, min_lng, max_lng = bounding_box_with_margin(points, margin_km=2.0)

    assert min_lat < 37.50
    assert max_lat > 37.55
    assert min_lng < 127.00
    assert max_lng > 127.05
    # margin in degrees latitude should be roughly margin_km / 111
    assert (37.50 - min_lat) == pytest.approx(2.0 / 111.0, rel=0.05)
```

- [ ] **Step 2: 테스트 실행 → 실패 확인**

Run: `cd backend && pytest tests/test_geo.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.geo'`

- [ ] **Step 3: 구현**

`backend/app/geo.py`:
```python
import math

EARTH_RADIUS_KM = 6371.0088


def haversine_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lng2 - lng1)

    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return 2 * EARTH_RADIUS_KM * math.asin(math.sqrt(a))


def _to_local_xy_km(lat: float, lng: float, ref_lat: float) -> tuple[float, float]:
    x = math.radians(lng) * math.cos(math.radians(ref_lat)) * EARTH_RADIUS_KM
    y = math.radians(lat) * EARTH_RADIUS_KM
    return x, y


def project_point_onto_segment(
    point: tuple[float, float],
    seg_start: tuple[float, float],
    seg_end: tuple[float, float],
) -> tuple[float, float]:
    ref_lat = seg_start[0]

    px, py = _to_local_xy_km(point[0], point[1], ref_lat)
    ax, ay = _to_local_xy_km(seg_start[0], seg_start[1], ref_lat)
    bx, by = _to_local_xy_km(seg_end[0], seg_end[1], ref_lat)

    abx, aby = bx - ax, by - ay
    ab_len_sq = abx * abx + aby * aby

    if ab_len_sq == 0:
        t = 0.0
    else:
        apx, apy = px - ax, py - ay
        t = max(0.0, min(1.0, (apx * abx + apy * aby) / ab_len_sq))

    closest_x, closest_y = ax + t * abx, ay + t * aby
    distance_km = math.hypot(px - closest_x, py - closest_y)
    return distance_km, t


def bounding_box_with_margin(points: list[dict], margin_km: float) -> tuple[float, float, float, float]:
    lats = [p["lat"] for p in points]
    lngs = [p["lng"] for p in points]
    avg_lat = sum(lats) / len(lats)

    lat_margin_deg = margin_km / 111.0
    lng_margin_deg = margin_km / (111.320 * max(math.cos(math.radians(avg_lat)), 1e-9))

    return (
        min(lats) - lat_margin_deg,
        max(lats) + lat_margin_deg,
        min(lngs) - lng_margin_deg,
        max(lngs) + lng_margin_deg,
    )
```

- [ ] **Step 4: 테스트 실행 → 통과 확인**

Run: `cd backend && pytest tests/test_geo.py -v`
Expected: PASS

- [ ] **Step 5: 커밋**

```bash
git add backend/app/geo.py backend/tests/test_geo.py
git commit -m "feat: add pure geometry helpers for route-restaurant matching"
```

---

### Task 2: 카카오 Directions API 클라이언트 + 파서

**Files:**
- Create: `backend/app/config.py`
- Create: `backend/app/kakao/__init__.py`
- Create: `backend/app/kakao/directions.py`
- Test: `backend/tests/test_kakao_directions.py`

**Interfaces:**
- Consumes: `app.geo.haversine_km` (Task 1)
- Produces:
  - `app.config.get_kakao_api_key() -> str` (미설정 시 `app.config.MissingKakaoApiKeyError` 발생)
  - `app.kakao.directions.KakaoDirectionsError(Exception)`
  - `app.kakao.directions.fetch_route(origin_lat: float, origin_lng: float, dest_lat: float, dest_lng: float, api_key: str, *, timeout: float = 10.0) -> dict` — 카카오 API 원본 JSON 응답(dict)을 그대로 반환. 실패 시 `KakaoDirectionsError` 발생.
  - `app.kakao.directions.parse_route_points(response: dict) -> list[dict]` — 각 원소 `{"lat": float, "lng": float, "cumulative_distance_m": float, "cumulative_time_sec": float}`. `routes`가 없거나 `result_code != 0`이면 `KakaoDirectionsError` 발생.
  - `app.kakao.directions.parse_route_summary(response: dict) -> dict` — `{"total_distance_m": int, "total_duration_sec": int}` (`routes[0].summary.distance`/`duration` 그대로).

- [ ] **Step 1: 실패하는 테스트 작성**

`backend/tests/test_kakao_directions.py`:
```python
from unittest.mock import Mock, patch

import pytest
import requests

from app.geo import haversine_km
from app.kakao.directions import (
    KakaoDirectionsError,
    fetch_route,
    parse_route_points,
    parse_route_summary,
)

# 실제 카카오모빌리티 REST API 키로 라이브 호출해(서울시청→강남역, 2026-09-01) 응답
# 구조를 검증한 뒤, 그 구조를 그대로 반영해 만든 합성 응답 (좌표/거리값은 테스트용으로 단순화).
FAKE_RESPONSE = {
    "trans_id": "fake-trans-id",
    "routes": [
        {
            "result_code": 0,
            "result_msg": "",
            "summary": {
                "origin": {"name": "", "x": 127.0, "y": 37.5},
                "destination": {"name": "", "x": 127.1, "y": 37.6},
                "distance": 15000,
                "duration": 1200,
            },
            "sections": [
                {
                    "distance": 15000,
                    "duration": 1200,
                    "roads": [
                        {
                            "name": "Road A",
                            "distance": 10000,
                            "duration": 800,
                            "traffic_speed": 40.0,
                            "traffic_state": 1,
                            "vertexes": [127.0, 37.5, 127.05, 37.55],
                        },
                        {
                            "name": "Road B",
                            "distance": 5000,
                            "duration": 400,
                            "traffic_speed": 40.0,
                            "traffic_state": 1,
                            "vertexes": [127.05, 37.55, 127.1, 37.6],
                        },
                    ],
                }
            ],
        }
    ],
}


def test_fetch_route_returns_json_and_passes_correct_params():
    fake_response = Mock()
    fake_response.raise_for_status = Mock()
    fake_response.json = Mock(return_value=FAKE_RESPONSE)

    with patch("app.kakao.directions.requests.get", return_value=fake_response) as mock_get:
        result = fetch_route(37.5, 127.0, 37.6, 127.1, api_key="test-key")

    assert result == FAKE_RESPONSE
    mock_get.assert_called_once()
    _, kwargs = mock_get.call_args
    assert kwargs["params"]["origin"] == "127.0,37.5"
    assert kwargs["params"]["destination"] == "127.1,37.6"
    assert kwargs["headers"]["Authorization"] == "KakaoAK test-key"


def test_fetch_route_raises_kakao_directions_error_on_request_failure():
    with patch("app.kakao.directions.requests.get", side_effect=requests.ConnectionError("boom")):
        with pytest.raises(KakaoDirectionsError):
            fetch_route(37.5, 127.0, 37.6, 127.1, api_key="test-key")


def test_parse_route_summary_extracts_totals():
    summary = parse_route_summary(FAKE_RESPONSE)
    assert summary == {"total_distance_m": 15000, "total_duration_sec": 1200}


def test_parse_route_points_accumulates_distance_and_time_across_roads():
    points = parse_route_points(FAKE_RESPONSE)

    assert len(points) == 3
    assert points[0] == {"lat": 37.5, "lng": 127.0, "cumulative_distance_m": 0.0, "cumulative_time_sec": 0.0}

    # Road A has a single segment, so it gets 100% of Road A's duration (800s).
    assert points[1]["lat"] == pytest.approx(37.55)
    assert points[1]["lng"] == pytest.approx(127.05)
    assert points[1]["cumulative_time_sec"] == pytest.approx(800.0)
    expected_seg1_m = haversine_km(37.5, 127.0, 37.55, 127.05) * 1000
    assert points[1]["cumulative_distance_m"] == pytest.approx(expected_seg1_m)

    # Road B has a single segment too, gets 100% of Road B's duration (400s) on top.
    assert points[2]["lat"] == pytest.approx(37.6)
    assert points[2]["lng"] == pytest.approx(127.1)
    assert points[2]["cumulative_time_sec"] == pytest.approx(1200.0)
    expected_seg2_m = haversine_km(37.55, 127.05, 37.6, 127.1) * 1000
    assert points[2]["cumulative_distance_m"] == pytest.approx(expected_seg1_m + expected_seg2_m)


def test_parse_route_points_raises_when_no_routes():
    with pytest.raises(KakaoDirectionsError):
        parse_route_points({"routes": []})


def test_parse_route_points_raises_when_result_code_nonzero():
    bad_response = {
        "routes": [{"result_code": 1, "result_msg": "경로를 찾을 수 없습니다", "sections": []}]
    }
    with pytest.raises(KakaoDirectionsError):
        parse_route_points(bad_response)
```

- [ ] **Step 2: 테스트 실행 → 실패 확인**

Run: `cd backend && pytest tests/test_kakao_directions.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.kakao'`

- [ ] **Step 3: 구현**

`backend/app/config.py`:
```python
import os


class MissingKakaoApiKeyError(RuntimeError):
    pass


def get_kakao_api_key() -> str:
    api_key = os.environ.get("KAKAO_REST_API_KEY")
    if not api_key:
        raise MissingKakaoApiKeyError("KAKAO_REST_API_KEY environment variable is not set")
    return api_key
```

`backend/app/kakao/__init__.py` (빈 파일)

`backend/app/kakao/directions.py`:
```python
import requests

from app.geo import haversine_km

KAKAO_DIRECTIONS_URL = "https://apis-navi.kakaomobility.com/v1/directions"


class KakaoDirectionsError(Exception):
    pass


def fetch_route(
    origin_lat: float,
    origin_lng: float,
    dest_lat: float,
    dest_lng: float,
    api_key: str,
    *,
    timeout: float = 10.0,
) -> dict:
    params = {
        "origin": f"{origin_lng},{origin_lat}",
        "destination": f"{dest_lng},{dest_lat}",
    }
    headers = {"Authorization": f"KakaoAK {api_key}"}

    try:
        response = requests.get(KAKAO_DIRECTIONS_URL, params=params, headers=headers, timeout=timeout)
        response.raise_for_status()
    except requests.RequestException as exc:
        raise KakaoDirectionsError(f"Kakao Directions API request failed: {exc}") from exc

    return response.json()


def parse_route_summary(response: dict) -> dict:
    route = _first_route(response)
    summary = route.get("summary", {})
    return {
        "total_distance_m": summary.get("distance"),
        "total_duration_sec": summary.get("duration"),
    }


def parse_route_points(response: dict) -> list[dict]:
    route = _first_route(response)

    points: list[dict] = []
    cumulative_distance_m = 0.0
    cumulative_time_sec = 0.0

    for section in route.get("sections", []):
        for road in section.get("roads", []):
            vertexes = road.get("vertexes") or []
            coords = list(zip(vertexes[0::2], vertexes[1::2]))  # (lng, lat) pairs
            if len(coords) < 2:
                continue

            road_duration_sec = road.get("duration", 0)

            seg_lengths_m = []
            for (lng1, lat1), (lng2, lat2) in zip(coords, coords[1:]):
                seg_lengths_m.append(haversine_km(lat1, lng1, lat2, lng2) * 1000)
            total_len_m = sum(seg_lengths_m)

            if not points:
                lng0, lat0 = coords[0]
                points.append(
                    {
                        "lat": lat0,
                        "lng": lng0,
                        "cumulative_distance_m": 0.0,
                        "cumulative_time_sec": 0.0,
                    }
                )

            running_len_m = 0.0
            for (lng, lat), seg_len_m in zip(coords[1:], seg_lengths_m):
                running_len_m += seg_len_m
                fraction = (running_len_m / total_len_m) if total_len_m > 0 else 1.0
                points.append(
                    {
                        "lat": lat,
                        "lng": lng,
                        "cumulative_distance_m": cumulative_distance_m + running_len_m,
                        "cumulative_time_sec": cumulative_time_sec + fraction * road_duration_sec,
                    }
                )

            cumulative_distance_m += total_len_m
            cumulative_time_sec += road_duration_sec

    return points


def _first_route(response: dict) -> dict:
    routes = response.get("routes") or []
    if not routes:
        raise KakaoDirectionsError("Kakao Directions API returned no routes")

    route = routes[0]
    if route.get("result_code", 0) != 0:
        raise KakaoDirectionsError(f"Kakao Directions API error: {route.get('result_msg')}")

    return route
```

- [ ] **Step 4: 테스트 실행 → 통과 확인**

Run: `cd backend && pytest tests/test_kakao_directions.py -v`
Expected: PASS

- [ ] **Step 5: 커밋**

```bash
git add backend/app/config.py backend/app/kakao/__init__.py backend/app/kakao/directions.py backend/tests/test_kakao_directions.py
git commit -m "feat: add Kakao Directions API client and route-point parser"
```

---

### Task 3: 경로-맛집 매칭 알고리즘

**Files:**
- Create: `backend/app/matching.py`
- Test: `backend/tests/test_matching.py`

**Interfaces:**
- Consumes: `app.geo.project_point_onto_segment` (Task 1), `app.models.Restaurant` (데이터 파운데이션 계획)
- Produces:
  - `app.matching.RestaurantMatch` — dataclass, 필드 `restaurant`(Restaurant 인스턴스), `distance_from_route_km: float`, `cumulative_time_sec: float`
  - `app.matching.match_restaurants_to_route(route_points: list[dict], candidates: list[Restaurant], radius_km: float) -> list[RestaurantMatch]` — `route_points`가 2개 미만이면 빈 리스트 반환. 반환값은 `cumulative_time_sec` 오름차순 정렬.

- [ ] **Step 1: 실패하는 테스트 작성**

`backend/tests/test_matching.py`:
```python
import pytest

from app.matching import match_restaurants_to_route
from app.models import Restaurant

ROUTE_POINTS = [
    {"lat": 37.50, "lng": 127.00, "cumulative_distance_m": 0.0, "cumulative_time_sec": 0.0},
    {"lat": 37.55, "lng": 127.05, "cumulative_distance_m": 7000.0, "cumulative_time_sec": 600.0},
    {"lat": 37.60, "lng": 127.10, "cumulative_distance_m": 14000.0, "cumulative_time_sec": 1200.0},
]


def make_restaurant(id_, lat, lng):
    return Restaurant(id=id_, name=f"restaurant-{id_}", latitude=lat, longitude=lng)


def test_match_restaurants_to_route_includes_nearby_and_excludes_far():
    near = make_restaurant("near", 37.55, 127.051)  # essentially on the second point
    far = make_restaurant("far", 38.5, 128.5)

    matches = match_restaurants_to_route(ROUTE_POINTS, [near, far], radius_km=2.0)

    matched_ids = {m.restaurant.id for m in matches}
    assert "near" in matched_ids
    assert "far" not in matched_ids


def test_match_restaurants_to_route_interpolates_cumulative_time_near_midpoint():
    # Sits almost exactly at the first route point, so its time should be ~0s, not ~600s or ~1200s.
    at_start = make_restaurant("start", 37.50, 127.001)

    matches = match_restaurants_to_route(ROUTE_POINTS, [at_start], radius_km=2.0)

    assert len(matches) == 1
    assert matches[0].cumulative_time_sec == pytest.approx(0.0, abs=60.0)


def test_match_restaurants_to_route_skips_restaurants_without_coordinates():
    no_coords = Restaurant(id="no-coords", name="no coords", latitude=None, longitude=None)

    matches = match_restaurants_to_route(ROUTE_POINTS, [no_coords], radius_km=2.0)

    assert matches == []


def test_match_restaurants_to_route_sorts_by_cumulative_time_ascending():
    late = make_restaurant("late", 37.60, 127.101)
    early = make_restaurant("early", 37.50, 127.001)

    matches = match_restaurants_to_route(ROUTE_POINTS, [late, early], radius_km=2.0)

    assert [m.restaurant.id for m in matches] == ["early", "late"]


def test_match_restaurants_to_route_returns_empty_for_degenerate_route():
    near = make_restaurant("near", 37.50, 127.001)

    matches = match_restaurants_to_route([ROUTE_POINTS[0]], [near], radius_km=2.0)

    assert matches == []
```

- [ ] **Step 2: 테스트 실행 → 실패 확인**

Run: `cd backend && pytest tests/test_matching.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.matching'`

- [ ] **Step 3: 구현**

`backend/app/matching.py`:
```python
from dataclasses import dataclass

from app.geo import project_point_onto_segment
from app.models import Restaurant


@dataclass
class RestaurantMatch:
    restaurant: Restaurant
    distance_from_route_km: float
    cumulative_time_sec: float


def match_restaurants_to_route(
    route_points: list[dict],
    candidates: list[Restaurant],
    radius_km: float,
) -> list[RestaurantMatch]:
    if len(route_points) < 2:
        return []

    matches = []

    for restaurant in candidates:
        if restaurant.latitude is None or restaurant.longitude is None:
            continue

        best_distance_km = None
        best_time_sec = None

        for seg_start, seg_end in zip(route_points, route_points[1:]):
            distance_km, t = project_point_onto_segment(
                (restaurant.latitude, restaurant.longitude),
                (seg_start["lat"], seg_start["lng"]),
                (seg_end["lat"], seg_end["lng"]),
            )
            if best_distance_km is None or distance_km < best_distance_km:
                best_distance_km = distance_km
                best_time_sec = seg_start["cumulative_time_sec"] + t * (
                    seg_end["cumulative_time_sec"] - seg_start["cumulative_time_sec"]
                )

        if best_distance_km is not None and best_distance_km <= radius_km:
            matches.append(
                RestaurantMatch(
                    restaurant=restaurant,
                    distance_from_route_km=best_distance_km,
                    cumulative_time_sec=best_time_sec,
                )
            )

    matches.sort(key=lambda m: m.cumulative_time_sec)
    return matches
```

- [ ] **Step 4: 테스트 실행 → 통과 확인**

Run: `cd backend && pytest tests/test_matching.py -v`
Expected: PASS

- [ ] **Step 5: 커밋**

```bash
git add backend/app/matching.py backend/tests/test_matching.py
git commit -m "feat: add route-restaurant matching algorithm"
```

---

### Task 4: DB 후보 조회 (바운딩박스 + 필터)

**Files:**
- Create: `backend/app/repository.py`
- Test: `backend/tests/test_repository.py`

**Interfaces:**
- Consumes: `app.models.Restaurant`, `app.models.Broadcast` (데이터 파운데이션 계획), `app.db.make_engine`/`init_db`/`make_session_factory` (같은 계획, 테스트에서만 사용)
- Produces: `app.repository.query_candidate_restaurants(session: Session, min_lat: float, max_lat: float, min_lng: float, max_lng: float, *, broadcast_slug: str | None = None, category: str | None = None) -> list[Restaurant]` — 좌표가 없는(NULL) 맛집은 항상 제외.

- [ ] **Step 1: 실패하는 테스트 작성**

`backend/tests/test_repository.py`:
```python
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool

from app.db import init_db, make_session_factory
from app.models import Broadcast, Restaurant
from app.repository import query_candidate_restaurants


def make_session_factory_in_memory():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    init_db(engine)
    return make_session_factory(engine)


def seed(session):
    ttoganjib = Broadcast(id="ttoganjib", name="또간집")
    session.add(ttoganjib)

    inside = Restaurant(
        id="inside", name="Inside", latitude=37.55, longitude=127.05, category="한식"
    )
    inside.broadcasts.append(ttoganjib)

    outside = Restaurant(id="outside", name="Outside", latitude=38.5, longitude=128.5, category="한식")
    no_coords = Restaurant(id="no-coords", name="NoCoords", latitude=None, longitude=None)
    wrong_category = Restaurant(
        id="wrong-category", name="WrongCategory", latitude=37.55, longitude=127.05, category="양식"
    )

    session.add_all([inside, outside, no_coords, wrong_category])
    session.commit()


def test_query_candidate_restaurants_filters_by_bounding_box():
    session_factory = make_session_factory_in_memory()
    with session_factory() as session:
        seed(session)

        results = query_candidate_restaurants(session, 37.0, 38.0, 126.5, 127.5)

        ids = {r.id for r in results}
        assert "inside" in ids
        assert "outside" not in ids
        assert "no-coords" not in ids


def test_query_candidate_restaurants_filters_by_category():
    session_factory = make_session_factory_in_memory()
    with session_factory() as session:
        seed(session)

        results = query_candidate_restaurants(session, 37.0, 38.0, 126.5, 127.5, category="한식")

        ids = {r.id for r in results}
        assert "inside" in ids
        assert "wrong-category" not in ids


def test_query_candidate_restaurants_filters_by_broadcast_slug():
    session_factory = make_session_factory_in_memory()
    with session_factory() as session:
        seed(session)

        results = query_candidate_restaurants(
            session, 37.0, 38.0, 126.5, 127.5, broadcast_slug="ttoganjib"
        )

        ids = {r.id for r in results}
        assert ids == {"inside"}
```

- [ ] **Step 2: 테스트 실행 → 실패 확인**

Run: `cd backend && pytest tests/test_repository.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.repository'`

- [ ] **Step 3: 구현**

`backend/app/repository.py`:
```python
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Broadcast, Restaurant


def query_candidate_restaurants(
    session: Session,
    min_lat: float,
    max_lat: float,
    min_lng: float,
    max_lng: float,
    *,
    broadcast_slug: str | None = None,
    category: str | None = None,
) -> list[Restaurant]:
    stmt = select(Restaurant).where(
        Restaurant.latitude.is_not(None),
        Restaurant.longitude.is_not(None),
        Restaurant.latitude.between(min_lat, max_lat),
        Restaurant.longitude.between(min_lng, max_lng),
    )

    if category:
        stmt = stmt.where(Restaurant.category == category)

    if broadcast_slug:
        stmt = stmt.join(Restaurant.broadcasts).where(Broadcast.id == broadcast_slug)

    return list(session.scalars(stmt).unique())
```

- [ ] **Step 4: 테스트 실행 → 통과 확인**

Run: `cd backend && pytest tests/test_repository.py -v`
Expected: PASS

- [ ] **Step 5: 커밋**

```bash
git add backend/app/repository.py backend/tests/test_repository.py
git commit -m "feat: add bounding-box restaurant candidate query"
```

---

### Task 5: FastAPI 엔드포인트 (GET /api/route-restaurants)

**Files:**
- Modify: `backend/requirements.txt`
- Create: `backend/app/api/__init__.py`
- Create: `backend/app/api/main.py`
- Create: `backend/app/api/routes.py`
- Test: `backend/tests/test_api_route_restaurants.py`

**Interfaces:**
- Consumes:
  - `app.config.get_kakao_api_key`, `app.config.MissingKakaoApiKeyError` (Task 2)
  - `app.kakao.directions.fetch_route`, `parse_route_points`, `parse_route_summary`, `KakaoDirectionsError` (Task 2)
  - `app.geo.bounding_box_with_margin` (Task 1)
  - `app.repository.query_candidate_restaurants` (Task 4)
  - `app.matching.match_restaurants_to_route`, `RestaurantMatch` (Task 3)
  - `app.db.make_engine`, `make_session_factory` (데이터 파운데이션 계획)
- Produces: `app.api.main.app` (FastAPI 인스턴스), `app.api.routes.router`, `app.api.routes.get_session` (FastAPI dependency, 다른 계획/테스트에서 override 가능)

- [ ] **Step 1: 의존성 추가**

`pip show fastapi uvicorn httpx` 로 이미 설치되어 있는지 확인하고, 없다면 `pip install fastapi uvicorn httpx`로 설치한 뒤 `pip show fastapi uvicorn httpx`로 정확한 설치 버전을 확인한다. **데이터 파운데이션 계획의 최종 리뷰에서 `requirements.txt`에 실제 설치되지 않는 버전을 핀 고정했다가 지적받은 적이 있으므로, 반드시 이 환경에 실제로 설치된 버전으로 핀을 맞출 것** — 아래는 참고용 초안이며 실제 설치 버전과 다르면 실제 버전으로 교체한다:

`backend/requirements.txt`에 다음 줄을 추가한다 (기존 내용 유지):
```
fastapi==0.115.0
uvicorn==0.32.0
httpx==0.27.2
```

`pip install -r backend/requirements.txt` 로 설치가 정상적으로 되는지 확인한다.

- [ ] **Step 2: 실패하는 테스트 작성**

`backend/tests/test_api_route_restaurants.py`:
```python
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool

from app.api.main import app
from app.api.routes import get_session
from app.db import init_db, make_session_factory
from app.models import Broadcast, Restaurant

# 실제 카카오모빌리티 API로 라이브 검증된 구조의 합성 응답 (test_kakao_directions.py의 FAKE_RESPONSE와 동일한 구조).
FAKE_KAKAO_RESPONSE = {
    "routes": [
        {
            "result_code": 0,
            "result_msg": "",
            "summary": {"distance": 15000, "duration": 1200},
            "sections": [
                {
                    "distance": 15000,
                    "duration": 1200,
                    "roads": [
                        {
                            "name": "Road A",
                            "distance": 15000,
                            "duration": 1200,
                            "vertexes": [127.0, 37.5, 127.05, 37.55, 127.1, 37.6],
                        }
                    ],
                }
            ],
        }
    ]
}


def make_test_session_factory():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    init_db(engine)
    return make_session_factory(engine)


def seed(session_factory):
    with session_factory() as session:
        ttoganjib = Broadcast(id="ttoganjib", name="또간집")
        session.add(ttoganjib)

        near = Restaurant(
            id="near", name="Near Restaurant", latitude=37.55, longitude=127.05, category="한식"
        )
        near.broadcasts.append(ttoganjib)

        far = Restaurant(id="far", name="Far Restaurant", latitude=38.5, longitude=128.5, category="한식")

        session.add_all([near, far])
        session.commit()


def override_get_session_factory(session_factory):
    def _override():
        with session_factory() as session:
            yield session

    return _override


def test_get_route_restaurants_returns_nearby_restaurant_with_expected_shape(monkeypatch):
    monkeypatch.setenv("KAKAO_REST_API_KEY", "test-key")
    monkeypatch.setattr(
        "app.api.routes.fetch_route", lambda *args, **kwargs: FAKE_KAKAO_RESPONSE
    )

    session_factory = make_test_session_factory()
    seed(session_factory)
    app.dependency_overrides[get_session] = override_get_session_factory(session_factory)

    client = TestClient(app)
    try:
        response = client.get(
            "/api/route-restaurants",
            params={"origin": "37.5,127.0", "destination": "37.6,127.1"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    body = response.json()

    assert body["route"]["total_distance_m"] == 15000
    assert body["route"]["total_duration_sec"] == 1200

    names = [r["name"] for r in body["restaurants"]]
    assert "Near Restaurant" in names
    assert "Far Restaurant" not in names

    near_result = next(r for r in body["restaurants"] if r["name"] == "Near Restaurant")
    assert near_result["broadcasts"] == ["또간집"]
    assert "distance_from_route_km" in near_result
    assert "cumulative_time_sec" in near_result


def test_get_route_restaurants_filters_by_broadcast_query_param(monkeypatch):
    monkeypatch.setenv("KAKAO_REST_API_KEY", "test-key")
    monkeypatch.setattr(
        "app.api.routes.fetch_route", lambda *args, **kwargs: FAKE_KAKAO_RESPONSE
    )

    session_factory = make_test_session_factory()
    seed(session_factory)
    app.dependency_overrides[get_session] = override_get_session_factory(session_factory)

    client = TestClient(app)
    try:
        response = client.get(
            "/api/route-restaurants",
            params={
                "origin": "37.5,127.0",
                "destination": "37.6,127.1",
                "broadcast": "no-such-program",
            },
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["restaurants"] == []


def test_get_route_restaurants_returns_400_for_malformed_origin(monkeypatch):
    monkeypatch.setenv("KAKAO_REST_API_KEY", "test-key")

    client = TestClient(app)
    response = client.get(
        "/api/route-restaurants",
        params={"origin": "not-a-coordinate", "destination": "37.6,127.1"},
    )

    assert response.status_code == 400


def test_get_route_restaurants_returns_500_when_kakao_api_key_missing(monkeypatch):
    monkeypatch.delenv("KAKAO_REST_API_KEY", raising=False)

    client = TestClient(app)
    response = client.get(
        "/api/route-restaurants",
        params={"origin": "37.5,127.0", "destination": "37.6,127.1"},
    )

    assert response.status_code == 500


def test_get_route_restaurants_returns_502_when_kakao_api_fails(monkeypatch):
    monkeypatch.setenv("KAKAO_REST_API_KEY", "test-key")

    def raise_error(*args, **kwargs):
        from app.kakao.directions import KakaoDirectionsError

        raise KakaoDirectionsError("boom")

    monkeypatch.setattr("app.api.routes.fetch_route", raise_error)

    client = TestClient(app)
    response = client.get(
        "/api/route-restaurants",
        params={"origin": "37.5,127.0", "destination": "37.6,127.1"},
    )

    assert response.status_code == 502
```

- [ ] **Step 3: 테스트 실행 → 실패 확인**

Run: `cd backend && pytest tests/test_api_route_restaurants.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.api'`

- [ ] **Step 4: 구현**

`backend/app/api/__init__.py` (빈 파일)

`backend/app/api/routes.py`:
```python
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.config import MissingKakaoApiKeyError, get_kakao_api_key
from app.db import make_engine, make_session_factory
from app.geo import bounding_box_with_margin
from app.kakao.directions import KakaoDirectionsError, fetch_route, parse_route_points, parse_route_summary
from app.matching import RestaurantMatch, match_restaurants_to_route
from app.repository import query_candidate_restaurants

router = APIRouter()

DEFAULT_RADIUS_KM = 2.0

_ENGINE = make_engine()
_SESSION_FACTORY = make_session_factory(_ENGINE)


def get_session():
    with _SESSION_FACTORY() as session:
        yield session


def _parse_lat_lng(value: str) -> tuple[float, float]:
    try:
        lat_str, lng_str = value.split(",")
        return float(lat_str), float(lng_str)
    except (ValueError, AttributeError) as exc:
        raise HTTPException(status_code=400, detail=f"잘못된 좌표 형식입니다: {value}") from exc


def _serialize_match(match: RestaurantMatch) -> dict:
    restaurant = match.restaurant
    return {
        "id": restaurant.id,
        "name": restaurant.name,
        "category": restaurant.category,
        "address": restaurant.address,
        "latitude": restaurant.latitude,
        "longitude": restaurant.longitude,
        "phone": restaurant.phone,
        "hours": restaurant.hours,
        "distance_from_route_km": round(match.distance_from_route_km, 3),
        "cumulative_time_sec": round(match.cumulative_time_sec),
        "broadcasts": [b.name for b in restaurant.broadcasts],
    }


@router.get("/api/route-restaurants")
def get_route_restaurants(
    origin: str = Query(..., description="lat,lng"),
    destination: str = Query(..., description="lat,lng"),
    radius_km: float = Query(DEFAULT_RADIUS_KM, gt=0),
    broadcast: str | None = Query(None),
    category: str | None = Query(None),
    session: Session = Depends(get_session),
):
    origin_lat, origin_lng = _parse_lat_lng(origin)
    dest_lat, dest_lng = _parse_lat_lng(destination)

    try:
        api_key = get_kakao_api_key()
    except MissingKakaoApiKeyError as exc:
        raise HTTPException(status_code=500, detail="서버 설정 오류: 카카오 API 키가 설정되지 않았습니다") from exc

    try:
        raw_response = fetch_route(origin_lat, origin_lng, dest_lat, dest_lng, api_key)
        route_points = parse_route_points(raw_response)
        route_summary = parse_route_summary(raw_response)
    except KakaoDirectionsError as exc:
        raise HTTPException(status_code=502, detail=f"경로를 가져오지 못했습니다: {exc}") from exc

    if len(route_points) < 2:
        raise HTTPException(status_code=502, detail="경로를 계산할 수 없습니다")

    min_lat, max_lat, min_lng, max_lng = bounding_box_with_margin(route_points, radius_km)
    candidates = query_candidate_restaurants(
        session, min_lat, max_lat, min_lng, max_lng, broadcast_slug=broadcast, category=category
    )
    matches = match_restaurants_to_route(route_points, candidates, radius_km)

    return {
        "route": {
            "total_distance_m": route_summary["total_distance_m"],
            "total_duration_sec": route_summary["total_duration_sec"],
            "points": route_points,
        },
        "restaurants": [_serialize_match(m) for m in matches],
    }
```

`backend/app/api/main.py`:
```python
from fastapi import FastAPI

from app.api.routes import router

app = FastAPI(title="foodmap route-restaurants API")
app.include_router(router)
```

- [ ] **Step 5: 테스트 실행 → 통과 확인**

Run: `cd backend && pytest tests/test_api_route_restaurants.py -v`
Expected: PASS

- [ ] **Step 6: 전체 테스트 스위트 실행**

Run: `cd backend && pytest -v`
Expected: 이 계획의 모든 테스트(Task 1~5)와 데이터 파운데이션 계획의 기존 테스트가 모두 PASS

- [ ] **Step 7: 커밋**

```bash
git add backend/requirements.txt backend/app/api/__init__.py backend/app/api/main.py backend/app/api/routes.py backend/tests/test_api_route_restaurants.py
git commit -m "feat: add GET /api/route-restaurants FastAPI endpoint"
```

---

## 완료 후 수동 확인

카카오 Directions API 자체(`/v1/directions`, 일반 REST API 키)는 이미 실제 키로 라이브 검증
완료했다(스펙 §2.3). 아래는 이 계획으로 만든 엔드투엔드 서버가 실제 크롤링 DB와 함께
정상 동작하는지 확인하는 절차다.

```bash
cd backend
export KAKAO_REST_API_KEY=... # 실제 키
export DATABASE_URL=sqlite:///./foodmap.db  # 크롤러가 채워둔 DB
uvicorn app.api.main:app --reload
```
다른 터미널에서:
```bash
curl "http://127.0.0.1:8000/api/route-restaurants?origin=37.5665,126.9780&destination=35.1796,129.0756"
```
실제 크롤링된 DB(`foodmap.db`)를 사용해 응답에 맛집이 정상적으로 포함되는지 확인한다.
