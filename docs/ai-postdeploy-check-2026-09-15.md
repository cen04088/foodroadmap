# 배포 후 AI 재검증 — 2026-09-15

서울역→강릉역 18건, 서울역→전주 한옥마을 9건, 총 27건을 실서비스 API에서 요청했다. 모든 요청이 정상 응답했으며 새 필드(min_minutes, max_minutes, menu_match, required_unverified 등)를 반환했다. 배포 버전 ID 자체는 조회하지 않았다.

## 확인된 개선

- 20분 이내 / 2시간 이후: 두 경로에서 실제 추천 시간이 경계를 지켰다. 이전 33분·108분 위반은 재현되지 않았다.
- 30~60분 요청 후 10분 늦게: 40~70분으로 이동하고 메뉴를 유지했다. 시간 해제도 세 시간 필드를 비웠다.
- 칼국수 1만원 미만: price_exclusive=true, 모든 추천 가격이 1만원 미만이었다. 이하로 변경하면 false가 되고 강릉 경로 후보 수가 19→25로 증가했다.
- 돈까스와 냉면 모두: all로 해석했다. 각 메뉴 1만원 제한 시 강릉 경로 결과 없음, 둘 중 하나 허용 시 any로 바뀌어 20곳 중 3곳 추천. 전주 경로 예산 없는 all 요청은 전주맛자랑 1곳과 두 메뉴 확인 근거를 반환했다.
- 주차 필수·알레르기 안전 필수: 한식/예산이 있어도 추천을 보류했다. 주차를 직접 확인하겠다는 후속 요청에서는 필수 조건과 되묻기를 해제하고 기존 한식/예산을 유지했다.
- 미확인 조건만 요청: 일반 추천 대신 메뉴·예산·시간을 되물었다.
- 또간집 제외: excluded_broadcasts에 반영됐고 반환된 식당 방송과 충돌하지 않았다.
- 간식 꽈배기 요청은 간식으로 추천, 돼지고기 요청은 삼겹살 등으로 확장됐다.

## 남은 오류 및 권장 순서

### 1. 식사 메뉴 판별이 아직 불충분 — 우선 수정

- 강릉 경로 '가장 저렴한 한 끼': 고구마 700원, 흑미찹쌀 도넛츠 1개 1,000원, 맛계란 1,500원.
- 전주 경로 같은 요청: 후라이 500원 두 곳, 고구마 700원.
- 전주 경로 '처음부터. 조건 없이 추천해줘': 대우호프의 생맥주(500cc) 4,500원.
- 시간 상한+가격순 요청에도 죽순 1,900원·도넛 등 메뉴가 선택됐다.

앞서 제외한 이름은 차단되지만 다른 표기가 계속 최저가를 차지한다. 단순 제외어 추가만으로 식사 여부를 보장할 수 없다. 즉시 개선은 생맥주/후라이/맛계란/도넛 등 명확한 비식사 메뉴 처리, 근본 개선은 메뉴 분류(식사/간식/추가/음료/미확인)를 저장하고 일반 식사 추천에는 검증된 식사 메뉴를 쓰는 것이다. 미확인 메뉴는 최저가 근거로 사용하지 않고, 사용자가 특정 메뉴나 간식을 명시한 경우 별도로 처리한다. 분류를 AI로 제안받더라도 검토 상태와 원본 근거를 보관해야 한다.

### 2. 다른 이름으로 수집된 동일 장소 중복 의심

'창성옥'과 '창성옥 본점'이 같은 11.6분 지점, 같은 후라이 가격으로 2자리를 차지한다. 현재 이름+주소 정확 일치만 병합하므로 이름 변형은 남는다. 같은 장소인지는 주소·좌표·전화 또는 외부 장소 ID로 확인해야 하며 이름만으로 자동 병합하지 않는다.

## 한계

27건의 조건 필드 검사에서 불일치는 없었지만, 위 식사 적합성 문제 때문에 전체 합격으로 판단하지 않는다. 공개 API는 전체 메뉴를 제공하지 않아 all 조건의 두 메뉴 근거는 서버 응답까지 확인했고 원천 메뉴 데이터 전체와 대조하지 못했다. 이번 작업에서는 코드 수정·푸시를 하지 않았다. 브라우저/UI 및 부하 검사는 포함하지 않았다.

AI 요청 응답시간 중앙값: 1.41초.

## 요청별 응답 기록

### 서울–강릉

- 출발 후 20분 이내에 가장 저렴하게
  - 조건: `{"categories": [], "broadcasts": [], "menu_keywords": [], "excluded_keywords": [], "max_price_won": null, "target_minutes": null, "time_window_minutes": 30, "sort": "price", "unverified": [], "clarification": null, "min_minutes": 0, "max_minutes": 20, "price_exclusive": false, "menu_match": "any", "excluded_broadcasts": [], "required_unverified": [], "purpose": "meal"}`
  - 추천: [{"name": "광장시장 찹쌀꽈배기", "minutes": 16.2, "category": "카페", "broadcasts": ["또간집"], "menu": {"name": "흑미찹쌀 도넛츠 1개", "price_won": 1000, "is_representative": false}}, {"name": "여의주훠궈관 을지로본점", "minutes": 16.2, "category": "중식", "broadcasts": ["흑백요리사"], "menu": {"name": "죽순", "price_won": 1900, "is_representative": false}}, {"name": "호수집", "minutes": 3.6, "category": "한식", "broadcasts": ["김사원세끼"], "menu": {"name": "볶음밥", "price_won": 2000, "is_representative": false}}]

- 출발 후 2시간 이후에 먹고 싶어
  - 조건: `{"categories": [], "broadcasts": [], "menu_keywords": [], "excluded_keywords": [], "max_price_won": null, "target_minutes": null, "time_window_minutes": 30, "sort": "timing", "unverified": [], "clarification": null, "min_minutes": 120, "max_minutes": null, "price_exclusive": false, "menu_match": "any", "excluded_broadcasts": [], "required_unverified": [], "purpose": "meal"}`
  - 추천: [{"name": "매화촌해장국", "minutes": 136.1, "category": "한식", "broadcasts": ["허영만의 백반기행"], "menu": {"name": "해장국", "price_won": 11000, "is_representative": false}}, {"name": "물치손칼국수", "minutes": 158.5, "category": "한식", "broadcasts": ["또간집"], "menu": {"name": "칼국수", "price_won": 8000, "is_representative": false}}, {"name": "단양면옥", "minutes": 158.6, "category": "한식", "broadcasts": ["허영만의 백반기행"], "menu": {"name": "함흥물냉면", "price_won": 10000, "is_representative": false}}]

- 출발 후 30분에서 1시간 사이에 국수
  - 조건: `{"categories": [], "broadcasts": [], "menu_keywords": ["국수"], "excluded_keywords": [], "max_price_won": null, "target_minutes": null, "time_window_minutes": 30, "sort": "timing", "unverified": [], "clarification": null, "min_minutes": 30, "max_minutes": 60, "price_exclusive": false, "menu_match": "any", "excluded_broadcasts": [], "required_unverified": [], "purpose": "meal"}`
  - 추천: [{"name": "별미손칼국수", "minutes": 44.6, "category": "한식", "broadcasts": ["백년가게"], "menu": {"name": "칼국수", "price_won": 10000, "is_representative": false}}, {"name": "쌍둥이네포장마차", "minutes": 43.8, "category": "술집", "broadcasts": ["김사원세끼"], "menu": {"name": "칼국수", "price_won": 7000, "is_representative": false}}, {"name": "장원보쌈족발", "minutes": 43.1, "category": "한식", "broadcasts": ["백년가게"], "menu": {"name": "쟁반국수 소", "price_won": 10000, "is_representative": false}}]

- 10분 더 늦게
  - 조건: `{"categories": [], "broadcasts": [], "menu_keywords": ["국수"], "excluded_keywords": [], "max_price_won": null, "target_minutes": null, "time_window_minutes": 30, "sort": "timing", "unverified": [], "clarification": null, "min_minutes": 40, "max_minutes": 70, "price_exclusive": false, "menu_match": "any", "excluded_broadcasts": [], "required_unverified": [], "purpose": "meal"}`
  - 추천: [{"name": "시가올", "minutes": 51.7, "category": "한식", "broadcasts": ["맛있는 녀석들"], "menu": {"name": "비빔국수", "price_won": 10000, "is_representative": true}}, {"name": "별미손칼국수", "minutes": 44.6, "category": "한식", "broadcasts": ["백년가게"], "menu": {"name": "칼국수", "price_won": 10000, "is_representative": false}}, {"name": "쌍둥이네포장마차", "minutes": 43.8, "category": "술집", "broadcasts": ["김사원세끼"], "menu": {"name": "칼국수", "price_won": 7000, "is_representative": false}}]

- 시간 상관없이
  - 조건: `{"categories": [], "broadcasts": [], "menu_keywords": ["국수"], "excluded_keywords": [], "max_price_won": null, "target_minutes": null, "time_window_minutes": 30, "sort": "timing", "unverified": [], "clarification": null, "min_minutes": null, "max_minutes": null, "price_exclusive": false, "menu_match": "any", "excluded_broadcasts": [], "required_unverified": [], "purpose": "meal"}`
  - 추천: [{"name": "한조분식", "minutes": 0.0, "category": "한식", "broadcasts": ["쯔양"], "menu": {"name": "멸치국수", "price_won": 6000, "is_representative": true}}, {"name": "대구막창껍데기", "minutes": 0.0, "category": "한식", "broadcasts": ["김사원세끼"], "menu": {"name": "열무국수", "price_won": 7000, "is_representative": false}}, {"name": "남영돈", "minutes": 0.0, "category": "한식", "broadcasts": ["쯔양", "김사원세끼"], "menu": {"name": "잔치국수", "price_won": 7000, "is_representative": false}}]

- 돈까스와 냉면 둘 다 파는 곳. 메뉴 각각 1만원 이하
  - 조건: `{"categories": [], "broadcasts": [], "menu_keywords": ["돈까스", "냉면"], "excluded_keywords": [], "max_price_won": 10000, "target_minutes": null, "time_window_minutes": 30, "sort": "timing", "unverified": [], "clarification": null, "min_minutes": null, "max_minutes": null, "price_exclusive": false, "menu_match": "all", "excluded_broadcasts": [], "required_unverified": [], "purpose": "meal"}`
  - 추천: []

- 둘 중 하나만 있어도 괜찮아
  - 조건: `{"categories": [], "broadcasts": [], "menu_keywords": ["돈까스", "냉면"], "excluded_keywords": [], "max_price_won": 10000, "target_minutes": null, "time_window_minutes": 30, "sort": "timing", "unverified": [], "clarification": null, "min_minutes": null, "max_minutes": null, "price_exclusive": false, "menu_match": "any", "excluded_broadcasts": [], "required_unverified": [], "purpose": "meal"}`
  - 추천: [{"name": "한조분식", "minutes": 0.0, "category": "한식", "broadcasts": ["쯔양"], "menu": {"name": "물냉면", "price_won": 6000, "is_representative": false}}, {"name": "두툼", "minutes": 2.9, "category": "한식", "broadcasts": ["비밀이야"], "menu": {"name": "물냉면", "price_won": 5000, "is_representative": false}}, {"name": "경기식당", "minutes": 3.6, "category": "한식", "broadcasts": ["김사원세끼"], "menu": {"name": "냉면", "price_won": 8000, "is_representative": false}}]

- 칼국수 메뉴 1만원 미만인 곳
  - 조건: `{"categories": [], "broadcasts": [], "menu_keywords": ["칼국수"], "excluded_keywords": [], "max_price_won": 10000, "target_minutes": null, "time_window_minutes": 30, "sort": "timing", "unverified": [], "clarification": null, "min_minutes": null, "max_minutes": null, "price_exclusive": true, "menu_match": "any", "excluded_broadcasts": [], "required_unverified": [], "purpose": "meal"}`
  - 추천: [{"name": "경동맛집", "minutes": 3.6, "category": "한식", "broadcasts": ["허영만의 백반기행"], "menu": {"name": "들깨수제비칼국수", "price_won": 8000, "is_representative": false}}, {"name": "남해식당", "minutes": 11.2, "category": "한식", "broadcasts": ["한국인의 밥상"], "menu": {"name": "칼국수+냉면", "price_won": 9000, "is_representative": false}}, {"name": "소공바지락칼국수", "minutes": 14.0, "category": "한식", "broadcasts": ["또간집"], "menu": {"name": "바지락칼국수", "price_won": 8000, "is_representative": false}}]

- 1만원 이하로 바꿔줘
  - 조건: `{"categories": [], "broadcasts": [], "menu_keywords": ["칼국수"], "excluded_keywords": [], "max_price_won": 10000, "target_minutes": null, "time_window_minutes": 30, "sort": "timing", "unverified": [], "clarification": null, "min_minutes": null, "max_minutes": null, "price_exclusive": false, "menu_match": "any", "excluded_broadcasts": [], "required_unverified": [], "purpose": "meal"}`
  - 추천: [{"name": "경동맛집", "minutes": 3.6, "category": "한식", "broadcasts": ["허영만의 백반기행"], "menu": {"name": "들깨수제비칼국수", "price_won": 8000, "is_representative": false}}, {"name": "남해식당", "minutes": 11.2, "category": "한식", "broadcasts": ["한국인의 밥상"], "menu": {"name": "칼국수+냉면", "price_won": 9000, "is_representative": false}}, {"name": "소공바지락칼국수", "minutes": 14.0, "category": "한식", "broadcasts": ["또간집"], "menu": {"name": "바지락칼국수", "price_won": 8000, "is_representative": false}}]

- 땅콩 알레르기가 있어. 안전한 곳만, 한식 2만원 이하로
  - 조건: `{"categories": ["한식"], "broadcasts": [], "menu_keywords": [], "excluded_keywords": [], "max_price_won": 20000, "target_minutes": null, "time_window_minutes": 30, "sort": "timing", "unverified": ["땅콩 알레르기 안전"], "clarification": "반드시 필요한 조건(땅콩 알레르기 안전)을 확인할 수 없어 추천을 보류했어요. 이 조건은 직접 확인하고 메뉴·가격·시간으로 찾아볼까요?", "min_minutes": null, "max_minutes": null, "price_exclusive": false, "menu_match": "any", "excluded_broadcasts": [], "required_unverified": ["땅콩 알레르기 안전"], "purpose": "meal"}`
  - 추천: []

- 반드시 주차 가능한 곳만. 한식 2만원 이하
  - 조건: `{"categories": ["한식"], "broadcasts": [], "menu_keywords": [], "excluded_keywords": [], "max_price_won": 20000, "target_minutes": null, "time_window_minutes": 30, "sort": "timing", "unverified": ["주차 가능"], "clarification": "반드시 필요한 조건(주차 가능)을 확인할 수 없어 추천을 보류했어요. 이 조건은 직접 확인하고 메뉴·가격·시간으로 찾아볼까요?", "min_minutes": null, "max_minutes": null, "price_exclusive": false, "menu_match": "any", "excluded_broadcasts": [], "required_unverified": ["주차 가능"], "purpose": "meal"}`
  - 추천: []

- 주차는 내가 확인할게. 주차 조건 빼고 추천해줘
  - 조건: `{"categories": ["한식"], "broadcasts": [], "menu_keywords": [], "excluded_keywords": [], "max_price_won": 20000, "target_minutes": null, "time_window_minutes": 30, "sort": "timing", "unverified": [], "clarification": null, "min_minutes": null, "max_minutes": null, "price_exclusive": false, "menu_match": "any", "excluded_broadcasts": [], "required_unverified": [], "purpose": "meal"}`
  - 추천: [{"name": "한조분식", "minutes": 0.0, "category": "한식", "broadcasts": ["쯔양"], "menu": {"name": "멸치국수", "price_won": 6000, "is_representative": true}}, {"name": "대구막창껍데기", "minutes": 0.0, "category": "한식", "broadcasts": ["김사원세끼"], "menu": {"name": "된장찌개", "price_won": 5000, "is_representative": false}}, {"name": "상록수 연탄구이 숙대본점", "minutes": 0.0, "category": "한식", "broadcasts": ["쯔양", "허영만의 백반기행"], "menu": {"name": "원조)비빔수제비", "price_won": 7000, "is_representative": true}}]

- 지금 영업 중이고 조용한 곳
  - 조건: `{"categories": [], "broadcasts": [], "menu_keywords": [], "excluded_keywords": [], "max_price_won": null, "target_minutes": null, "time_window_minutes": 30, "sort": "timing", "unverified": ["영업 중", "조용한 곳"], "clarification": "요청하신 조건은 등록 정보로 확인할 수 없어요. 원하는 메뉴, 메뉴당 예산 또는 출발 후 식사 시간을 알려주세요.", "min_minutes": null, "max_minutes": null, "price_exclusive": false, "menu_match": "any", "excluded_broadcasts": [], "required_unverified": [], "purpose": "meal"}`
  - 추천: []

- 또간집에 나온 곳은 빼고 추천해줘
  - 조건: `{"categories": [], "broadcasts": [], "menu_keywords": [], "excluded_keywords": [], "max_price_won": null, "target_minutes": null, "time_window_minutes": 30, "sort": "timing", "unverified": [], "clarification": null, "min_minutes": null, "max_minutes": null, "price_exclusive": false, "menu_match": "any", "excluded_broadcasts": ["또간집"], "required_unverified": [], "purpose": "meal"}`
  - 추천: [{"name": "한조분식", "minutes": 0.0, "category": "한식", "broadcasts": ["쯔양"], "menu": {"name": "멸치국수", "price_won": 6000, "is_representative": true}}, {"name": "대구막창껍데기", "minutes": 0.0, "category": "한식", "broadcasts": ["김사원세끼"], "menu": {"name": "된장찌개", "price_won": 5000, "is_representative": false}}, {"name": "상록수 연탄구이 숙대본점", "minutes": 0.0, "category": "한식", "broadcasts": ["쯔양", "허영만의 백반기행"], "menu": {"name": "원조)비빔수제비", "price_won": 7000, "is_representative": true}}]

- 가장 저렴한 한 끼 추천해줘
  - 조건: `{"categories": [], "broadcasts": [], "menu_keywords": [], "excluded_keywords": [], "max_price_won": null, "target_minutes": null, "time_window_minutes": 30, "sort": "price", "unverified": [], "clarification": null, "min_minutes": null, "max_minutes": null, "price_exclusive": false, "menu_match": "any", "excluded_broadcasts": [], "required_unverified": [], "purpose": "meal"}`
  - 추천: [{"name": "잠원떡볶이", "minutes": 29.1, "category": "한식", "broadcasts": ["쯔양", "김사원세끼"], "menu": {"name": "고구마", "price_won": 700, "is_representative": false}}, {"name": "광장시장 찹쌀꽈배기", "minutes": 16.2, "category": "카페", "broadcasts": ["또간집"], "menu": {"name": "흑미찹쌀 도넛츠 1개", "price_won": 1000, "is_representative": false}}, {"name": "소바식당", "minutes": 35.4, "category": "일식", "broadcasts": ["또간집"], "menu": {"name": "맛계란", "price_won": 1500, "is_representative": false}}]

- 한 시간쯤 뒤, 한식으로 2만 원 이하
  - 조건: `{"categories": ["한식"], "broadcasts": [], "menu_keywords": [], "excluded_keywords": [], "max_price_won": 20000, "target_minutes": 60, "time_window_minutes": 30, "sort": "timing", "unverified": [], "clarification": null, "min_minutes": null, "max_minutes": null, "price_exclusive": false, "menu_match": "any", "excluded_broadcasts": [], "required_unverified": [], "purpose": "meal"}`
  - 추천: [{"name": "매봉골황제능이버섯", "minutes": 66.7, "category": "한식", "broadcasts": ["맛있는 녀석들"], "menu": {"name": "메밀전병", "price_won": 15000, "is_representative": false}}, {"name": "시가올", "minutes": 51.7, "category": "한식", "broadcasts": ["맛있는 녀석들"], "menu": {"name": "비빔국수", "price_won": 10000, "is_representative": true}}, {"name": "별미손칼국수", "minutes": 44.6, "category": "한식", "broadcasts": ["백년가게"], "menu": {"name": "칼국수", "price_won": 10000, "is_representative": false}}]

- 간식으로 꽈배기 먹고 싶어
  - 조건: `{"categories": [], "broadcasts": [], "menu_keywords": ["꽈배기"], "excluded_keywords": [], "max_price_won": null, "target_minutes": null, "time_window_minutes": 30, "sort": "timing", "unverified": [], "clarification": null, "min_minutes": null, "max_minutes": null, "price_exclusive": false, "menu_match": "any", "excluded_broadcasts": [], "required_unverified": [], "purpose": "snack"}`
  - 추천: [{"name": "광장시장 찹쌀꽈배기", "minutes": 16.2, "category": "카페", "broadcasts": ["또간집"], "menu": {"name": "찹쌀꽈배기 1개", "price_won": 1000, "is_representative": false}}]

- 돼지고기 먹고 싶어
  - 조건: `{"categories": [], "broadcasts": [], "menu_keywords": ["돼지고기"], "excluded_keywords": [], "max_price_won": null, "target_minutes": null, "time_window_minutes": 30, "sort": "timing", "unverified": [], "clarification": null, "min_minutes": null, "max_minutes": null, "price_exclusive": false, "menu_match": "any", "excluded_broadcasts": [], "required_unverified": [], "purpose": "meal"}`
  - 추천: [{"name": "대구막창껍데기", "minutes": 0.0, "category": "한식", "broadcasts": ["김사원세끼"], "menu": {"name": "돼지막창", "price_won": 15000, "is_representative": false}}, {"name": "상록수 연탄구이 숙대본점", "minutes": 0.0, "category": "한식", "broadcasts": ["쯔양", "허영만의 백반기행"], "menu": {"name": "진짜별미)연탄돼지막창", "price_won": 15000, "is_representative": true}}, {"name": "원조마포껍데기집", "minutes": 0.0, "category": "한식", "broadcasts": ["김사원세끼"], "menu": {"name": "삼겹살", "price_won": 14000, "is_representative": false}}]

### 서울–전주

- 출발 후 20분 이내에 가장 저렴하게
  - 조건: `{"categories": [], "broadcasts": [], "menu_keywords": [], "excluded_keywords": [], "max_price_won": null, "target_minutes": null, "time_window_minutes": 30, "sort": "price", "unverified": [], "clarification": null, "min_minutes": 0, "max_minutes": 20, "price_exclusive": false, "menu_match": "any", "excluded_broadcasts": [], "required_unverified": [], "purpose": "meal"}`
  - 추천: [{"name": "창성옥", "minutes": 11.6, "category": "한식", "broadcasts": ["백년가게"], "menu": {"name": "후라이", "price_won": 500, "is_representative": false}}, {"name": "창성옥 본점", "minutes": 11.6, "category": "한식", "broadcasts": ["허영만의 백반기행"], "menu": {"name": "후라이", "price_won": 500, "is_representative": false}}, {"name": "호수집", "minutes": 0.6, "category": "한식", "broadcasts": ["김사원세끼"], "menu": {"name": "볶음밥", "price_won": 2000, "is_representative": false}}]

- 출발 후 2시간 이후에 먹고 싶어
  - 조건: `{"categories": [], "broadcasts": [], "menu_keywords": [], "excluded_keywords": [], "max_price_won": null, "target_minutes": null, "time_window_minutes": 30, "sort": "timing", "unverified": [], "clarification": null, "min_minutes": 120, "max_minutes": null, "price_exclusive": false, "menu_match": "any", "excluded_broadcasts": [], "required_unverified": [], "purpose": "meal"}`
  - 추천: [{"name": "차령짬뽕", "minutes": 129.2, "category": "중식", "broadcasts": ["쯔양"], "menu": {"name": "짬뽕", "price_won": 10000, "is_representative": true}}, {"name": "백김치새싹막회 우아본점", "minutes": 187.5, "category": "한식", "broadcasts": ["전현무계획"], "menu": {"name": "포장 소", "price_won": 45000, "is_representative": false}}, {"name": "진미반점", "minutes": 187.8, "category": "중식", "broadcasts": ["한국인의 밥상"], "menu": {"name": "짜장", "price_won": 7000, "is_representative": false}}]

- 돈까스와 냉면 둘 다 파는 곳
  - 조건: `{"categories": [], "broadcasts": [], "menu_keywords": ["돈까스", "냉면"], "excluded_keywords": [], "max_price_won": null, "target_minutes": null, "time_window_minutes": 30, "sort": "timing", "unverified": [], "clarification": null, "min_minutes": null, "max_minutes": null, "price_exclusive": false, "menu_match": "all", "excluded_broadcasts": [], "required_unverified": [], "purpose": "meal"}`
  - 추천: [{"name": "전주맛자랑", "minutes": 29.0, "category": "한식", "broadcasts": ["김사원세끼"], "menu": {"name": "매운돈까스", "price_won": 8000, "is_representative": false}}]

- 출발 후 한 시간쯤에 칼국수 1만원 미만
  - 조건: `{"categories": ["한식"], "broadcasts": [], "menu_keywords": ["칼국수"], "excluded_keywords": [], "max_price_won": 10000, "target_minutes": 60, "time_window_minutes": 30, "sort": "timing", "unverified": [], "clarification": null, "min_minutes": null, "max_minutes": null, "price_exclusive": true, "menu_match": "any", "excluded_broadcasts": [], "required_unverified": [], "purpose": "meal"}`
  - 추천: [{"name": "상갈분식", "minutes": 57.8, "category": "한식", "broadcasts": ["허영만의 백반기행"], "menu": {"name": "칼국수", "price_won": 7000, "is_representative": false}}, {"name": "정통집 강남점", "minutes": 31.8, "category": "한식", "broadcasts": ["김사원세끼"], "menu": {"name": "칼국수", "price_won": 7000, "is_representative": false}}]

- 한 시간쯤 뒤, 한식으로 2만 원 이하
  - 조건: `{"categories": ["한식"], "broadcasts": [], "menu_keywords": [], "excluded_keywords": [], "max_price_won": 20000, "target_minutes": 60, "time_window_minutes": 30, "sort": "timing", "unverified": [], "clarification": null, "min_minutes": null, "max_minutes": null, "price_exclusive": false, "menu_match": "any", "excluded_broadcasts": [], "required_unverified": [], "purpose": "meal"}`
  - 추천: [{"name": "상갈분식", "minutes": 57.8, "category": "한식", "broadcasts": ["허영만의 백반기행"], "menu": {"name": "떡국", "price_won": 6000, "is_representative": false}}, {"name": "이순실평양명가", "minutes": 63.3, "category": "한식", "broadcasts": ["흑백요리사"], "menu": {"name": "평양 물냉면", "price_won": 15000, "is_representative": true}}, {"name": "생아구한마리", "minutes": 63.5, "category": "한식", "broadcasts": ["맛있는 녀석들"], "menu": {"name": "산낙지탕탕", "price_won": 15000, "is_representative": false}}]

- 가장 저렴한 한 끼 추천해줘
  - 조건: `{"categories": [], "broadcasts": [], "menu_keywords": [], "excluded_keywords": [], "max_price_won": null, "target_minutes": null, "time_window_minutes": 30, "sort": "price", "unverified": [], "clarification": null, "min_minutes": null, "max_minutes": null, "price_exclusive": false, "menu_match": "any", "excluded_broadcasts": [], "required_unverified": [], "purpose": "meal"}`
  - 추천: [{"name": "창성옥", "minutes": 11.6, "category": "한식", "broadcasts": ["백년가게"], "menu": {"name": "후라이", "price_won": 500, "is_representative": false}}, {"name": "창성옥 본점", "minutes": 11.6, "category": "한식", "broadcasts": ["허영만의 백반기행"], "menu": {"name": "후라이", "price_won": 500, "is_representative": false}}, {"name": "잠원떡볶이", "minutes": 27.6, "category": "한식", "broadcasts": ["쯔양", "김사원세끼"], "menu": {"name": "고구마", "price_won": 700, "is_representative": false}}]

- 한식 2만원 이하, 주차 가능한 곳만
  - 조건: `{"categories": ["한식"], "broadcasts": [], "menu_keywords": [], "excluded_keywords": [], "max_price_won": 20000, "target_minutes": null, "time_window_minutes": 30, "sort": "timing", "unverified": ["주차 가능"], "clarification": "반드시 필요한 조건(주차 가능)을 확인할 수 없어 추천을 보류했어요. 이 조건은 직접 확인하고 메뉴·가격·시간으로 찾아볼까요?", "min_minutes": null, "max_minutes": null, "price_exclusive": false, "menu_match": "any", "excluded_broadcasts": [], "required_unverified": ["주차 가능"], "purpose": "meal"}`
  - 추천: []

- 주차는 내가 확인할게, 시간은 30분 이내로
  - 조건: `{"categories": ["한식"], "broadcasts": [], "menu_keywords": [], "excluded_keywords": [], "max_price_won": 20000, "target_minutes": null, "time_window_minutes": 30, "sort": "timing", "unverified": [], "clarification": null, "min_minutes": 0, "max_minutes": 30, "price_exclusive": false, "menu_match": "any", "excluded_broadcasts": [], "required_unverified": [], "purpose": "meal"}`
  - 추천: [{"name": "바다식당", "minutes": 15.0, "category": "한식", "broadcasts": ["맛있는 녀석들"], "menu": {"name": "칠면조쏘세지", "price_won": 13000, "is_representative": false}}, {"name": "나리의 집", "minutes": 15.0, "category": "한식", "broadcasts": ["김사원세끼"], "menu": {"name": "청국장", "price_won": 8000, "is_representative": false}}, {"name": "해피홈레스토랑", "minutes": 14.9, "category": "한식", "broadcasts": ["맛있는 녀석들"], "menu": {"name": "푸푸", "price_won": 4000, "is_representative": false}}]

- 처음부터. 조건 없이 추천해줘
  - 조건: `{"categories": [], "broadcasts": [], "menu_keywords": [], "excluded_keywords": [], "max_price_won": null, "target_minutes": null, "time_window_minutes": 30, "sort": "timing", "unverified": [], "clarification": null, "min_minutes": null, "max_minutes": null, "price_exclusive": false, "menu_match": "any", "excluded_broadcasts": [], "required_unverified": [], "purpose": "meal"}`
  - 추천: [{"name": "대우호프", "minutes": 0.0, "category": "술집", "broadcasts": ["김사원세끼"], "menu": {"name": "생맥주(500cc)", "price_won": 4500, "is_representative": false}}, {"name": "야키토리혼바", "minutes": 0.0, "category": "일식", "broadcasts": ["흑백요리사"], "menu": {"name": "오츠카레 코스", "price_won": 39000, "is_representative": true}}, {"name": "서령 본점", "minutes": 0.2, "category": "한식", "broadcasts": ["먹을텐데"], "menu": {"name": "서령 순면", "price_won": 17000, "is_representative": true}}]
