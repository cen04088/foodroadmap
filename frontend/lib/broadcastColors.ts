export interface BroadcastColor {
  color: string;
  letter: string;
}

export const BROADCAST_COLORS: Record<string, BroadcastColor> = {
  또간집: { color: "#E11D48", letter: "또" },
  흑백요리사: { color: "#27272A", letter: "흑" },
  쯔양: { color: "#DB2777", letter: "쯔" },
  "쯔양 몇끼": { color: "#F472B6", letter: "몇" },
  먹을텐데: { color: "#D97706", letter: "먹" },
  전현무계획: { color: "#2563EB", letter: "전" },
  "허영만의 백반기행": { color: "#65A30D", letter: "허" },
  "한국인의 밥상": { color: "#9333EA", letter: "한" },
  "맛있는 녀석들": { color: "#0D9488", letter: "맛" },
  동네한바퀴: { color: "#0891B2", letter: "동" },
  백년가게: { color: "#92400E", letter: "백" },
  비밀이야: { color: "#4F46E5", letter: "비" },
  "공간 탐닉": { color: "#0284C7", letter: "공" },
  김사원세끼: { color: "#16A34A", letter: "김" },
};

export const DEFAULT_BROADCAST_COLOR: BroadcastColor = { color: "#78716C", letter: "?" };

export function getBroadcastColor(name: string): BroadcastColor {
  return BROADCAST_COLORS[name] ?? DEFAULT_BROADCAST_COLOR;
}
