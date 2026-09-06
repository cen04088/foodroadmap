export function formatDuration(totalSeconds: number): string {
  const totalMinutes = Math.floor(totalSeconds / 60);
  const hours = Math.floor(totalMinutes / 60);
  const minutes = totalMinutes % 60;

  if (hours === 0) {
    return `${minutes}분`;
  }
  return `${hours}시간 ${minutes}분`;
}

export function formatDistance(km: number): string {
  return `${km.toFixed(1)}km`;
}

export function formatWon(won: number): string {
  return `${won.toLocaleString("ko-KR")}원`;
}
