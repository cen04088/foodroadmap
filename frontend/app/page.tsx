"use client";

import { Suspense, useEffect, useRef, useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import SearchForm, { type SelectedPlace } from "../components/SearchForm";
import FilterBar, { type Filters } from "../components/FilterBar";
import MapFilter from "../components/MapFilter";
import MapView from "../components/MapView";
import RestaurantList from "../components/RestaurantList";
import RestaurantDetail from "../components/RestaurantDetail";
import {
  ApiError,
  fetchAllRestaurants,
  fetchRouteRestaurants,
  type RestaurantSummary,
  type RouteRestaurantsResponse,
} from "../lib/api";
import { formatDuration } from "../lib/format";

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
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [detailId, setDetailId] = useState<string | null>(null);
  const [listScrollTarget, setListScrollTarget] = useState<string | null>(null);
  const [mapCenter, setMapCenter] = useState<{ lat: number; lng: number } | null>(null);
  const [radiusKm, setRadiusKm] = useState(2);
  const [browseRestaurants, setBrowseRestaurants] = useState<RestaurantSummary[]>([]);
  const [browseBroadcast, setBrowseBroadcast] = useState("");
  const searchSeqRef = useRef(0);
  const browseSeqRef = useRef(0);
  const filterDebounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const mapContainerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const seq = ++browseSeqRef.current;
    fetchAllRestaurants({ broadcast: browseBroadcast || undefined })
      .then((restaurants) => {
        if (seq !== browseSeqRef.current) return;
        setBrowseRestaurants(restaurants);
      })
      .catch(() => {
        if (seq !== browseSeqRef.current) return;
        setBrowseRestaurants([]);
      });
  }, [browseBroadcast]);

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
        radiusKm,
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
    setSelectedId(id);
  }

  function handleShowDetail(id: string) {
    setDetailId(id);
    setSelectedId(id);
  }

  function handleMarkerClick(id: string) {
    setDetailId(null);
    setSelectedId(id);
    setListScrollTarget(id);
  }

  const detailRestaurant = detailId ? result?.restaurants.find((r) => r.id === detailId) ?? null : null;

  const isJourneyReady = Boolean(result && origin && destination);

  return (
    <main className="relative flex min-h-screen w-full flex-col overflow-hidden sm:h-screen sm:min-h-0">
      {/* 지도 — 데스크톱에서는 화면 전체를 채우는 배경, 모바일에서는 지금처럼 목록 위에 고정 높이로 위치.
          검색 전에는 전체 맛집을, 검색 후에는 경로상 맛집만 보여준다. */}
      <div ref={mapContainerRef} className="relative order-3 min-h-0 p-4 pb-0 sm:absolute sm:inset-0 sm:p-0">
        <MapView
          route={result?.route.points ?? []}
          restaurants={result ? result.restaurants : browseRestaurants}
          highlightedRestaurantId={selectedId}
          center={mapCenter}
          activeBroadcast={(result ? filters.broadcast : browseBroadcast) || null}
          onMarkerClick={handleMarkerClick}
        />
        {!result && (
          <div className="absolute right-6 top-4 z-10 sm:top-6">
            <MapFilter value={browseBroadcast} onChange={setBrowseBroadcast} />
          </div>
        )}
      </div>

      {/* 검색+필터+목록 — 모바일에서는 지금처럼 세로로 쌓이고(display: contents로 위 지도 사이에 끼워짐),
          데스크톱에서는 지도 위에 뜨는 좌측 사이드바 하나로 묶인다. */}
      <header className="pointer-events-none relative z-20 flex items-center justify-between bg-[#171310]/95 px-5 py-4 text-[#fff7ed] shadow-lg shadow-black/10 backdrop-blur-xl sm:absolute sm:inset-x-0 sm:top-0 sm:bg-[#171310]/85 sm:px-7">
        <Link href="/" className="pointer-events-auto text-xl font-black tracking-[-0.06em] text-[#ffb45a]">FOODMAP</Link>
        <nav className="pointer-events-auto flex items-center gap-4 text-sm text-[#a89c91] sm:gap-6">
          <span className="hidden sm:inline">미식 로드트립</span>
          <Link href="/broadcasts" className="transition hover:text-[#fff7ed]">프로그램</Link>
        </nav>
      </header>

      <div className="contents sm:pointer-events-none sm:absolute sm:bottom-6 sm:left-6 sm:top-20 sm:z-10 sm:flex sm:w-[390px] sm:flex-col sm:gap-3">
        <div className="order-1 shrink-0 p-4 pb-0 sm:pointer-events-auto sm:p-0">
          <div className="rounded-2xl border border-white/10 bg-[#29201a]/95 p-5 shadow-xl shadow-black/25 backdrop-blur-xl">
            <div className="mb-5">
              <p className="text-xs font-bold tracking-[0.16em] text-[#ffb45a]">MY FOOD ROAD</p>
              <h1 className="mt-1 text-xl font-bold tracking-tight text-[#fff7ed]">{isJourneyReady ? "가는 길의 맛집" : "오늘의 미식 로드트립"}</h1>
              <p className="mt-1 text-sm text-[#a89c91]">{isJourneyReady ? "시간순으로 들를 곳을 골라보세요" : "목적지까지 가는 길이, 맛집 여행이 됩니다."}</p>
            </div>
            <SearchForm onOriginSelect={handleOriginSelect} onSearch={handleSearch} isLoading={isLoading} />
            {!isJourneyReady && (
              <div className="mt-5 border-t border-white/10 pt-4">
                <p className="mb-2 text-xs font-medium text-[#a89c91]">추천 반경 <span className="ml-2 text-[#ffb45a]">{radiusKm}km</span></p>
                <div className="flex gap-2 text-xs">
                  {[1, 2, 3].map((km) => (
                    <button
                      key={km}
                      type="button"
                      onClick={() => setRadiusKm(km)}
                      className={`rounded-full px-3 py-1.5 transition ${
                        radiusKm === km
                          ? "bg-[#ff7a1a] font-semibold text-[#171310]"
                          : "bg-white/5 text-[#a89c91] hover:bg-white/10"
                      }`}
                    >
                      {radiusKm === km ? "●" : "○"} {km}km
                    </button>
                  ))}
                </div>
              </div>
            )}
            {isJourneyReady && <><div className="my-4 border-t border-white/10" /><FilterBar filters={filters} onChange={handleFiltersChange} /></>}
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
          <div className="sm:h-full sm:overflow-y-auto sm:rounded-2xl sm:border sm:border-white/10 sm:bg-[#29201a]/95 sm:p-3 sm:shadow-xl sm:shadow-black/25 sm:backdrop-blur-xl">
            {detailRestaurant ? (
              <RestaurantDetail restaurant={detailRestaurant} onBack={() => setDetailId(null)} />
            ) : result ? (
              <>
                <div className="mb-3 flex items-center justify-between px-1 pt-1 text-sm">
                  <span className="font-semibold text-[#fff7ed]">{origin?.label} <span className="text-[#a89c91]">→</span> {destination?.label}</span>
                  <span className="text-xs text-[#ffb45a]">{formatDuration(result.route.total_duration_sec)}</span>
                </div>
                <RestaurantList restaurants={result.restaurants} selectedId={selectedId} onSelect={handleSelectRestaurant} onShowDetail={handleShowDetail} scrollToId={listScrollTarget} />
              </>
            ) : (
              <div className="flex h-full min-h-[200px] items-center justify-center rounded-2xl border border-dashed border-white/10 px-4 text-center text-sm text-[#a89c91] sm:border-none">
                출발지와 목적지를 정하면, 가는 길의 방송 맛집을 시간순으로 안내해드려요.
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
