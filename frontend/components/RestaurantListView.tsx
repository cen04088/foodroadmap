"use client";

import { useState } from "react";
import { BROADCASTS } from "./FilterBar";
import RestaurantCard from "./RestaurantCard";
import RestaurantDetail from "./RestaurantDetail";
import type { RestaurantSummary } from "../lib/api";

export interface RestaurantListViewProps {
  restaurants: RestaurantSummary[];
  broadcastFilter: string;
  onBroadcastFilterChange: (broadcast: string) => void;
  onClose: () => void;
}

function CloseIcon() {
  return (
    <svg viewBox="0 0 20 20" fill="none" className="h-5 w-5" aria-hidden="true">
      <path d="M5 5l10 10M15 5L5 15" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
    </svg>
  );
}

export default function RestaurantListView({
  restaurants,
  broadcastFilter,
  onBroadcastFilterChange,
  onClose,
}: RestaurantListViewProps) {
  const [detailId, setDetailId] = useState<string | null>(null);
  const detailRestaurant = detailId ? restaurants.find((r) => r.id === detailId) ?? null : null;

  return (
    <div className="fixed inset-0 z-40 flex flex-col bg-paper text-ink">
      <header className="flex shrink-0 items-center justify-between gap-3 border-b border-line px-5 py-4">
        <h1 className="text-lg font-bold">맛집 목록</h1>
        <div className="flex items-center gap-3">
          <div className="relative">
            <select
              value={broadcastFilter}
              onChange={(e) => onBroadcastFilterChange(e.target.value)}
              className="w-[150px] appearance-none rounded-lg border border-line bg-surface py-1.5 pl-3 pr-7 text-sm font-medium text-ink outline-none"
            >
              {BROADCASTS.map((b) => (
                <option key={b.value} value={b.value} style={{ backgroundColor: "var(--surface)", color: "var(--ink)" }}>
                  {b.label}
                </option>
              ))}
            </select>
            <svg
              viewBox="0 0 20 20"
              fill="none"
              className="pointer-events-none absolute right-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-ink-muted"
              aria-hidden="true"
            >
              <path d="M5 7.5L10 12.5L15 7.5" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label="목록 닫기"
            className="grid h-9 w-9 place-items-center rounded-full text-ink-muted transition hover:bg-surface-hover hover:text-ink"
          >
            <CloseIcon />
          </button>
        </div>
      </header>

      <div className="flex-1 overflow-y-auto p-4 sm:p-6">
        {detailRestaurant ? (
          <div className="mx-auto max-w-[560px]">
            <RestaurantDetail restaurant={detailRestaurant} onBack={() => setDetailId(null)} />
          </div>
        ) : restaurants.length === 0 ? (
          <div className="flex h-full min-h-[200px] items-center justify-center rounded-2xl border border-dashed border-line px-4 text-center text-sm text-ink-muted">
            조건에 맞는 맛집이 없어요
          </div>
        ) : (
          <div className="mx-auto grid max-w-[1200px] grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {restaurants.map((restaurant) => (
              <RestaurantCard
                key={restaurant.id}
                restaurant={restaurant}
                isSelected={false}
                onSelect={() => setDetailId(restaurant.id)}
                onShowDetail={() => setDetailId(restaurant.id)}
              />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
