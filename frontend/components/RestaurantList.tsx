"use client";

import RestaurantCard from "./RestaurantCard";
import type { RestaurantResult } from "../lib/api";

export interface RestaurantListProps {
  restaurants: RestaurantResult[];
  hoveredId: string | null;
  onHover: (id: string | null) => void;
}

export default function RestaurantList({ restaurants, hoveredId, onHover }: RestaurantListProps) {
  if (restaurants.length === 0) {
    return <p className="p-4 text-center text-gray-500">이 경로 근처엔 방송 맛집이 없어요</p>;
  }

  return (
    <div className="flex flex-col gap-2 overflow-y-auto">
      {restaurants.map((restaurant) => (
        <RestaurantCard
          key={restaurant.id}
          restaurant={restaurant}
          isHovered={hoveredId === restaurant.id}
          onHover={onHover}
        />
      ))}
    </div>
  );
}
