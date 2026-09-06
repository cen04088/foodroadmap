export interface RoutePoint {
  lat: number;
  lng: number;
  cumulative_distance_m: number;
  cumulative_time_sec: number;
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
