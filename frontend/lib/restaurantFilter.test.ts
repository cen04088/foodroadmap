import { describe, expect, it } from "vitest";
import { matchesFilters } from "./restaurantFilter";

const NO_FILTERS = { broadcast: "", category: "", priceBucket: "" };

describe("matchesFilters", () => {
  const restaurant = { broadcasts: ["또간집", "먹을텐데"], category: "한식", reference_price_won: 12000 };

  it("matches everything when no filter is set", () => {
    expect(matchesFilters(restaurant, NO_FILTERS)).toBe(true);
  });

  it("matches when the restaurant has the filtered broadcast", () => {
    expect(matchesFilters(restaurant, { ...NO_FILTERS, broadcast: "먹을텐데" })).toBe(true);
  });

  it("does not match when the restaurant lacks the filtered broadcast", () => {
    expect(matchesFilters(restaurant, { ...NO_FILTERS, broadcast: "쯔양" })).toBe(false);
  });

  it("matches when the category is exactly equal", () => {
    expect(matchesFilters(restaurant, { ...NO_FILTERS, category: "한식" })).toBe(true);
  });

  it("does not match when the category differs", () => {
    expect(matchesFilters(restaurant, { ...NO_FILTERS, category: "일식" })).toBe(false);
  });

  it("requires both broadcast and category to match when both are set", () => {
    expect(matchesFilters(restaurant, { ...NO_FILTERS, broadcast: "또간집", category: "일식" })).toBe(false);
    expect(matchesFilters(restaurant, { ...NO_FILTERS, broadcast: "또간집", category: "한식" })).toBe(true);
  });

  it("never matches a restaurant with no category when a category filter is set", () => {
    const noCategory = { broadcasts: ["또간집"], category: null, reference_price_won: 12000 };
    expect(matchesFilters(noCategory, { ...NO_FILTERS, category: "한식" })).toBe(false);
  });

  it("matches when the reference price falls inside the bucket", () => {
    expect(matchesFilters(restaurant, { ...NO_FILTERS, priceBucket: "10000-20000" })).toBe(true);
  });

  it("does not match when the reference price falls outside the bucket", () => {
    expect(matchesFilters(restaurant, { ...NO_FILTERS, priceBucket: "under-10000" })).toBe(false);
    expect(matchesFilters(restaurant, { ...NO_FILTERS, priceBucket: "over-30000" })).toBe(false);
  });

  it("excludes restaurants with an unknown price once a bucket is chosen", () => {
    const noPrice = { broadcasts: ["또간집"], category: "한식", reference_price_won: null };
    expect(matchesFilters(noPrice, NO_FILTERS)).toBe(true);
    expect(matchesFilters(noPrice, { ...NO_FILTERS, priceBucket: "under-10000" })).toBe(false);
  });
});
