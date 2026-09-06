"use client";

import { useEffect, useRef } from "react";
import RestaurantCard from "./RestaurantCard";
import type { RestaurantResult } from "../lib/api";
import { matchesFilters, type RestaurantFilterCriteria } from "../lib/restaurantFilter";

export interface RestaurantListProps {
  restaurants: RestaurantResult[];
  selectedId: string | null;
  // 지정하면 필터에 안 맞는 카드를 지우지 않고 흑백+반투명으로 죽인다 (재검색 없이).
  activeFilters?: RestaurantFilterCriteria;
  onSelect: (id: string) => void;
  onShowDetail: (id: string) => void;
  scrollToId?: string | null;
}

export default function RestaurantList({
  restaurants,
  selectedId,
  activeFilters,
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
      {restaurants.map((restaurant, index) => (
        <div
          key={restaurant.id}
          ref={(el) => {
            if (el) itemRefs.current.set(restaurant.id, el);
            else itemRefs.current.delete(restaurant.id);
          }}
        >
          <RestaurantCard
            restaurant={restaurant}
            order={index + 1}
            isSelected={selectedId === restaurant.id}
            isDimmed={activeFilters ? !matchesFilters(restaurant, activeFilters) : false}
            onSelect={onSelect}
            onShowDetail={onShowDetail}
          />
        </div>
      ))}
    </div>
  );
}
