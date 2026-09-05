"use client";

import { Suspense, useRef, useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import SearchForm, { type SelectedPlace } from "../components/SearchForm";
import FilterBar, { type Filters } from "../components/FilterBar";
import MapView from "../components/MapView";
import RestaurantList from "../components/RestaurantList";
import RestaurantDetail from "../components/RestaurantDetail";
import { ApiError, fetchRouteRestaurants, type RouteRestaurantsResponse } from "../lib/api";

function errorMessageFor(error: unknown): string {
  if (error instanceof ApiError) {
    if (error.status === 0) return "서버에 연결할 수 없습니다";
    if (error.status === 500) return "일시적인 오류입니다, 잠시 후 다시 시도해주세요";
    if (error.status === 502) return "경로를 가져오지 못했습니다, 다시 시도해주세요";
    if (error.status === 422) return "선택한 위치 근처에서 자동차 경로를 찾을 수 없어요, 다른 장소를 선택해보세요";
    return "요청 중 오류가 발생했습니다";
  }
  return "알 수 없는 오류가 발생했습니다";
}

function HomeContent() {
  const searchParams = useSearchParams();
  const [origin, setOrigin] = useState<SelectedPlace | null>(null);
  const [destination, setDestination] = useState<SelectedPlace | null>(null);
  const [filters, setFilters] = useState<Filters>(() => ({
    broadcast: searchParams.get("broadcast") ?? "",
    category: "",
  }));
  const [result, setResult] = useState<RouteRestaurantsResponse | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [hoveredId, setHoveredId] = useState<string | null>(null);
  const [detailId, setDetailId] = useState<string | null>(null);
  const [listScrollTarget, setListScrollTarget] = useState<string | null>(null);
  const [mapCenter, setMapCenter] = useState<{ lat: number; lng: number } | null>(null);
  const searchSeqRef = useRef(0);
  const filterDebounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const mapContainerRef = useRef<HTMLDivElement>(null);

  async function runSearch(
    searchOrigin: SelectedPlace,
    searchDestination: SelectedPlace,
    searchFilters: Filters
  ) {
    const seq = ++searchSeqRef.current;
    setIsLoading(true);
    setErrorMessage(null);
    setDetailId(null);
    try {
      const response = await fetchRouteRestaurants({
        originLat: searchOrigin.lat,
        originLng: searchOrigin.lng,
        destinationLat: searchDestination.lat,
        destinationLng: searchDestination.lng,
        broadcast: searchFilters.broadcast || undefined,
        category: searchFilters.category || undefined,
      });
      if (seq !== searchSeqRef.current) return;
      setResult(response);
    } catch (error) {
      if (seq !== searchSeqRef.current) return;
      setErrorMessage(errorMessageFor(error));
    } finally {
      if (seq !== searchSeqRef.current) return;
      setIsLoading(false);
    }
  }

  function handleSearch(searchOrigin: SelectedPlace, searchDestination: SelectedPlace) {
    setOrigin(searchOrigin);
    setDestination(searchDestination);
    if (filterDebounceRef.current) {
      clearTimeout(filterDebounceRef.current);
      filterDebounceRef.current = null;
    }
    runSearch(searchOrigin, searchDestination, filters);
  }

  function handleFiltersChange(newFilters: Filters) {
    setFilters(newFilters);

    if (filterDebounceRef.current) {
      clearTimeout(filterDebounceRef.current);
    }

    if (origin && destination) {
      filterDebounceRef.current = setTimeout(() => {
        runSearch(origin, destination, newFilters);
      }, 400);
    }
  }

  function handleOriginSelect(place: SelectedPlace) {
    setMapCenter({ lat: place.lat, lng: place.lng });
  }

  function handleSelectRestaurant(id: string) {
    setHoveredId(id);
  }

  function handleShowDetail(id: string) {
    setDetailId(id);
    setHoveredId(id);
  }

  function handleMarkerClick(id: string) {
    setDetailId(null);
    setHoveredId(id);
    setListScrollTarget(id);
  }

  const detailRestaurant = detailId ? result?.restaurants.find((r) => r.id === detailId) ?? null : null;

  return (
    <main className="relative flex w-full flex-col sm:h-screen">
      {/* 지도 — 데스크톱에서는 화면 전체를 채우는 배경, 모바일에서는 지금처럼 목록 위에 고정 높이로 위치 */}
      <div ref={mapContainerRef} className="order-3 min-h-0 p-4 pb-0 sm:absolute sm:inset-0 sm:p-0">
        <MapView
          route={result?.route.points ?? []}
          restaurants={result?.restaurants ?? []}
          highlightedRestaurantId={hoveredId}
          center={mapCenter}
          activeBroadcast={filters.broadcast || null}
          onMarkerClick={handleMarkerClick}
        />
      </div>

      {/* 검색+필터+목록 — 모바일에서는 지금처럼 세로로 쌓이고(display: contents로 위 지도 사이에 끼워짐),
          데스크톱에서는 지도 위에 뜨는 좌측 사이드바 하나로 묶인다. */}
      <div className="contents sm:pointer-events-none sm:absolute sm:inset-y-6 sm:left-6 sm:z-10 sm:flex sm:w-[400px] sm:flex-col sm:gap-4">
        <div className="order-1 shrink-0 p-4 pb-0 sm:pointer-events-auto sm:p-0">
          <div className="rounded-2xl border border-line bg-surface p-4 shadow-sm shadow-black/5 sm:shadow-lg sm:shadow-black/10">
            <div className="mb-4 flex items-center justify-between">
              <h1 className="text-lg font-semibold text-ink">경로 맛집</h1>
              <Link href="/broadcasts" className="text-sm text-ink-muted transition hover:text-ink">
                방송·유튜브별로 보기
              </Link>
            </div>
            <SearchForm onOriginSelect={handleOriginSelect} onSearch={handleSearch} isLoading={isLoading} />
            <div className="my-4 border-t border-line" />
            <FilterBar filters={filters} onChange={handleFiltersChange} />
          </div>
        </div>

        {errorMessage && (
          <div className="order-2 shrink-0 px-4 sm:pointer-events-auto sm:px-0">
            <div className="rounded-xl border border-danger/20 bg-danger-soft px-4 py-3 text-sm text-danger-ink">
              {errorMessage}
            </div>
          </div>
        )}

        <div className="order-4 p-4 pt-0 sm:min-h-0 sm:flex-1 sm:overflow-hidden sm:p-0 sm:pointer-events-auto">
          <div className="sm:h-full sm:overflow-y-auto sm:rounded-2xl sm:border sm:border-line sm:bg-surface sm:p-3 sm:shadow-lg sm:shadow-black/10">
            {detailRestaurant ? (
              <RestaurantDetail restaurant={detailRestaurant} onBack={() => setDetailId(null)} />
            ) : result ? (
              <RestaurantList
                restaurants={result.restaurants}
                hoveredId={hoveredId}
                onHover={setHoveredId}
                onSelect={handleSelectRestaurant}
                onShowDetail={handleShowDetail}
                scrollToId={listScrollTarget}
              />
            ) : (
              <div className="flex h-full min-h-[200px] items-center justify-center rounded-2xl border border-dashed border-line px-4 text-center text-sm text-ink-muted sm:border-none">
                출발지와 도착지를 검색해주세요
              </div>
            )}
          </div>
        </div>
      </div>
    </main>
  );
}

export default function Home() {
  return (
    <Suspense fallback={null}>
      <HomeContent />
    </Suspense>
  );
}
