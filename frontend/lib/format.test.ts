import { describe, expect, it } from "vitest";
import { formatDuration, formatDistance, formatWon } from "./format";

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

describe("formatWon", () => {
  it("adds thousands separators and appends 원", () => {
    expect(formatWon(0)).toBe("0원");
    expect(formatWon(5000)).toBe("5,000원");
    expect(formatWon(16400)).toBe("16,400원");
    expect(formatWon(1234567)).toBe("1,234,567원");
  });
});
