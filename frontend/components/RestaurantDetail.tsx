"use client";

import { useState } from "react";
import { formatDistance, formatDuration } from "../lib/format";
import type { RestaurantSummary } from "../lib/api";
import { getBroadcastColor } from "../lib/broadcastColors";
import { getBroadcastImage } from "../lib/broadcastImages";
import { getYoutubeVideoId } from "../lib/youtube";
import YoutubeModal from "./YoutubeModal";

export interface RestaurantDetailProps {
  restaurant: RestaurantSummary & { distance_from_route_km?: number; cumulative_time_sec?: number };
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

function YoutubeIcon() {
  return (
    <svg viewBox="0 0 20 20" fill="none" className="h-4 w-4 shrink-0" aria-hidden="true">
      <rect x="2.5" y="5" width="15" height="10" rx="3" stroke="currentColor" strokeWidth="1.4" />
      <path d="M8.5 8v4l3.5-2-3.5-2Z" fill="currentColor" />
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
  const [showVideo, setShowVideo] = useState(false);
  const videoId = restaurant.youtube_url ? getYoutubeVideoId(restaurant.youtube_url) : null;
  const primaryBroadcast = restaurant.broadcasts[0] ?? null;
  const { color: programColor, letter: programLetter } = getBroadcastColor(primaryBroadcast ?? "");
  const programImage = primaryBroadcast ? getBroadcastImage(primaryBroadcast) : null;

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
        {videoId ? (
          <button
            type="button"
            onClick={() => setShowVideo(true)}
            className="group relative mb-4 block aspect-video w-full overflow-hidden rounded-xl bg-[#171310] text-left"
          >
            <span
              role="img"
              aria-label={`${restaurant.name} 방송 영상`}
              className="block h-full w-full bg-cover bg-center opacity-70 transition duration-300 group-hover:scale-105 group-hover:opacity-50"
              style={{ backgroundImage: `url(https://i.ytimg.com/vi/${videoId}/hqdefault.jpg)` }}
            />
            <span className="absolute inset-0 grid place-items-center"><span className="rounded-full bg-[#ff7a1a] px-4 py-2 text-sm font-bold text-[#171310] shadow-lg">▶ 방송 영상 보기</span></span>
          </button>
        ) : programImage ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img
            src={programImage}
            alt={primaryBroadcast ?? ""}
            className="mb-4 block aspect-video w-full rounded-xl object-cover"
          />
        ) : primaryBroadcast ? (
          <div
            className="relative mb-4 flex aspect-video w-full items-center justify-center overflow-hidden rounded-xl"
            style={{ backgroundColor: programColor }}
          >
            <span
              aria-hidden="true"
              className="absolute -right-4 -top-6 select-none text-[8rem] font-black leading-none text-white/15"
            >
              {programLetter}
            </span>
            <div className="relative flex flex-col items-center gap-2 px-4 text-center">
              <span className="grid h-12 w-12 place-items-center rounded-full bg-white/20 text-xl font-black text-white">
                {programLetter}
              </span>
              <span className="text-base font-bold text-white">{primaryBroadcast}</span>
            </div>
          </div>
        ) : null}
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

        {restaurant.distance_from_route_km !== undefined && restaurant.cumulative_time_sec !== undefined && (
          <div className="mt-4 rounded-xl bg-accent-soft px-4 py-3 text-sm text-ink">
            <span className="font-bold text-accent-soft-ink">🚗 출발 후 {formatDuration(restaurant.cumulative_time_sec)}</span>
            <span className="text-ink-muted"> · 경로에서 {formatDistance(restaurant.distance_from_route_km)}</span>
          </div>
        )}

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

          {videoId && (
            <button
              type="button"
              onClick={() => setShowVideo(true)}
              className="flex w-fit items-center gap-2 rounded-lg border border-line px-3 py-1.5 text-sm font-medium text-ink transition hover:border-accent/40 hover:text-accent"
            >
              <YoutubeIcon />
              유튜브 보기
            </button>
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
        className="mt-3 flex w-full shrink-0 items-center justify-center gap-2 rounded-xl bg-accent px-6 py-3 text-[15px] font-semibold text-white shadow-[0_8px_28px_-6px_var(--accent-glow)] transition hover:bg-accent-hover"
      >
        카카오맵에서 길찾기
      </a>

      {showVideo && videoId && (
        <YoutubeModal videoId={videoId} title={restaurant.name} onClose={() => setShowVideo(false)} />
      )}
    </div>
  );
}
