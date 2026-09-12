export function formatDuration(totalSeconds: number): string {
  const totalMinutes = Math.floor(totalSeconds / 60);
  const hours = Math.floor(totalMinutes / 60);
  const minutes = totalMinutes % 60;

  if (hours === 0) {
    return `${minutes}분`;
  }
  return `${hours}시간 ${minutes}분`;
}

// 출발 후 1분 미만은 "출발 직후". 출발지 반경 안의 식당은 모두 경로 첫 구간에 투영되어
// 0~59초가 나오는데, 카드마다 "출발 후 0분"이 줄지어 보이면 계산이 고장난 것처럼 읽힌다.
export function formatDepartureOffset(totalSeconds: number): string {
  if (totalSeconds < 60) return "출발 직후";
  return `출발 후 ${formatDuration(totalSeconds)}`;
}

export function formatDistance(km: number): string {
  return `${km.toFixed(1)}km`;
}

export function formatWon(won: number): string {
  return `${won.toLocaleString("ko-KR")}원`;
}
