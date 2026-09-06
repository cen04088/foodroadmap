export const BROADCAST_IMAGES: Record<string, string> = {
  또간집: "/broadcasts/ttoganjib.jpg",
  전현무계획: "/broadcasts/jeonhyeonmu.jpg",
  쯔양: "/broadcasts/tzuyang.jpg",
  비밀이야: "/broadcasts/bimirya.jpg",
  "허영만의 백반기행": "/broadcasts/baekban.jpg",
  백년가게: "/broadcasts/baengnyeon.jpg",
  "맛있는 녀석들": "/broadcasts/matnyeoseok.jpg",
  김사원세끼: "/broadcasts/kimsawon.jpg",
  "한국인의 밥상": "/broadcasts/bapsang.jpg",
  흑백요리사: "/broadcasts/heukbaek.jpg",
  먹을텐데: "/broadcasts/meogeulteonde.jpg",
  "공간 탐닉": "/broadcasts/tamnik.jpg",
  "쯔양 몇끼": "/broadcasts/myeotkki.jpg",
  동네한바퀴: "/broadcasts/kimyoungchul.jpg",
};

export function getBroadcastImage(name: string): string | null {
  return BROADCAST_IMAGES[name] ?? null;
}
