import { describe, expect, it } from "vitest";
import { groupByMealWindow, mealWindowAt } from "./mealSections";

// 로컬 시각 기준으로 만든다 — 함수도 getHours()로 로컬 시각을 읽으므로 실행 환경의 시간대와 무관하다.
const at = (hour: number, minute = 0) => new Date(2026, 9, 12, hour, minute);
const stop = (id: string, minutesAfter: number) => ({ id, cumulative_time_sec: minutesAfter * 60 });

describe("mealWindowAt", () => {
  it("includes the start minute and excludes the end minute", () => {
    expect(mealWindowAt(at(11, 0))?.name).toBe("점심");
    expect(mealWindowAt(at(13, 59))?.name).toBe("점심");
    expect(mealWindowAt(at(14, 0))).toBeNull();
    expect(mealWindowAt(at(10, 59))).toBeNull();
  });
});

describe("groupByMealWindow", () => {
  it("returns null when nothing is passed during a meal window", () => {
    expect(groupByMealWindow([stop("a", 10), stop("b", 50)], at(14, 30))).toBeNull();
  });

  it("splits the route into before / during / after lunch without reordering", () => {
    const items = [stop("a", 5), stop("b", 40), stop("c", 90), stop("d", 240)];
    const sections = groupByMealWindow(items, at(10, 30))!;

    expect(sections.map((s) => s.label)).toEqual(["점심 전", "점심 시간대", "점심 후"]);
    expect(sections.map((s) => s.items.map((i) => i.id))).toEqual([["a"], ["b", "c"], ["d"]]);
    expect(sections.map((s) => s.startIndex)).toEqual([0, 1, 3]);
  });

  it("records the first and last arrival of each section", () => {
    const [, lunch] = groupByMealWindow([stop("a", 5), stop("b", 40), stop("c", 90)], at(10, 30))!;
    expect(lunch.firstArrival).toEqual(at(11, 10));
    expect(lunch.lastArrival).toEqual(at(12, 0));
  });

  it("names the gap between two meals after the earlier one", () => {
    const items = [stop("a", 30), stop("b", 200), stop("c", 330)];
    const sections = groupByMealWindow(items, at(12, 0))!;
    expect(sections.map((s) => s.label)).toEqual(["점심 시간대", "점심 후", "저녁 시간대"]);
  });

  it("starts with the meal section when departing during a meal", () => {
    const [first] = groupByMealWindow([stop("a", 0), stop("b", 20)], at(12, 0))!;
    expect(first).toMatchObject({ label: "점심 시간대", startIndex: 0 });
  });

  it("follows arrivals past midnight into the next morning", () => {
    const sections = groupByMealWindow([stop("a", 60), stop("b", 9 * 60)], at(23, 0))!;
    expect(sections.map((s) => s.label)).toEqual(["아침 전", "아침 시간대"]);
  });
});
