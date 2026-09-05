"use client";

import { useEffect, useRef } from "react";
import RestaurantCard from "./RestaurantCard";
import type { RestaurantResult } from "../lib/api";

export interface RestaurantListProps {
  restaurants: RestaurantResult[];
  selectedId: string | null;
  onSelect: (id: string) => void;
  onShowDetail: (id: string) => void;
  scrollToId?: string | null;
}

export default function RestaurantList({
  restaurants,
  selectedId,
  onSelect,
  onShowDetail,
  scrollToId,
}: RestaurantListProps) {
  const itemRefs = useRef<Map<string, HTMLDivElement>>(new Map());

  useEffect(() => {
    if (!scrollToId) return;
    itemRefs.current.get(scrollToId)?.scrollIntoView({ behavior: "smooth", block: "nearest" });
  }, [scrollToId]);

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
        <div
          key={restaurant.id}
          ref={(el) => {
            if (el) itemRefs.current.set(restaurant.id, el);
            else itemRefs.current.delete(restaurant.id);
          }}
        >
          <RestaurantCard
            restaurant={restaurant}
            isSelected={selectedId === restaurant.id}
            onSelect={onSelect}
            onShowDetail={onShowDetail}
          />
        </div>
      ))}
    </div>
  );
}
