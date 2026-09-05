"use client";

import RestaurantCard from "./RestaurantCard";
import type { RestaurantResult } from "../lib/api";

export interface RestaurantListProps {
  restaurants: RestaurantResult[];
  hoveredId: string | null;
  onHover: (id: string | null) => void;
  onSelect: (id: string) => void;
  onShowDetail: (id: string) => void;
}

export default function RestaurantList({ restaurants, hoveredId, onHover, onSelect, onShowDetail }: RestaurantListProps) {
  if (restaurants.length === 0) {
    return (
      <div className="flex h-full min-h-[200px] items-center justify-center rounded-2xl border border-dashed border-line px-4 text-center text-sm text-ink-muted">
        이 경로 근처엔 방송 맛집이 없어요
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-3 overflow-y-auto">
      {restaurants.map((restaurant) => (
        <RestaurantCard
          key={restaurant.id}
          restaurant={restaurant}
          isHovered={hoveredId === restaurant.id}
          onHover={onHover}
          onSelect={onSelect}
          onShowDetail={onShowDetail}
        />
      ))}
    </div>
  );
}
