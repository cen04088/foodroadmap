# 경로 맛집 추천 서비스 — 설계 문서

- 작성일: 2026-09-01
- 상태: 승인됨 (구현 계획 수립 대기)

## 1. 개요

사용자가 목적지까지의 경로를 검색하면, 그 경로상에(또는 경로에서 일정 반경 이내에) 있는
방송/유튜브 출연 맛집을 알려주는 서비스. 맛집이 경로상 어느 위치에 있는지, 출발지로부터
몇 시간 거리에 있는지를 함께 보여주는 것이 핵심 가치.

## 2. 목표 및 범위

### 2.1 플랫폼
- 웹앱 (모바일 반응형). 앱(iOS/Android)은 이후 단계에서 검토.

### 2.2 데이터 소스
- 맛집 DB는 matzipmap.com(맛집여지도)을 크롤링하여 구축.
  - 사이트는 Next.js App Router로 서버 렌더링되며, 크롤링에 필요한 데이터는 실제 HTML에
    그대로 포함되어 있어 별도 JS 실행 없이 정적 HTML 파싱(requests + BeautifulSoup)만으로
    수집 가능함을 실제 페이지 요청으로 확인함(2026-09-01).
  - **프로그램 목록**: `GET /broadcasts` 페이지에서 `href="/broadcast/{slug}"` 링크로 확인.
    확인된 슬러그: `ttoganjib`(또간집), `heukbaek`(흑백요리사), `tzuyang`(쯔양),
    `myeotkki`(쯔양 몇끼), `meogeulteonde`(먹을텐데), `jeonhyeonmu`(전현무계획),
    `baekban`(허영만의 백반기행), `bapsang`(한국인의 밥상), `kimyoungchul`(맛있는 녀석들),
    `matnyeoseok`(동네한바퀴), `baengnyeon`(백년가게), `bimirya`(비밀이야),
    `tamnik`(공간 탐닉), `kimsawon`(김사원세끼).
  - **목록 페이지**: `GET /broadcast/{slug}?page=N`. 각 맛집은
    `<li><a class="bc-item" href="/place/{uuid}">` 안에 다음 구조로 존재:
    - `.bc-item__name` (텍스트, 내부에 `.bc-item__cat` 업종 span 포함)
    - `.bc-item__addr` (지번 주소)
    - `.bc-item__meta` 안의 두 `<span>` — 첫 번째가 `📞 전화번호`, 두 번째가 `🕘 영업시간`
      (둘 중 하나가 없을 수도 있음 — 예: 전화번호 없이 영업시간만 있는 케이스 확인됨)
    - `.bc-item__desc`(설명, 선택), `.bc-item__menu`(대표 메뉴, 선택)
    - href의 `{uuid}`가 해당 맛집의 matzipmap 고유 ID(`external_id`)
    - 페이지네이션: `<nav class="bc-pager">` 내 `a.bc-pager__nav[rel="next"]` 존재 여부로
      다음 페이지 유무 판단(마지막 페이지에는 없음).
  - **상세 페이지**: `GET /place/{uuid}`. `<script type="application/ld+json">` 안에
    `"@type":"Restaurant"` 객체로 `name`, `address`, `geo:{latitude,longitude}`,
    `telephone`, `servesCuisine`, `hasMenu` 등이 포함됨. **위경도 좌표가 이미 matzipmap
    측에서 지오코딩되어 제공되므로, 이 서비스에서 별도 지오코딩 파이프라인을 구축할
    필요가 없음** (기존 설계에서 계획했던 카카오 로컬 API 지오코딩 단계 제거).
  - 수집 절차: (1) 프로그램별 목록 페이지를 페이지네이션 끝까지 순회해 기본 필드 +
    `external_id` + 소속 프로그램 수집 → (2) 수집된 `external_id` 집합에 대해 상세 페이지를
    1회씩 요청해 좌표(및 검증용 상세 필드) 획득 → (3) DB에 upsert.
  - **법적 리스크 메모**: 국내 저작권법상 데이터베이스제작자의 권리 이슈가 있을 수 있음.
    개인 프로토타입/MVP 단계에서는 리스크가 낮으나, 트래픽이 늘어나는 정식 서비스
    단계에서는 직접 수집 DB 전환 또는 제휴를 재검토해야 함. 크롤러는 요청 간 딜레이를 두어
    대상 서버 부하를 최소화한다.

### 2.3 지도/경로 API
- 카카오모빌리티 Directions API 사용.
  - 무료 한도: 일 1만 건 무료, 초과 시 100만 건까지 건당 8원.
  - 프론트엔드 지도 표시는 카카오맵 JS SDK 사용.
  - (맛집 좌표는 matzipmap 상세 페이지에서 이미 확보되므로, 카카오 로컬 API는 이 서비스에서
    사용하지 않음.)
  - **요청**: `GET https://apis-navi.kakaomobility.com/v1/directions` (주의: `/affiliate/v1/...`
    경로가 **아님** — affiliate 경로는 별도 제휴 승인이 필요한 상품이라 403 permission
    denied가 남; 일반 REST API 키로는 `/v1/directions`를 사용), 헤더
    `Authorization: KakaoAK ${REST_API_KEY}`, 쿼리 파라미터 `origin=${lng},${lat}`,
    `destination=${lng},${lat}` (카카오는 x=경도, y=위도 순서).
  - **응답 구조** — 실제 REST API 키로 라이브 호출해 검증 완료(2026-09-01, 서울시청→강남역
    구간):
    `routes[0].result_code`(0=성공), `routes[0].summary.distance`(총 거리, m),
    `routes[0].summary.duration`(총 소요시간, 초), `routes[0].sections[].roads[]` 배열의 각
    road가 `distance`(m), `duration`(초), `vertexes`(평탄화된 `[lng, lat, lng, lat, ...]` 배열,
    {x,y} 객체 배열이 아님을 확인)를 가짐. 문서 기준 스키마와 실제 응답이 정확히 일치함을
    확인했다.
  - **중요**: API 응답은 vertex 단위가 아니라 **road(도로 구간) 단위로만** 누적거리/시간을
    제공한다. vertex별 누적값은 API가 주지 않으므로, 이 서비스가 각 road의 vertex 목록을
    순회하며 직접 누적 distance/duration을 계산해야 한다 (§4 참고).

### 2.4 "경로상 맛집" 판단 기준
- 경로선으로부터 직선거리 기준, 고정 반경값(기본 2km) 이내인 맛집을 채택.
  (추후 지역/사용자별 조정 가능하도록 설계는 열어두되, MVP는 고정값)

### 2.5 "출발 후 몇 시간 거리" 계산 방식
- 맛집에서 경로선상 가장 가까운 지점까지의 최단거리를 구하고, 그 지점의
  원래 경로 상 누적 주행시간(우회 미포함)을 그대로 사용.
- 맛집 방문을 위한 실제 우회 시간은 계산하지 않음 (API 호출량/응답시간 절약).

### 2.6 MVP 기능 범위
- 출발지/도착지 입력 → 경로 검색 → 경로상 맛집 리스트(거리/시간순) + 지도 표시.
- 방송프로그램 필터, 업종 필터.
- 즐겨찾기/공유/회원 시스템은 MVP 범위 밖.

## 3. 아키텍처

```
[크롤러 (Python, 배치)] ──▶ [PostgreSQL: 맛집 DB]
                                     ▲
                                     │ 조회
[프론트엔드: Next.js + 카카오맵 SDK] ──▶ [백엔드: FastAPI] ──▶ [카카오모빌리티 Directions API]
```

### 3.1 컴포넌트

- **크롤러**: matzipmap.com을 프로그램별 목록 페이지 → 상세 페이지 순으로 순회하며 맛집
  데이터(좌표 포함)를 수집해 upsert. 주기 실행(예: 주 1회 cron/스케줄 잡)으로 신규/변경분
  반영. (§2.2 참고 — 별도 지오코딩 단계는 불필요)
- **DB (PostgreSQL)**:
  - `restaurants`: external_id(matzipmap uuid, unique), 상호명, 업종, 주소, 좌표(lat/lng),
    전화번호, 영업시간
  - `broadcasts`: 프로그램 slug, 프로그램명
  - `restaurant_broadcasts`: N:M (한 맛집이 여러 방송에 나올 수 있음)
- **백엔드 (FastAPI)**: 출발지/도착지를 받아 카카오 Directions API 호출 → 경로 좌표 획득 →
  DB에서 후보 조회 → 경로-맛집 매칭 로직 실행 → 정렬된 결과 반환.
- **프론트엔드 (Next.js + 카카오맵 JS SDK)**: 출발/도착 입력, 지도에 경로선+맛집 마커,
  리스트뷰(거리순/시간순), 방송프로그램/업종 필터 UI.

초기에는 PostGIS 없이 일반 PostgreSQL + 애플리케이션 레벨 계산(haversine + 점-세그먼트
거리 공식)으로 처리. 데이터가 수만 건 이상으로 늘어나면 PostGIS 전환을 검토.

## 4. 핵심 알고리즘: 경로-맛집 매칭

1. 카카오 Directions API 응답(`routes[0].sections[].roads[]`)을 순회하며, road 단위로만
   주어지는 `distance`/`duration`을 vertex 단위로 환산한 **경로 포인트 리스트**를 만든다:
   각 road의 `vertexes`(평탄화된 `[lng,lat,...]`)를 좌표 쌍으로 묶고, road 내부의
   세그먼트 길이 비율로 그 road의 `duration`을 배분해 각 포인트에 "누적 거리(m)"와
   "누적 시간(초, 출발 기준)"을 부여한다. (road 내부는 균일 속도로 가정하는 근사치 —
   §2.5의 "우회 미포함" 단순화와 같은 급의 근사.)
2. 경로의 바운딩박스(위경도 최소/최대 + 반경 여유)로 DB 1차 필터링.
3. 각 후보 맛집에 대해 1에서 만든 경로 포인트 리스트의 각 세그먼트와의 최단 직선거리
   (point-to-segment distance, haversine 기반 근사) 계산 → 반경(기본 2km) 이내인 것만 채택.
4. 채택된 맛집은 가장 가까운 세그먼트 양끝점의 누적 주행시간을 선형보간해
   "출발 후 몇 시간 지점"으로 사용.
5. 결과를 누적시간(경로 진행순)으로 정렬해 반환.

## 5. API 설계 (개략)

`GET /api/route-restaurants?origin=lat,lng&destination=lat,lng&radius_km=2&broadcast=또간집&category=한식`

응답: 경로 폴리라인, 총 소요시간/거리, 매칭된 맛집 리스트
(상호명, 좌표, 반경 이내 거리, 출발 후 누적시간, 방송프로그램, 업종, 전화번호, 영업시간).

## 6. 에러 처리

- 카카오 Directions API 실패/쿼터 초과 → 사용자에게 재시도 안내, 429/5xx 구분 로깅.
- 상세 페이지에서 좌표(geo)를 파싱하지 못한 맛집 → 해당 레코드는 좌표 없이 저장하되
  매칭 대상(경로 계산)에서는 제외, 다음 크롤링 주기에 재시도.
- 크롤러가 matzipmap.com 구조 변경(CSS 클래스/JSON-LD 스키마 변경 등)으로 파싱 실패 시 →
  알림 후 해당 배치 스킵, 기존 DB는 유지.

## 7. 테스트 전략

- 매칭 알고리즘(점-세그먼트 거리, 반경 필터, 누적시간 계산)은 순수 함수로 분리해
  유닛테스트로 검증 (고정된 가짜 경로 좌표 + 가짜 맛집 좌표로 케이스 구성).
- 크롤러는 저장된 HTML 픽스처(목록 페이지, 상세 페이지 각각)를 이용한 파싱 테스트
  (실 네트워크 호출 없이).
- API 엔드투엔드 테스트는 카카오 API를 모킹해 통합 테스트.

## 8. 향후 검토 사항 (MVP 범위 밖)

- 모바일 네이티브 앱.
- 맛집 DB 자체 수집/제휴로 전환 (저작권 리스크 해소).
- 우회시간 포함한 정밀 계산.
- 반경 사용자 조정 UI.
- 회원/즐겨찾기/공유 기능.
