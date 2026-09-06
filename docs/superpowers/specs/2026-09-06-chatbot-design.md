# 맛집 챗봇 — 설계 문서

- 작성일: 2026-09-06
- 상태: 승인됨 (구현 계획 수립 대기)
- 상위 스펙: [2026-09-01-route-restaurant-service-design.md](2026-09-01-route-restaurant-service-design.md), [2026-09-03-frontend-design.md](2026-09-03-frontend-design.md)

## 1. 범위

우측 하단 플로팅 버튼으로 여는 대화형 챗봇. 목표는 "속도와 정확성" — 이 문서에서 그 두 목표를 구체적인 아키텍처 선택으로 번역한다.

챗봇이 답변하는 것:

- **자연어 맛집 추천/검색** — 방송·업종·지역 조건을 자연어로 걸어 찾기
- **현재 화면 맥락 인식** — 사용자가 이미 경로를 검색했거나 지도를 특정 지역으로 옮겨놓은 상태면 그 결과/영역 안에서 답변
- **계산형 조건** — "지금 영업 중", "여기서 가까운" 같이 실시간 계산이 필요한 조건

범위 밖 (§8 참고):

- 리뷰/방송 소개 기반 답변 — matzipmap.com에 그런 콘텐츠 자체가 없음 (§2 참고)
- 외부 리뷰 플랫폼(네이버/카카오 등) 크롤링
- 대화 히스토리 영속화, 로그인 연동

## 2. 사전 조사 — RAG 소스가 될 수 있는 데이터

구현 전에 matzipmap.com의 실제 페이지 구조를 확인했다 (`backend/tests/fixtures/place_detail.html`, `broadcasts_list.html`).

| 후보 | 결과 |
|---|---|
| 방송 에피소드 소개/설명 | 없음 — 방송 목록 페이지는 "어떻게 쓰는지" 안내 문구 + 맛집 카드(이름/주소/방송수)뿐 |
| 사용자 리뷰/댓글 (`.comments`) | 존재하지만 확인한 샘플은 댓글 0개 — 신뢰할 만한 데이터소스로 보기 어려움 |
| **메뉴 (`.pd-menu`)** | **있음** — 실제 메뉴 이름 + 가격 (예: "크림카츠 16,400원"). 지금 크롤러가 전혀 수집하지 않음 |

**결론**: 리뷰·방송소개는 소스가 없어 이번 범위에서 제외한다. 대신 메뉴 데이터를 새로 수집해 챗봇의 부가 검색 대상으로 삼는다 (§4).

**미해결 리스크**: 메뉴 섹션 하단에 "외 N개"로 표시가 잘리는 경우를 확인했다. 이게 정적 HTML에 이미 다 들어있고 "더보기"가 단순 CSS 토글인지, 아니면 별도 XHR로 추가 로드되는지 fixture만으로는 확정할 수 없다 — 구현 착수 시 실제 페이지에서 확인해야 한다 (후자라면 크롤러가 그 요청도 따라가야 함).

## 3. 왜 벡터 임베딩이 아닌가

기존 필드(이름/주소/업종/방송태그)는 구조화 데이터라 임베딩 유사도 검색을 쓰면 "흑백요리사" 같은 정확한 태그 매칭이 의미적 유사도로 흐려지고, 3,400여 건 규모에서는 인덱스된 SQL 조회가 벡터 검색보다 빠르고 정확하다.

메뉴 데이터(§2)가 새로 생겨도 마찬가지 논리를 적용한다: "짬뽕" 같은 검색은 오타·부분 일치 정도만 잡으면 충분하고, 이 정도는 **PostgreSQL `pg_trgm` 트라이그램 유사도 검색**으로 임베딩 파이프라인 없이 해결된다 (신규 인프라 없음, 크롤링마다 임베딩 API 호출/비용 없음, 인덱스 하나만 추가). "매콤한 거 뭐 있어" 같은 의미 기반 질의까지 지원하려면 결국 임베딩이 필요해질 수 있는데, 이건 트라이그램 검색으로 실제 부족함이 드러난 뒤에 붙일 확장 포인트로 남겨둔다 (YAGNI).

**즉 이 프로젝트의 "RAG"는 벡터 검색이 아니라 "LLM이 조건을 해석 → 백엔드가 정확한 쿼리(SQL/트라이그램/계산)를 실행 → 결과만 LLM에 근거로 제공"이다.** 답변에 나오는 모든 사실은 실제 쿼리 결과에서만 나온다.

## 4. 데이터 모델 변경

새 테이블:

```python
class MenuItem(Base):
    __tablename__ = "menu_items"

    id = Column(Integer, primary_key=True, autoincrement=True)
    restaurant_id = Column(String, ForeignKey("restaurants.id"), nullable=False, index=True)
    name = Column(String, nullable=False)
    price_won = Column(Integer, nullable=True)  # 가격 미표시 메뉴 대비 nullable
```

- `backend/app/crawler/parser.py`의 `parse_place_detail_page`에 `.pd-menu .pd-menu__item`을 파싱해 `menu: list[{name, price_won}]`로 추가 반환
- `run_crawl.py`의 `upsert_restaurant` 흐름에 메뉴 upsert 추가 (기존 메뉴 삭제 후 재삽입 — 가격 변동/메뉴 개편을 그대로 반영)
- `name` 컬럼에 트라이그램 GIN 인덱스 (`CREATE EXTENSION pg_trgm` + `CREATE INDEX ... USING gin (name gin_trgm_ops)`) — 기존 프로젝트에 Alembic이 없으므로(상위 스펙 관례대로) `railway ssh` + 수동 SQL로 적용

## 5. 백엔드 아키텍처

### 5.1 새 엔드포인트

```
POST /api/chat
{
  "message": "부산 갈 건데 맛있는 녀석들 나온 한식집 있어?",
  "history": [{"role": "user"|"assistant", "content": "..."}, ...],  // 최근 10턴까지만, 서버는 저장 안 함
  "app_context": {
    "mode": "route" | "browse",
    "route": { "origin_label": "...", "destination_label": "...", "restaurants": [...] } | null,
    "browse": { "bounds": {min_lat,max_lat,min_lng,max_lng}, "broadcast": "..." } | null
  }
}
```

응답:

```
{
  "reply": "부산 쪽엔 맛있는 녀석들에 나온 한식집이 3곳 있어요...",
  "restaurant_ids": ["id1", "id2", "id3"]  // 프론트가 미니 카드로 렌더링, 클릭 시 기존 상세보기
}
```

서버는 대화 상태를 들고 있지 않는다(stateless) — 매 요청에 프론트가 히스토리와 현재 화면 상태를 함께 보낸다. 세션/로그인이 없는 지금 구조와 일관되고, 서버 쪽 상태 관리가 통째로 필요 없어진다.

### 5.2 LLM 도구 정의 (tool-use)

| 도구 | 설명 | 내부 구현 |
|---|---|---|
| `search_restaurants(broadcast?, category?, region_bbox?, open_now?, near_current_context?, radius_km?)` | 조건에 맞는 맛집 찾기 | `app_context.mode == "route"`면 이미 계산된 `route.restaurants` 배열 안에서 필터링(새 DB 호출 없음). 아니면 기존 `list_all_restaurants`/`query_candidate_restaurants` 재사용 |
| `search_by_menu(keyword)` | 메뉴 이름으로 찾기 | `pg_trgm` 유사도 쿼리 (§4) |
| `get_restaurant_detail(id)` | 특정 맛집 상세 | 기존 `_serialize_restaurant` 재사용 |

LLM은 사용자 메시지 + `app_context`를 보고 도구 호출 여부/인자를 결정할 뿐, 조건 판정이나 계산은 절대 직접 하지 않는다 — 아래 §5.3, §5.4가 그 실행을 전담한다.

### 5.3 "지금 영업 중" — 결정론적 파서

`hours` 필드는 크롤러가 원문 그대로 가져온 자유 텍스트다 (예: `"월 11:30~21:00 (브레이크 15:00~17:00), 화 정기휴무 (매주 화요일)"`). LLM에게 이 판정을 맡기면 §3의 "정확성" 원칙과 정면으로 어긋나므로, 전용 파서를 만든다.

```python
# app/hours.py
def is_open_now(hours_text: str, at: datetime) -> bool | None:
    """반환값: True=영업중, False=영업종료, None=패턴을 해석하지 못함."""
```

- 요일별 시간대(`HH:MM~HH:MM`), 브레이크타임 제외, "정기휴무 (매주 X요일)" 같은 흔한 패턴 몇 가지만 정규식으로 처리
- 패턴이 안 맞으면 **반드시 `None`을 반환** — 절대로 추측하지 않는다
- `search_restaurants(open_now=true)` 호출 시 `None`인 맛집은 결과에서 제외하지 않고 별도로 표시해, LLM 시스템 프롬프트가 "영업시간을 확인 못한 곳도 있다"고 솔직히 언급하도록 강제 (오답보다 "모른다"는 답이 낫다는 원칙)

### 5.4 거리 계산 — "가까운" 조건의 기준점

`near_current_context`는 **사용자가 언급한 임의의 지명이 아니라 현재 화면 기준점**으로 한정한다 (v1 범위):

- `route` 모드: 이미 계산된 `distance_from_route_km` 재사용 (재계산 없음)
- `browse` 모드: 지도 뷰포트 중심 좌표, `app/geo.py`의 `haversine_km`으로 계산

"부산역 근처" 같이 화면에 없는 임의 지명 기준 검색은 서버가 그 지명을 좌표로 변환할 수단(카카오 Places 등)이 아직 없어 v1 범위에서 제외한다 — 필요해지면 백엔드에 지오코딩 연동을 추가하는 후속 작업으로 다룬다 (§8).

### 5.5 LLM 공급자

이 문서에서는 특정 벤더에 종속시키지 않는다 — tool-calling(function calling)을 지원하는 LLM API(Claude, OpenAI 등 무엇이든)면 §5.2 인터페이스가 그대로 성립한다. 실제 벤더·모델·비용은 구현 착수 시 결정한다.

## 6. 프론트엔드

새 컴포넌트:

```
frontend/components/
  ChatWidget.tsx     # 우측 하단 플로팅 버튼 + 열리는 채팅 패널
  ChatMessage.tsx     # 메시지 1개 (사용자/챗봇, 챗봇 메시지엔 미니 맛집 카드 포함 가능)
```

- 대화 히스토리는 컴포넌트 로컬 state로만 유지 (새로고침하면 사라짐 — 서버에 안 보내는 원칙과 일관, 영속화는 범위 밖)
- 메시지 전송 시 현재 `page.tsx` 상태(`result` 있으면 route 모드로 그 안의 restaurants, 없으면 browse 모드로 `viewBounds`/`browseBroadcast`)를 `app_context`로 함께 전송 — `page.tsx`가 이미 들고 있는 상태를 그대로 넘기는 것이라 별도 상태 동기화 로직 불필요
- 답변에 `restaurant_ids`가 오면 미니 카드로 렌더링, 클릭 시 기존 `RestaurantDetail` 오픈 (이미 있는 `handleShowDetail` 재사용)

## 7. 에러 처리

| 상황 | 처리 |
|---|---|
| LLM API 호출 실패/타임아웃 | "지금 답변을 드리기 어려워요, 잠시 후 다시 시도해주세요" |
| 도구 실행 중 DB 오류 | 위와 동일한 문구로 통일 (내부 오류 노출 안 함) |
| `open_now` 조건인데 판정 불가 항목 존재 | 결과에 포함하되 "영업시간 확인이 안 되는 곳도 있어요" 명시 (§5.3) |
| 조건에 맞는 맛집 0건 | 에러 아님 — "조건에 맞는 곳을 못 찾았어요" 안내 |

## 8. 범위 밖 (향후 확장 가능 지점)

- 임의 지명("부산역 근처") 기준 거리 검색 — 서버 쪽 지오코딩 연동 필요 (§5.4)
- 트라이그램 검색으로 부족함이 드러나면 메뉴 텍스트에 임베딩 기반 의미 검색 추가
- 외부 리뷰 플랫폼 크롤링 — 완전히 별도의 데이터 소스/크롤러가 필요한 큰 작업이라 별도 스펙으로 다룸
- 대화 히스토리 영속화 (로그인/즐겨찾기 기능과 함께 갈 가능성이 높음 — 상위 스펙 §8과 동일 사유로 지금은 범위 밖)

## 9. 테스트 전략

- `app/hours.py`의 `is_open_now`: 다양한 실제 `hours` 패턴(정규 영업, 브레이크타임, 정기휴무, 해석 불가 케이스)에 대한 단위 테스트 — 이 파서가 §5.3의 정확성 원칙을 지키는 핵심이라 가장 두껍게 테스트한다
- 도구 함수들(`search_restaurants`, `search_by_menu`, `get_restaurant_detail`)은 LLM 없이 순수 함수로 단위 테스트
- `/api/chat` 엔드포인트: LLM 호출을 모킹해 도구 호출 경로·`app_context` 분기(route vs browse)만 검증 — 실제 LLM 응답 품질은 자동화 테스트 대상이 아님
- 프론트: `ChatWidget` 열기/닫기, `app_context` 조립 로직 단위 테스트 + 실제 브라우저에서 대화 흐름 육안 확인
