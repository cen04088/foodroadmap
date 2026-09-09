// 가격 구간은 UI(버튼 라벨)와 두 종류의 필터링(브라우즈 모드는 서버 쿼리, 경로 모드는
// 클라이언트 필터)에서 모두 쓰이므로 한 곳에 모아둔다. 기준 가격은 서버가 내려주는
// reference_price_won — 대표 메뉴 최저가, 없으면 전체 메뉴 최저가다.
export interface PriceBucket {
  value: string;
  label: string;
  minPrice?: number;
  maxPrice?: number;
}

export const PRICE_BUCKETS: PriceBucket[] = [
  { value: "", label: "전체" },
  { value: "under-10000", label: "1만원 이하", maxPrice: 10000 },
  { value: "10000-20000", label: "1~2만원", minPrice: 10000, maxPrice: 20000 },
  { value: "20000-30000", label: "2~3만원", minPrice: 20000, maxPrice: 30000 },
  { value: "over-30000", label: "3만원 이상", minPrice: 30000 },
];

export function findPriceBucket(value: string): PriceBucket | null {
  if (!value) return null;
  return PRICE_BUCKETS.find((b) => b.value === value) ?? null;
}

export function matchesPriceBucket(referencePriceWon: number | null, bucketValue: string): boolean {
  const bucket = findPriceBucket(bucketValue);
  if (!bucket) return true;
  // 가격을 모르는 가게는 구간을 지정한 순간 제외한다 — 서버 쪽 _apply_price_filter와 같은 규칙.
  if (referencePriceWon === null) return false;
  if (bucket.minPrice !== undefined && referencePriceWon < bucket.minPrice) return false;
  if (bucket.maxPrice !== undefined && referencePriceWon > bucket.maxPrice) return false;
  return true;
}
