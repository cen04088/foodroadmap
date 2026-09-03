경로 기반 방송 맛집 추천 서비스의 프론트엔드. 출발지/도착지를 검색하면 카카오 Directions API로 경로를 구하고, 그 경로 근처의 방송 출연 맛집을 지도+리스트로 보여준다. 백엔드는 `../backend`(FastAPI)에 있고, 이 프론트엔드는 브라우저에서 백엔드를 직접 호출한다(프록시 없음). 설계는 [`../docs/superpowers/specs/2026-09-03-frontend-design.md`](../docs/superpowers/specs/2026-09-03-frontend-design.md) 참고.

## 로컬에서 실행하기 (foodmap)

이 앱은 **백엔드와 프론트엔드를 둘 다 띄워야** 동작한다. 카카오 API 키가 두 종류 필요하다 — 서로 다른 키이니 헷갈리지 말 것:

- **카카오모빌리티 Directions REST API 키** — 백엔드가 서버에서 경로를 조회할 때 씀.
- **카카오맵 JavaScript SDK 앱 키** — 프론트엔드가 브라우저에서 지도/장소검색을 띄울 때 씀.

둘 다 [Kakao Developers](https://developers.kakao.com)의 같은 애플리케이션에서 발급받되, "REST API 키"와 "JavaScript 키"는 별개의 값이다.

### 1. 백엔드 실행 (별도 터미널)

```bash
cd ../backend
pip install -r requirements.txt

# Windows PowerShell
$env:KAKAO_REST_API_KEY="<카카오 REST API 키>"
$env:DATABASE_URL="sqlite:///./foodmap.db"   # 크롤러로 채운 로컬 DB
$env:FRONTEND_ORIGINS="http://localhost:3000" # CORS 허용 오리진(프론트 개발 서버 주소)

uvicorn app.api.main:app --reload
```

`foodmap.db`에 실제 맛집 데이터가 없다면 먼저 크롤러를 한 번 돌려야 한다: `python -m app.crawler.run_crawl` (`backend/` 안에서, 시간이 좀 걸림 — 사이트 부하를 줄이려고 요청마다 1초 딜레이가 있음).

### 2. 프론트엔드 환경변수 설정

```bash
cp .env.local.example .env.local
```

`.env.local`을 열어 채운다:

```
NEXT_PUBLIC_KAKAO_JS_KEY=<카카오맵 JavaScript SDK 앱 키>
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
```

`.env.local`은 `.gitignore`에 걸려 있으니 실제 키 값을 커밋하지 않는다.

### 3. 프론트엔드 실행

```bash
npm install
npm run dev
```

[http://localhost:3000](http://localhost:3000)을 열면 된다.

## 테스트

```bash
npm test          # lib/format.ts, lib/api.ts 단위 테스트 (Vitest)
npx tsc --noEmit   # 타입 체크
npm run build      # 프로덕션 빌드
```

컴포넌트/카카오 SDK 연동은 자동 테스트가 없다 — 위 명령이 통과해도 실제 브라우저에서 검색 흐름을 직접 확인해야 한다(설계 문서 §8).
