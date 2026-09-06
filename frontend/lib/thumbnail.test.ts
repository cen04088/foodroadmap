import { describe, expect, it } from "vitest";
import { getRestaurantThumbnailUrl } from "./thumbnail";

describe("getRestaurantThumbnailUrl", () => {
  it("prefers the youtube thumbnail when a youtube_url is present", () => {
    const url = getRestaurantThumbnailUrl({
      youtube_url: "https://www.youtube.com/watch?v=abc123",
      broadcasts: ["흑백요리사"],
    });

    expect(url).toBe("https://i.ytimg.com/vi/abc123/hqdefault.jpg");
  });

  it("falls back to the broadcast image when there is no youtube_url", () => {
    const url = getRestaurantThumbnailUrl({
      youtube_url: null,
      broadcasts: ["흑백요리사"],
    });

    expect(url).toBe("/broadcasts/heukbaek.jpg");
  });

  it("returns null when neither a youtube video nor a mapped broadcast image exists", () => {
    const url = getRestaurantThumbnailUrl({
      youtube_url: null,
      broadcasts: ["존재하지않는방송"],
    });

    expect(url).toBeNull();
  });

  it("returns null when there are no broadcasts at all", () => {
    const url = getRestaurantThumbnailUrl({ youtube_url: null, broadcasts: [] });

    expect(url).toBeNull();
  });
});
