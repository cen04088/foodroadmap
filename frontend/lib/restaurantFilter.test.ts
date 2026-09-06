import { describe, expect, it } from "vitest";
import { matchesFilters } from "./restaurantFilter";

describe("matchesFilters", () => {
  const restaurant = { broadcasts: ["또간집", "먹을텐데"], category: "한식" };

  it("matches everything when no filter is set", () => {
    expect(matchesFilters(restaurant, { broadcast: "", category: "" })).toBe(true);
  });

  it("matches when the restaurant has the filtered broadcast", () => {
    expect(matchesFilters(restaurant, { broadcast: "먹을텐데", category: "" })).toBe(true);
  });

  it("does not match when the restaurant lacks the filtered broadcast", () => {
    expect(matchesFilters(restaurant, { broadcast: "쯔양", category: "" })).toBe(false);
  });

  it("matches when the category is exactly equal", () => {
    expect(matchesFilters(restaurant, { broadcast: "", category: "한식" })).toBe(true);
  });

  it("does not match when the category differs", () => {
    expect(matchesFilters(restaurant, { broadcast: "", category: "일식" })).toBe(false);
  });

  it("requires both broadcast and category to match when both are set", () => {
    expect(matchesFilters(restaurant, { broadcast: "또간집", category: "일식" })).toBe(false);
    expect(matchesFilters(restaurant, { broadcast: "또간집", category: "한식" })).toBe(true);
  });

  it("never matches a restaurant with no category when a category filter is set", () => {
    const noCategory = { broadcasts: ["또간집"], category: null };
    expect(matchesFilters(noCategory, { broadcast: "", category: "한식" })).toBe(false);
  });
});
