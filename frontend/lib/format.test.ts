import { describe, expect, it } from "vitest";
import { formatDuration, formatDistance } from "./format";

describe("formatDuration", () => {
  it("formats under an hour as minutes only", () => {
    expect(formatDuration(0)).toBe("0분");
    expect(formatDuration(59)).toBe("0분");
    expect(formatDuration(60)).toBe("1분");
    expect(formatDuration(45 * 60)).toBe("45분");
  });

  it("formats an hour or more as hours and minutes", () => {
    expect(formatDuration(60 * 60)).toBe("1시간 0분");
    expect(formatDuration(80 * 60)).toBe("1시간 20분");
    expect(formatDuration(125 * 60)).toBe("2시간 5분");
  });
});

describe("formatDistance", () => {
  it("rounds to one decimal place and appends km", () => {
    expect(formatDistance(0)).toBe("0.0km");
    expect(formatDistance(1.234)).toBe("1.2km");
    expect(formatDistance(1.98)).toBe("2.0km");
  });
});
