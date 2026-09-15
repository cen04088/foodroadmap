export interface RoutePoint {
  lat: number;
  lng: number;
  cumulative_distance_m: number;
  cumulative_time_sec: number;
}

export interface MenuItemSummary {
  name: string;
  price_won: number | null;
  is_representative: boolean;
}

export interface RestaurantSummary {
  id: string;
  name: string;
  category: string | null;
  address: string | null;
  latitude: number;
  longitude: number;
  phone: string | null;
  hours: string | null;
  youtube_url: string | null;
  broadcasts: string[];
  menu: MenuItemSummary[];
}

export interface RestaurantResult extends RestaurantSummary {
  distance_from_route_km: number;
  cumulative_time_sec: number;
}

export interface EndpointAdjustment {
  lat: number;
  lng: number;
  // 0이면 좌표는 그대로 두고 교통 통제(유고) 정보만 제외해 계산했다는 뜻.
  offset_m: number;
  reason: string;
}

export interface RouteRestaurantsResponse {
  meal_context_id?: string;
  // 출발/도착지 주변 도로 문제로 좌표를 가까운 도로 지점으로 옮겨 계산했을 때만 값이 채워진다.
  adjustments?: { origin: EndpointAdjustment | null; destination: EndpointAdjustment | null };
  route: {
    total_distance_m: number;
    total_duration_sec: number;
    points: RoutePoint[];
  };
  restaurants: RestaurantResult[];
}

export interface MealPreferences {
  min_minutes?: number | null;
  max_minutes?: number | null;
  price_exclusive?: boolean;
  menu_match?: "any" | "all";
  excluded_broadcasts?: string[];
  required_unverified?: string[];
  purpose?: "meal" | "snack";
  categories: string[];
  broadcasts: string[];
  menu_keywords: string[];
  excluded_keywords: string[];
  max_price_won: number | null;
  target_minutes: number | null;
  time_window_minutes: number;
  sort: "timing" | "earliest" | "price";
  unverified: string[];
  clarification: string | null;
}

export interface MealRecommendationResponse {
  preferences: MealPreferences;
  reply: string;
  notes: string[];
  matched_count: number;
  recommendations: {
    restaurant_id: string;
    reasons: string[];
    menu: MenuItemSummary | null;
  }[];
}

export async function fetchMealRecommendations(
  params: { route_context_id: string; message: string; previous: MealPreferences | null },
  signal?: AbortSignal,
  baseUrl = process.env.NEXT_PUBLIC_API_BASE_URL ?? "",
): Promise<MealRecommendationResponse> {
  let response: Response;
  try {
    response = await fetch(`${baseUrl}/api/meal-recommendations`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(params),
      signal,
    });
  } catch (error) {
    if (signal?.aborted) throw error;
    throw new ApiError(0, "서버에 연결하지 못했어요. 연결 상태를 확인하고 다시 시도해주세요.");
  }
  if (!response.ok) {
    const data = await response.json().catch(() => null);
    throw new ApiError(response.status, typeof data?.detail === "string"
      ? data.detail : "추천을 불러오지 못했어요. 잠시 후 다시 시도해주세요.");
  }
  return response.json();
}

export class ApiError extends Error {
  status: number;

  constructor(status: number, message: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

export interface FetchRouteRestaurantsParams {
  originLat: number;
  originLng: number;
  destinationLat: number;
  destinationLng: number;
  broadcast?: string;
  category?: string;
  radiusKm?: number;
}

export interface BroadcastSummary {
  slug: string;
  name: string;
  count: number;
}

async function fetchJson<T>(path: string, baseUrl: string): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${baseUrl}${path}`);
  } catch {
    throw new ApiError(0, "네트워크 오류: 서버에 연결할 수 없습니다");
  }

  if (!response.ok) {
    // 서버가 detail 문자열을 주면 그대로 살린다 — 경로 오류처럼 카카오가 준 사유를 사용자에게 보여줘야 한다.
    const detail = await readDetail(response);
    throw new ApiError(response.status, detail ?? `요청 실패: ${response.status}`);
  }

  return response.json() as Promise<T>;
}

async function readDetail(response: Response): Promise<string | null> {
  if (typeof response.json !== "function") return null;
  const data: unknown = await response.json().catch(() => null);
  const detail = (data as { detail?: unknown } | null)?.detail;
  return typeof detail === "string" && detail.trim() ? detail : null;
}

export async function fetchRouteRestaurants(
  params: FetchRouteRestaurantsParams,
  baseUrl: string = process.env.NEXT_PUBLIC_API_BASE_URL ?? ""
): Promise<RouteRestaurantsResponse> {
  const query = new URLSearchParams({
    origin: `${params.originLat},${params.originLng}`,
    destination: `${params.destinationLat},${params.destinationLng}`,
  });
  if (params.broadcast) query.set("broadcast", params.broadcast);
  if (params.category) query.set("category", params.category);
  // 반경은 프론트에서 안 보내고 백엔드 기본값(2km)에 맡긴다 — 사용자가 고르는 UI를
  // 없앴으므로 기본값을 양쪽에 중복해두지 않는다. 파라미터 자체는 남겨둔다.
  if (params.radiusKm) query.set("radius_km", String(params.radiusKm));

  return fetchJson<RouteRestaurantsResponse>(`/api/route-restaurants?${query.toString()}`, baseUrl);
}

export interface BroadcastOverview {
  broadcasts: BroadcastSummary[];
  // 좌표가 있고 서비스에 보이는 식당의 고유 개수. 방송별 count 합계는 여러 방송에 나온 곳을 중복 센다.
  total_restaurants: number;
}

export async function fetchBroadcastOverview(
  baseUrl: string = process.env.NEXT_PUBLIC_API_BASE_URL ?? ""
): Promise<BroadcastOverview> {
  return fetchJson<BroadcastOverview>("/api/broadcasts", baseUrl);
}

export async function fetchBroadcasts(
  baseUrl: string = process.env.NEXT_PUBLIC_API_BASE_URL ?? ""
): Promise<BroadcastSummary[]> {
  const data = await fetchJson<{ broadcasts: BroadcastSummary[] }>("/api/broadcasts", baseUrl);
  return data.broadcasts;
}

export interface MapBounds {
  minLat: number;
  maxLat: number;
  minLng: number;
  maxLng: number;
}

export interface FetchAllRestaurantsParams {
  broadcast?: string;
  category?: string;
  bounds?: MapBounds;
}

export async function fetchAllRestaurants(
  params: FetchAllRestaurantsParams = {},
  baseUrl: string = process.env.NEXT_PUBLIC_API_BASE_URL ?? ""
): Promise<RestaurantSummary[]> {
  const query = new URLSearchParams();
  if (params.broadcast) query.set("broadcast", params.broadcast);
  if (params.category) query.set("category", params.category);
  if (params.bounds) {
    query.set("min_lat", String(params.bounds.minLat));
    query.set("max_lat", String(params.bounds.maxLat));
    query.set("min_lng", String(params.bounds.minLng));
    query.set("max_lng", String(params.bounds.maxLng));
  }

  const qs = query.toString();
  const data = await fetchJson<{ restaurants: RestaurantSummary[] }>(
    `/api/restaurants${qs ? `?${qs}` : ""}`,
    baseUrl
  );
  return data.restaurants;
}

export type SuggestionKind = "improvement" | "broadcast";

export interface SubmitSuggestionParams {
  kind: SuggestionKind;
  body: string;
  contact?: string;
}

export async function submitSuggestion(
  params: SubmitSuggestionParams,
  baseUrl: string = process.env.NEXT_PUBLIC_API_BASE_URL ?? ""
): Promise<void> {
  let response: Response;
  try {
    response = await fetch(`${baseUrl}/api/suggestions`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        kind: params.kind,
        body: params.body,
        // 빈 문자열을 보내면 서버가 공백으로 받아 null 처리하지만, 아예 안 보내는 게 명확하다.
        ...(params.contact ? { contact: params.contact } : {}),
      }),
    });
  } catch {
    throw new ApiError(0, "네트워크 오류: 서버에 연결할 수 없습니다");
  }

  if (!response.ok) {
    throw new ApiError(response.status, `요청 실패: ${response.status}`);
  }
}
