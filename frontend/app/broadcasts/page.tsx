"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { ApiError, fetchBroadcasts, type BroadcastSummary } from "../../lib/api";
import { getBroadcastColor } from "../../lib/broadcastColors";

export default function BroadcastsPage() {
  const [broadcasts, setBroadcasts] = useState<BroadcastSummary[] | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  useEffect(() => {
    fetchBroadcasts()
      .then(setBroadcasts)
      .catch((error: unknown) => {
        setErrorMessage(
          error instanceof ApiError && error.status === 0
            ? "서버에 연결할 수 없습니다"
            : "목록을 불러오지 못했습니다"
        );
      });
  }, []);

  return (
    <main className="mx-auto flex w-full max-w-[1400px] flex-col gap-5 p-4 sm:p-6">
      <div>
        <Link href="/" className="text-sm text-ink-muted transition hover:text-ink">
          ← 경로 검색으로
        </Link>
        <h1 className="mt-2 text-xl font-semibold text-ink">방송·유튜브별로 보기</h1>
        <p className="mt-1 text-sm text-ink-muted">보고 싶은 방송을 눌러 근처 맛집을 확인하세요</p>
      </div>

      {errorMessage && (
        <div className="rounded-xl border border-danger/20 bg-danger-soft px-4 py-3 text-sm text-danger-ink">
          {errorMessage}
        </div>
      )}

      {!broadcasts && !errorMessage && <p className="text-sm text-ink-muted">불러오는 중...</p>}

      {broadcasts && (
        <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-4">
          {broadcasts.map((b) => {
            const { color, letter } = getBroadcastColor(b.name);
            return (
              <Link
                key={b.slug}
                href={`/?broadcast=${encodeURIComponent(b.name)}`}
                className="overflow-hidden rounded-2xl border border-line bg-surface transition hover:shadow-md hover:shadow-black/5"
              >
                <div className="h-1.5" style={{ backgroundColor: color }} />
                <div className="flex items-center gap-3 p-4">
                  <div
                    className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full text-sm font-bold text-white"
                    style={{ backgroundColor: color }}
                  >
                    {letter}
                  </div>
                  <div className="min-w-0">
                    <div className="truncate font-medium text-ink">{b.name}</div>
                    <div className="text-sm text-ink-muted">{b.count}곳</div>
                  </div>
                </div>
              </Link>
            );
          })}
        </div>
      )}
    </main>
  );
}
