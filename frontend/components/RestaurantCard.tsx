"use client";

import { formatDistance, formatDuration } from "../lib/format";
import type { RestaurantResult } from "../lib/api";

export interface RestaurantCardProps {
  restaurant: RestaurantResult;
  isHovered: boolean;
  onHover: (id: string | null) => void;
  onSelect: (id: string) => void;
}

export default function RestaurantCard({ restaurant, isHovered, onHover, onSelect }: RestaurantCardProps) {
  return (
    <div
      onMouseEnter={() => onHover(restaurant.id)}
      onMouseLeave={() => onHover(null)}
      onClick={() => onSelect(restaurant.id)}
      className={`rounded border p-3 ${isHovered ? "border-blue-500 bg-blue-50" : "border-gray-200"}`}
    >
      <div className="flex items-baseline justify-between">
        <span className="font-medium">{restaurant.name}</span>
        <span className="text-sm text-gray-500">{restaurant.category}</span>
      </div>
      <div className="mt-1 text-sm text-gray-600">
        {formatDistance(restaurant.distance_from_route_km)} · 출발 후 {formatDuration(restaurant.cumulative_time_sec)}
      </div>
      {restaurant.broadcasts.length > 0 && (
        <div className="mt-1 text-xs text-gray-500">{restaurant.broadcasts.join(", ")}</div>
      )}
      <div className="mt-1 text-xs text-gray-500">
        {restaurant.address}
        {restaurant.phone && ` · ${restaurant.phone}`}
        {restaurant.hours && ` · ${restaurant.hours}`}
      </div>
    </div>
  );
}
