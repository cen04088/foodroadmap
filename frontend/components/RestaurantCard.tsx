"use client";

import { formatDepartureOffset, formatDistance } from "../lib/format";
import type { RestaurantSummary } from "../lib/api";
import { getBroadcastColor } from "../lib/broadcastColors";
import { getRestaurantThumbnailUrl } from "../lib/thumbnail";
import { useFavorites } from "../lib/favorites";

function BookmarkIcon({ filled, className }: { filled: boolean; className?: string }) {
  return (
    <svg viewBox="0 0 20 20" fill={filled ? "currentColor" : "none"} className={className} aria-hidden="true">
      <path
        d="M5 3.5h10a1 1 0 0 1 1 1v12l-6-3.5-6 3.5v-12a1 1 0 0 1 1-1z"
        stroke="currentColor"
        strokeWidth="1.6"
        strokeLinejoin="round"
      />
    </svg>
  );
}

export interface RestaurantCardProps {
  restaurant: RestaurantSummary & { distance_from_route_km?: number; cumulative_time_sec?: number };
  order?: number;
  isSelected: boolean;
  // 필터에 안 맞는 카드를 목록에서 지우지 않고 흑백+반투명으로 죽여서, 경로 전체 맥락은
  // 유지하면서 조건에 맞는 것만 도드라져 보이게 한다.
  isDimmed?: boolean;
  // AI 식사 플래너가 고른 식당 — 이름 옆에 "AI 추천" 배지를 붙인다.
  isAiPick?: boolean;
  onSelect: (id: string) => void;
  onShowDetail: (id: string) => void;
}

export default function RestaurantCard({
  restaurant,
  order,
  isSelected,
  isDimmed = false,
  isAiPick = false,
  onSelect,
  onShowDetail,
}: RestaurantCardProps) {
  const metaLine = [restaurant.address, restaurant.phone, restaurant.hours].filter(Boolean).join(" · ");
  const hasRouteInfo = restaurant.distance_from_route_km !== undefined && restaurant.cumulative_time_sec !== undefined;
  const thumbnailUrl = getRestaurantThumbnailUrl(restaurant);
  const primaryBroadcast = restaurant.broadcasts[0] ?? null;
  const { color: programColor, letter: programLetter } = getBroadcastColor(primaryBroadcast ?? "");
  const { favorites, toggle } = useFavorites();
  const isSaved = favorites.some((f) => f.id === restaurant.id);

  return (
    <div
      onClick={() => onSelect(restaurant.id)}
      className={`cursor-pointer rounded-xl border p-4 transition ${
        isSelected
          ? "border-accent bg-accent-soft shadow-md shadow-accent/10"
          : "border-line bg-surface hover:border-accent/40 hover:shadow-md hover:shadow-black/5"
      } ${isDimmed ? "grayscale opacity-50" : ""}`}
    >
      <div className="flex gap-3">
        {thumbnailUrl ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img
            src={thumbnailUrl}
            alt={primaryBroadcast ?? ""}
            loading="lazy"
            className="h-16 w-16 shrink-0 rounded-lg object-cover"
          />
        ) : primaryBroadcast ? (
          <div
            className="grid h-16 w-16 shrink-0 place-items-center rounded-lg text-xl font-black text-white"
            style={{ backgroundColor: programColor }}
          >
            {programLetter}
          </div>
        ) : null}

        <div className="min-w-0 flex-1">
          <div className="flex items-start gap-3">
            {order && <span className="grid h-7 w-7 shrink-0 place-items-center rounded-full bg-accent text-xs font-black text-[#171310]">{order}</span>}
            <span className="flex-1 text-[15px] font-semibold leading-snug text-ink">{restaurant.name}</span>
            {isAiPick && (
              <span className="shrink-0 rounded-full bg-accent px-2 py-0.5 text-[11px] font-bold text-[#171310]">AI 추천</span>
            )}
            {restaurant.category && (
              <span className="shrink-0 rounded-full bg-surface-hover px-2.5 py-0.5 text-xs font-medium text-ink-muted">
                {restaurant.category}
              </span>
            )}
            <button
              type="button"
              // 카드 전체가 클릭 가능해서, 저장 버튼이 카드 선택까지 같이 트리거하면 안 된다.
              onClick={(e) => {
                e.stopPropagation();
                toggle(restaurant);
              }}
              aria-pressed={isSaved}
              aria-label={isSaved ? `${restaurant.name} 저장 취소` : `${restaurant.name} 저장`}
              className={`-mr-1 -mt-1 shrink-0 rounded-full p-1 transition ${
                isSaved ? "text-accent" : "text-ink-muted hover:text-ink"
              }`}
            >
              <BookmarkIcon filled={isSaved} className="h-4 w-4" />
            </button>
          </div>

          {hasRouteInfo && (
            <div className="mt-2 text-sm font-semibold text-accent-soft-ink">
              {formatDepartureOffset(restaurant.cumulative_time_sec!)}
              <span className="mx-1.5 font-normal text-line">·</span>
              <span className="font-normal text-ink-muted">경로에서 {formatDistance(restaurant.distance_from_route_km!)}</span>
            </div>
          )}

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

          {metaLine && <div className="mt-2 text-xs text-ink-muted">{metaLine}</div>}

          <button
            type="button"
            onClick={(e) => {
              e.stopPropagation();
              onShowDetail(restaurant.id);
            }}
            className="mt-2.5 text-xs font-medium text-accent transition hover:text-accent-hover"
          >
            자세히 보기
          </button>
        </div>
      </div>
    </div>
  );
}
