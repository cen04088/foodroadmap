"use client";

import { useEffect, useState } from "react";
import RestaurantCard from "./RestaurantCard";
import RestaurantDetail from "./RestaurantDetail";
import { fetchBroadcasts, type BroadcastSummary, type RestaurantSummary } from "../lib/api";
import { getBroadcastColor } from "../lib/broadcastColors";
import { getBroadcastImage } from "../lib/broadcastImages";

export interface RestaurantListViewProps {
  restaurants: RestaurantSummary[];
  broadcastFilter: string;
  onBroadcastFilterChange: (broadcast: string) => void;
  onClose: () => void;
  topOffset: number;
}

function CloseIcon() {
  return (
    <svg viewBox="0 0 20 20" fill="none" className="h-5 w-5" aria-hidden="true">
      <path d="M5 5l10 10M15 5L5 15" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
    </svg>
  );
}

function BackIcon() {
  return (
    <svg viewBox="0 0 20 20" fill="none" className="h-4 w-4" aria-hidden="true">
      <path d="M12.5 4.5L6.5 10l6 5.5" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

export default function RestaurantListView({
  restaurants,
  broadcastFilter,
  onBroadcastFilterChange,
  onClose,
  topOffset,
}: RestaurantListViewProps) {
  const [screen, setScreen] = useState<"broadcasts" | "restaurants">(broadcastFilter ? "restaurants" : "broadcasts");
  const [broadcasts, setBroadcasts] = useState<BroadcastSummary[] | null>(null);
  const [categoryFilter, setCategoryFilter] = useState("");
  const [detailId, setDetailId] = useState<string | null>(null);

  useEffect(() => {
    fetchBroadcasts()
      .then(setBroadcasts)
      .catch(() => setBroadcasts([]));
  }, []);

  function handleSelectBroadcast(name: string) {
    onBroadcastFilterChange(name);
    setCategoryFilter("");
    setScreen("restaurants");
  }

  function handleBackToBroadcasts() {
    setDetailId(null);
    setCategoryFilter("");
    setScreen("broadcasts");
    onBroadcastFilterChange("");
  }

  const categories = Array.from(
    new Set(restaurants.map((r) => r.category).filter((c): c is string => Boolean(c)))
  ).sort();
  const filteredRestaurants = categoryFilter ? restaurants.filter((r) => r.category === categoryFilter) : restaurants;
  const detailRestaurant = detailId ? filteredRestaurants.find((r) => r.id === detailId) ?? null : null;

  return (
    <div
      className="fixed inset-x-0 bottom-0 z-40 flex flex-col rounded-t-2xl border-t border-line bg-paper text-ink shadow-[0_-12px_32px_rgba(0,0,0,0.45)]"
      style={{ top: topOffset }}
    >
      <header className="flex shrink-0 items-center justify-between gap-3 border-b border-line px-5 py-4">
        {screen === "broadcasts" ? (
          <h1 className="text-lg font-bold">맛집 목록</h1>
        ) : (
          <button
            type="button"
            onClick={handleBackToBroadcasts}
            className="flex items-center gap-1.5 text-lg font-bold text-ink transition hover:text-accent"
          >
            <BackIcon />
            {broadcastFilter}
          </button>
        )}
        <button
          type="button"
          onClick={onClose}
          aria-label="목록 닫기"
          className="grid h-9 w-9 place-items-center rounded-full text-ink-muted transition hover:bg-surface-hover hover:text-ink"
        >
          <CloseIcon />
        </button>
      </header>

      {screen === "restaurants" && !detailRestaurant && categories.length > 0 && (
        <div className="flex shrink-0 flex-wrap gap-2 px-5 pt-4 sm:px-6">
          {["", ...categories].map((cat) => (
            <button
              key={cat || "all"}
              type="button"
              onClick={() => setCategoryFilter(cat)}
              className={`rounded-full px-3 py-1.5 text-xs font-medium transition ${
                categoryFilter === cat
                  ? "bg-accent text-[#171310]"
                  : "bg-surface text-ink-muted hover:bg-surface-hover"
              }`}
            >
              {cat || "전체"}
            </button>
          ))}
        </div>
      )}

      <div className="flex-1 overflow-y-auto p-4 sm:p-6">
        {screen === "broadcasts" ? (
          !broadcasts ? (
            <p className="text-sm text-ink-muted">불러오는 중...</p>
          ) : (
            <div className="mx-auto grid max-w-[1200px] grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-4">
              {broadcasts.map((b) => {
                const { color, letter } = getBroadcastColor(b.name);
                const image = getBroadcastImage(b.name);
                return (
                  <button
                    key={b.slug}
                    type="button"
                    onClick={() => handleSelectBroadcast(b.name)}
                    className="overflow-hidden rounded-2xl border border-line bg-surface text-left transition hover:border-accent/40 hover:shadow-md hover:shadow-black/20"
                  >
                    {image ? (
                      // eslint-disable-next-line @next/next/no-img-element
                      <img src={image} alt={b.name} className="aspect-video w-full object-cover" />
                    ) : (
                      <div className="flex aspect-video w-full items-center justify-center text-2xl font-black text-white" style={{ backgroundColor: color }}>
                        {letter}
                      </div>
                    )}
                    <div className="p-4">
                      <div className="truncate font-medium text-ink">{b.name}</div>
                      <div className="text-sm text-ink-muted">{b.count}곳</div>
                    </div>
                  </button>
                );
              })}
            </div>
          )
        ) : detailRestaurant ? (
          <div className="mx-auto max-w-[560px]">
            <RestaurantDetail restaurant={detailRestaurant} onBack={() => setDetailId(null)} />
          </div>
        ) : filteredRestaurants.length === 0 ? (
          <div className="flex h-full min-h-[200px] items-center justify-center rounded-2xl border border-dashed border-line px-4 text-center text-sm text-ink-muted">
            조건에 맞는 맛집이 없어요
          </div>
        ) : (
          <div className="mx-auto grid max-w-[1200px] grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {filteredRestaurants.map((restaurant) => (
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
