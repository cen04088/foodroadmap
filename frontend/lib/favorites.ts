"use client";

import { useCallback, useEffect, useState } from "react";
import type { RestaurantSummary } from "./api";

const STORAGE_KEY = "foodroadmap:favorites:v1";
// 같은 탭 안의 다른 컴포넌트에도 변경을 알리기 위한 이벤트 — 브라우저의 storage
// 이벤트는 "다른 탭"에서만 발생해서 자기 탭에서는 안 잡힌다.
const CHANGE_EVENT = "foodroadmap:favorites-changed";

// 좌표와 이름만 들고 있으면 저장 목록을 그리고 지도로 보낼 수 있다. id로 매번 다시
// 받아오지 않는 이유는 단건 조회 API가 없기 때문 — 목록 렌더에 필요한 최소한만 남긴다.
export interface FavoritePlace {
  id: string;
  name: string;
  category: string | null;
  address: string | null;
  latitude: number;
  longitude: number;
  savedAt: number;
}

export function toFavorite(restaurant: RestaurantSummary): FavoritePlace {
  return {
    id: restaurant.id,
    name: restaurant.name,
    category: restaurant.category,
    address: restaurant.address,
    latitude: restaurant.latitude,
    longitude: restaurant.longitude,
    savedAt: Date.now(),
  };
}

function isFavoritePlace(value: unknown): value is FavoritePlace {
  if (typeof value !== "object" || value === null) return false;
  const candidate = value as Record<string, unknown>;
  return (
    typeof candidate.id === "string" &&
    typeof candidate.name === "string" &&
    typeof candidate.latitude === "number" &&
    typeof candidate.longitude === "number"
  );
}

export function readFavorites(): FavoritePlace[] {
  // 시크릿 모드나 사이트 데이터 차단 설정에서는 접근 자체가 예외를 던진다.
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (!raw) return [];
    const parsed: unknown = JSON.parse(raw);
    if (!Array.isArray(parsed)) return [];
    // 이전 버전이 남긴 값이나 손상된 항목이 섞여 있어도 목록 전체를 버리지 않는다.
    return parsed.filter(isFavoritePlace);
  } catch {
    return [];
  }
}

function writeFavorites(favorites: FavoritePlace[]): void {
  try {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(favorites));
  } catch {
    // 용량 초과나 저장 차단 — 저장에 실패해도 화면은 계속 동작해야 한다.
  }
  window.dispatchEvent(new Event(CHANGE_EVENT));
}

export function isFavorite(id: string): boolean {
  return readFavorites().some((f) => f.id === id);
}

export function toggleFavorite(restaurant: RestaurantSummary): boolean {
  const current = readFavorites();
  const wasSaved = current.some((f) => f.id === restaurant.id);
  writeFavorites(
    wasSaved
      ? current.filter((f) => f.id !== restaurant.id)
      : [toFavorite(restaurant), ...current]
  );
  return !wasSaved;
}

export function useFavorites() {
  // 서버 렌더에는 localStorage가 없다. 빈 배열로 시작해 마운트 후 읽어야
  // 하이드레이션 불일치가 나지 않는다.
  const [favorites, setFavorites] = useState<FavoritePlace[]>([]);

  useEffect(() => {
    const sync = () => setFavorites(readFavorites());
    sync();
    window.addEventListener(CHANGE_EVENT, sync);
    window.addEventListener("storage", sync);
    return () => {
      window.removeEventListener(CHANGE_EVENT, sync);
      window.removeEventListener("storage", sync);
    };
  }, []);

  const toggle = useCallback((restaurant: RestaurantSummary) => {
    toggleFavorite(restaurant);
  }, []);

  const remove = useCallback((id: string) => {
    writeFavorites(readFavorites().filter((f) => f.id !== id));
  }, []);

  const clear = useCallback(() => writeFavorites([]), []);

  return { favorites, toggle, remove, clear };
}
