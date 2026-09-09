import { beforeEach, describe, expect, it, vi } from "vitest";
import { readFavorites, toFavorite } from "./favorites";
import type { RestaurantSummary } from "./api";

// vitest 환경이 node라 window가 없다 — readFavorites가 실제로 읽는 표면만 세워준다.
function stubStorage(getItem: () => string | null) {
  vi.stubGlobal("window", { localStorage: { getItem, setItem: () => {} } });
}

const restaurant: RestaurantSummary = {
  id: "r1",
  name: "국밥집",
  category: "한식",
  address: "서울시 중구",
  latitude: 37.5,
  longitude: 127.0,
  phone: null,
  hours: null,
  youtube_url: null,
  broadcasts: ["또간집"],
  menu: [],
};

describe("readFavorites", () => {
  beforeEach(() => vi.unstubAllGlobals());

  it("returns an empty list when nothing has been saved", () => {
    stubStorage(() => null);
    expect(readFavorites()).toEqual([]);
  });

  it("returns an empty list instead of throwing on malformed JSON", () => {
    stubStorage(() => "{not json");
    expect(readFavorites()).toEqual([]);
  });

  it("returns an empty list when the stored value is not an array", () => {
    stubStorage(() => JSON.stringify({ id: "r1" }));
    expect(readFavorites()).toEqual([]);
  });

  it("drops corrupted entries but keeps the valid ones", () => {
    const valid = toFavorite(restaurant);
    stubStorage(() => JSON.stringify([valid, { id: "missing-coords" }, null, "nope"]));

    const result = readFavorites();

    expect(result).toHaveLength(1);
    expect(result[0].id).toBe("r1");
  });

  it("returns an empty list when localStorage access throws", () => {
    stubStorage(() => {
      throw new Error("access denied");
    });
    expect(readFavorites()).toEqual([]);
  });
});

describe("toFavorite", () => {
  it("keeps only the fields the saved list needs to render and locate a place", () => {
    const favorite = toFavorite(restaurant);

    expect(favorite).toMatchObject({
      id: "r1",
      name: "국밥집",
      category: "한식",
      address: "서울시 중구",
      latitude: 37.5,
      longitude: 127.0,
    });
    expect(favorite.savedAt).toBeTypeOf("number");
  });
});
