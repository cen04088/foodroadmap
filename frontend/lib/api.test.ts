import { afterEach, describe, expect, it, vi } from "vitest";
import { ApiError, fetchAllRestaurants, fetchRouteRestaurants } from "./api";

const FAKE_RESPONSE = {
  route: { total_distance_m: 15000, total_duration_sec: 1200, points: [] },
  restaurants: [],
};

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("fetchRouteRestaurants", () => {
  it("builds the query string and returns the parsed JSON on success", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => FAKE_RESPONSE,
    });
    vi.stubGlobal("fetch", fetchMock);

    const result = await fetchRouteRestaurants(
      {
        originLat: 37.5665,
        originLng: 126.978,
        destinationLat: 37.4979,
        destinationLng: 127.0276,
        broadcast: "또간집",
        category: "한식",
        radiusKm: 3,
      },
      "http://localhost:8000"
    );

    expect(result).toEqual(FAKE_RESPONSE);

    const calledUrl = new URL(fetchMock.mock.calls[0][0] as string);
    expect(calledUrl.origin + calledUrl.pathname).toBe("http://localhost:8000/api/route-restaurants");
    expect(calledUrl.searchParams.get("origin")).toBe("37.5665,126.978");
    expect(calledUrl.searchParams.get("destination")).toBe("37.4979,127.0276");
    expect(calledUrl.searchParams.get("broadcast")).toBe("또간집");
    expect(calledUrl.searchParams.get("category")).toBe("한식");
    expect(calledUrl.searchParams.get("radius_km")).toBe("3");
  });

  it("omits radius_km from the query string when not provided", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => FAKE_RESPONSE,
    });
    vi.stubGlobal("fetch", fetchMock);

    await fetchRouteRestaurants(
      { originLat: 0, originLng: 0, destinationLat: 0, destinationLng: 0 },
      "http://localhost:8000"
    );

    const calledUrl = new URL(fetchMock.mock.calls[0][0] as string);
    expect(calledUrl.searchParams.has("radius_km")).toBe(false);
  });

  it("throws ApiError with the response status on a non-ok response", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: false,
      status: 502,
      json: async () => ({}),
    });
    vi.stubGlobal("fetch", fetchMock);

    const params = { originLat: 0, originLng: 0, destinationLat: 0, destinationLng: 0 };
    let caught: unknown;
    try {
      await fetchRouteRestaurants(params, "http://localhost:8000");
    } catch (err) {
      caught = err;
    }

    expect(caught).toBeInstanceOf(ApiError);
    expect((caught as ApiError).status).toBe(502);
  });

  it("throws ApiError with status 0 when the network request itself fails", async () => {
    const fetchMock = vi.fn().mockRejectedValue(new TypeError("network down"));
    vi.stubGlobal("fetch", fetchMock);

    const params = { originLat: 0, originLng: 0, destinationLat: 0, destinationLng: 0 };
    let caught: unknown;
    try {
      await fetchRouteRestaurants(params, "http://localhost:8000");
    } catch (err) {
      caught = err;
    }

    expect(caught).toBeInstanceOf(ApiError);
    expect((caught as ApiError).status).toBe(0);
  });
});

describe("fetchAllRestaurants", () => {
  const RESTAURANT = {
    id: "r1",
    name: "테스트식당",
    category: "한식",
    address: null,
    latitude: 37.5,
    longitude: 127.0,
    phone: null,
    hours: null,
    youtube_url: null,
    broadcasts: [],
  };

  it("requests /api/restaurants with no query string when no filters are given", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({ restaurants: [RESTAURANT] }),
    });
    vi.stubGlobal("fetch", fetchMock);

    const result = await fetchAllRestaurants({}, "http://localhost:8000");

    expect(result).toEqual([RESTAURANT]);
    expect(fetchMock.mock.calls[0][0]).toBe("http://localhost:8000/api/restaurants");
  });

  it("includes broadcast and category as query params when provided", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({ restaurants: [] }),
    });
    vi.stubGlobal("fetch", fetchMock);

    await fetchAllRestaurants({ broadcast: "또간집", category: "한식" }, "http://localhost:8000");

    const calledUrl = new URL(fetchMock.mock.calls[0][0] as string);
    expect(calledUrl.searchParams.get("broadcast")).toBe("또간집");
    expect(calledUrl.searchParams.get("category")).toBe("한식");
  });

  it("throws ApiError with the response status on a non-ok response", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: false,
      status: 500,
      json: async () => ({}),
    });
    vi.stubGlobal("fetch", fetchMock);

    let caught: unknown;
    try {
      await fetchAllRestaurants({}, "http://localhost:8000");
    } catch (err) {
      caught = err;
    }

    expect(caught).toBeInstanceOf(ApiError);
    expect((caught as ApiError).status).toBe(500);
  });
});
