// 지금 출발한다고 보고 각 식당을 지나는 시각을 계산해, 식사 시간대에 지나는 구간을 묶는다.
// 목록 순서(지나가는 순서)는 바꾸지 않고 구간 제목만 붙인다 — 순서를 바꾸면 카드 번호와
// "지나가는 순서대로 N곳" 안내가 어긋난다. 대신 화면은 첫 식사 구간으로 내려서 보여준다.

export interface MealWindow {
  name: string;
  startMinute: number;
  endMinute: number;
}

export const MEAL_WINDOWS: MealWindow[] = [
  { name: "아침", startMinute: 7 * 60, endMinute: 9 * 60 },
  { name: "점심", startMinute: 11 * 60, endMinute: 14 * 60 },
  { name: "저녁", startMinute: 17 * 60, endMinute: 20 * 60 },
];

export interface RouteSection<T> {
  // null이면 식사 시간대 밖의 구간
  meal: MealWindow | null;
  label: string;
  // 경로 전체 목록에서 이 구간 첫 항목의 위치 — 카드 순번을 이어 매기는 데 쓴다.
  startIndex: number;
  items: T[];
  firstArrival: Date;
  lastArrival: Date;
}

export function mealWindowAt(date: Date): MealWindow | null {
  const minute = date.getHours() * 60 + date.getMinutes();
  return MEAL_WINDOWS.find((w) => minute >= w.startMinute && minute < w.endMinute) ?? null;
}

// 식사 시간대에 지나는 곳이 하나도 없으면 null — 구간 제목 없이 예전처럼 한 줄로 보여준다.
// items는 지나가는 순서(cumulative_time_sec 오름차순)로 정렬돼 있어야 한다 — 서버가 그렇게 내려준다.
export function groupByMealWindow<T extends { cumulative_time_sec: number }>(
  items: T[],
  departure: Date,
): RouteSection<T>[] | null {
  const runs: Omit<RouteSection<T>, "label">[] = [];
  items.forEach((item, index) => {
    const arrival = new Date(departure.getTime() + item.cumulative_time_sec * 1000);
    const meal = mealWindowAt(arrival);
    const last = runs[runs.length - 1];
    if (last && last.meal === meal) {
      last.items.push(item);
      last.lastArrival = arrival;
      return;
    }
    runs.push({ meal, startIndex: index, items: [item], firstArrival: arrival, lastArrival: arrival });
  });

  if (!runs.some((run) => run.meal)) return null;

  return runs.map((run, i) => {
    if (run.meal) return { ...run, label: `${run.meal.name} 시간대` };
    // 식사 시간대 밖 구간은 앞뒤 식사에 붙여 부른다: 첫 식사 전이면 "점심 전", 그 뒤면 "점심 후".
    const previous = runs.slice(0, i).reverse().find((r) => r.meal)?.meal;
    const next = runs.slice(i + 1).find((r) => r.meal)?.meal;
    return { ...run, label: previous ? `${previous.name} 후` : `${next!.name} 전` };
  });
}
