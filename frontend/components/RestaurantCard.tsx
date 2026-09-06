"use client";

import { formatDistance, formatDuration } from "../lib/format";
import type { RestaurantSummary } from "../lib/api";
import { getBroadcastColor } from "../lib/broadcastColors";
import { getRestaurantThumbnailUrl } from "../lib/thumbnail";

export interface RestaurantCardProps {
  restaurant: RestaurantSummary & { distance_from_route_km?: number; cumulative_time_sec?: number };
  order?: number;
  isSelected: boolean;
  // 필터에 안 맞는 카드를 목록에서 지우지 않고 흑백+반투명으로 죽여서, 경로 전체 맥락은
  // 유지하면서 조건에 맞는 것만 도드라져 보이게 한다.
  isDimmed?: boolean;
  onSelect: (id: string) => void;
  onShowDetail: (id: string) => void;
}

export default function RestaurantCard({
  restaurant,
  order,
  isSelected,
  isDimmed = false,
  onSelect,
  onShowDetail,
}: RestaurantCardProps) {
  const metaLine = [restaurant.address, restaurant.phone, restaurant.hours].filter(Boolean).join(" · ");
  const hasRouteInfo = restaurant.distance_from_route_km !== undefined && restaurant.cumulative_time_sec !== undefined;
  const thumbnailUrl = getRestaurantThumbnailUrl(restaurant);
  const primaryBroadcast = restaurant.broadcasts[0] ?? null;
  const { color: programColor, letter: programLetter } = getBroadcastColor(primaryBroadcast ?? "");

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
            {restaurant.category && (
              <span className="shrink-0 rounded-full bg-surface-hover px-2.5 py-0.5 text-xs font-medium text-ink-muted">
                {restaurant.category}
              </span>
            )}
          </div>

          {hasRouteInfo && (
            <div className="mt-2 text-sm font-semibold text-accent-soft-ink">
              🚗 출발 후 {formatDuration(restaurant.cumulative_time_sec!)}
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
