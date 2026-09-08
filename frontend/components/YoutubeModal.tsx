"use client";

import { useEffect } from "react";
import { createPortal } from "react-dom";

export interface YoutubeModalProps {
  videoId: string;
  title: string;
  onClose: () => void;
}

export default function YoutubeModal({ videoId, title, onClose }: YoutubeModalProps) {
  useEffect(() => {
    function handleKeyDown(e: KeyboardEvent) {
      if (e.key === "Escape") onClose();
    }
    document.addEventListener("keydown", handleKeyDown);
    return () => document.removeEventListener("keydown", handleKeyDown);
  }, [onClose]);

  return createPortal(
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4"
      onClick={onClose}
    >
      {/* 높이가 아니라 폭만 제한하면 세로가 짧은 노트북에서 잘린다 — 패널 높이는
          헤더 + 폭×9/16으로 결정되는데, 오버레이는 세로 스크롤 없이 가운데 정렬이라
          넘치는 만큼 위아래가 동시에 깎여 나간다. 그래서 화면 높이에서 오버레이 여백
          (p-4 = 2rem)과 헤더(약 3.5rem)를 뺀 뒤 16/9를 곱해, 16:9를 유지한 채로 세로에
          들어가는 최대 폭을 직접 구한다. max-h는 헤더가 예상보다 커졌을 때의 안전장치. */}
      <div
        className="max-h-[calc(100dvh_-_2rem)] w-full max-w-[min(1344px,calc((100dvh_-_5.5rem)*16/9))] overflow-hidden rounded-2xl bg-surface shadow-2xl"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between px-4 py-3">
          <span className="truncate text-sm font-medium text-ink">{title}</span>
          <button
            type="button"
            onClick={onClose}
            aria-label="닫기"
            className="rounded-full p-1 text-ink-muted transition hover:bg-surface-hover hover:text-ink"
          >
            <svg viewBox="0 0 20 20" fill="none" className="h-5 w-5" aria-hidden="true">
              <path d="M5 5l10 10M15 5L5 15" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" />
            </svg>
          </button>
        </div>
        <div className="aspect-video w-full bg-black">
          <iframe
            src={`https://www.youtube.com/embed/${videoId}?autoplay=1`}
            title={title}
            allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture"
            allowFullScreen
            className="h-full w-full"
          />
        </div>
      </div>
    </div>,
    document.body
  );
}
