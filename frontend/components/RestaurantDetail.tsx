"use client";

import { useState } from "react";
import { formatDistance, formatDuration } from "../lib/format";
import type { RestaurantResult } from "../lib/api";
import { getBroadcastColor } from "../lib/broadcastColors";

export interface RestaurantDetailProps {
  restaurant: RestaurantResult;
  onBack: () => void;
}

function BackIcon() {
  return (
    <svg viewBox="0 0 20 20" fill="none" className="h-4 w-4" aria-hidden="true">
      <path d="M12.5 4.5L6.5 10l6 5.5" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

function PinIcon() {
  return (
    <svg viewBox="0 0 20 20" fill="none" className="mt-0.5 h-4 w-4 shrink-0 text-ink-muted" aria-hidden="true">
      <path
        d="M10 18s6-5.2 6-9.8A6 6 0 0 0 4 8.2C4 12.8 10 18 10 18Z"
        stroke="currentColor"
        strokeWidth="1.5"
        strokeLinejoin="round"
      />
      <circle cx="10" cy="8.2" r="2" stroke="currentColor" strokeWidth="1.5" />
    </svg>
  );
}

function PhoneIcon() {
  return (
    <svg viewBox="0 0 20 20" fill="none" className="h-4 w-4 shrink-0 text-ink-muted" aria-hidden="true">
      <path
        d="M6 3.5c.5 0 1.4 1.9 1.4 2.4 0 .7-1.1 1.1-1.1 1.8 0 1.4 2.5 3.9 3.9 3.9.7 0 1.1-1.1 1.8-1.1.5 0 2.4.9 2.4 1.4 0 1-1.3 2.1-2.3 2.1-1.9 0-4.2-1.4-5.9-3.1S3.5 7.4 3.5 5.5c0-1 1.1-2 2.5-2Z"
        stroke="currentColor"
        strokeWidth="1.4"
        strokeLinejoin="round"
      />
    </svg>
  );
}

function ClockIcon() {
  return (
    <svg viewBox="0 0 20 20" fill="none" className="h-4 w-4 shrink-0 text-ink-muted" aria-hidden="true">
      <circle cx="10" cy="10" r="6.5" stroke="currentColor" strokeWidth="1.4" />
      <path d="M10 6.5V10l2.5 1.5" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

function CopyIcon() {
  return (
    <svg viewBox="0 0 20 20" fill="none" className="h-3.5 w-3.5" aria-hidden="true">
      <rect x="7" y="7" width="9" height="9" rx="1.5" stroke="currentColor" strokeWidth="1.4" />
      <path d="M4.5 12.5v-7A1.5 1.5 0 0 1 6 4h7" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" />
    </svg>
  );
}

export default function RestaurantDetail({ restaurant, onBack }: RestaurantDetailProps) {
  const [copied, setCopied] = useState(false);

  async function handleCopyAddress() {
    if (!restaurant.address) return;
    try {
      await navigator.clipboard.writeText(restaurant.address);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      // 클립보드 접근이 막힌 환경(권한 거부 등)에서는 조용히 무시한다.
    }
  }

  const kakaoMapUrl = `https://map.kakao.com/link/to/${encodeURIComponent(restaurant.name)},${restaurant.latitude},${restaurant.longitude}`;

  return (
    <div className="flex h-full flex-col">
      <button
        type="button"
        onClick={onBack}
        className="flex w-fit items-center gap-1.5 rounded-lg px-1.5 py-1 text-sm text-ink-muted transition hover:text-ink"
      >
        <BackIcon />
        목록으로
      </button>

      <div className="mt-2 flex-1 overflow-y-auto pb-1">
        <div className="flex items-start justify-between gap-3">
          <h2 className="text-lg font-semibold leading-snug text-ink">{restaurant.name}</h2>
          {restaurant.category && (
            <span className="mt-0.5 shrink-0 rounded-full bg-surface-hover px-2.5 py-0.5 text-xs font-medium text-ink-muted">
              {restaurant.category}
            </span>
          )}
        </div>

        {restaurant.broadcasts.length > 0 && (
          <div className="mt-2 flex flex-wrap gap-1.5">
            {restaurant.broadcasts.map((b) => (
              <span
                key={b}
                style={{ backgroundColor: getBroadcastColor(b).color }}
                className="rounded-full px-2 py-0.5 text-xs font-medium text-white"
              >
                {b}
              </span>
            ))}
          </div>
        )}

        <div className="mt-4 rounded-xl bg-accent-soft px-4 py-3 text-sm text-ink">
          경로에서 {formatDistance(restaurant.distance_from_route_km)} · 출발 후{" "}
          {formatDuration(restaurant.cumulative_time_sec)} 지점
        </div>

        <div className="mt-4 flex flex-col gap-3 border-t border-line pt-4">
          {restaurant.address && (
            <div className="flex items-start justify-between gap-3">
              <div className="flex items-start gap-2.5">
                <PinIcon />
                <span className="text-sm text-ink">{restaurant.address}</span>
              </div>
              <button
                type="button"
                onClick={handleCopyAddress}
                className="flex shrink-0 items-center gap-1 rounded-md px-1.5 py-0.5 text-xs text-ink-muted transition hover:text-ink"
              >
                <CopyIcon />
                {copied ? "복사됨" : "복사"}
              </button>
            </div>
          )}

          {restaurant.phone && (
            <a
              href={`tel:${restaurant.phone}`}
              className="flex items-center gap-2.5 text-sm text-ink transition hover:text-accent"
            >
              <PhoneIcon />
              {restaurant.phone}
            </a>
          )}

          {restaurant.hours && (
            <div className="flex items-center gap-2.5 text-sm text-ink">
              <ClockIcon />
              {restaurant.hours}
            </div>
          )}
        </div>
      </div>

      <a
        href={kakaoMapUrl}
        target="_blank"
        rel="noopener noreferrer"
        className="mt-3 flex w-full shrink-0 items-center justify-center gap-2 rounded-xl bg-accent px-6 py-3 text-[15px] font-semibold text-white transition hover:bg-accent-hover"
      >
        카카오맵에서 길찾기
      </a>
    </div>
  );
}
