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

export interface RouteRestaurantsResponse {
  route: {
    total_distance_m: number;
    total_duration_sec: number;
    points: RoutePoint[];
  };
  restaurants: RestaurantResult[];
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
    throw new ApiError(response.status, `요청 실패: ${response.status}`);
  }

  return response.json() as Promise<T>;
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
