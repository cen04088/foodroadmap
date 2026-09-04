"use client";

import { formatDistance, formatDuration } from "../lib/format";
import type { RestaurantResult } from "../lib/api";
import { getBroadcastColor } from "../lib/broadcastColors";

export interface RestaurantCardProps {
  restaurant: RestaurantResult;
  isHovered: boolean;
  onHover: (id: string | null) => void;
  onSelect: (id: string) => void;
}

export default function RestaurantCard({ restaurant, isHovered, onHover, onSelect }: RestaurantCardProps) {
  const metaLine = [restaurant.address, restaurant.phone, restaurant.hours].filter(Boolean).join(" · ");

  return (
    <div
      onMouseEnter={() => onHover(restaurant.id)}
      onMouseLeave={() => onHover(null)}
      onClick={() => onSelect(restaurant.id)}
      className={`cursor-pointer rounded-xl border p-4 transition ${
        isHovered
          ? "border-accent bg-accent-soft shadow-md shadow-accent/10"
          : "border-line bg-surface hover:border-accent/40 hover:shadow-md hover:shadow-black/5"
      }`}
    >
      <div className="flex items-start justify-between gap-3">
        <span className="text-[15px] font-semibold leading-snug text-ink">{restaurant.name}</span>
        {restaurant.category && (
          <span className="shrink-0 rounded-full bg-surface-hover px-2.5 py-0.5 text-xs font-medium text-ink-muted">
            {restaurant.category}
          </span>
        )}
      </div>

      <div className="mt-1.5 text-sm text-ink-muted">
        {formatDistance(restaurant.distance_from_route_km)}
        <span className="mx-1.5 text-line">·</span>
        출발 후 {formatDuration(restaurant.cumulative_time_sec)}
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

      {metaLine && <div className="mt-2 text-xs text-ink-muted">{metaLine}</div>}
    </div>
  );
}
