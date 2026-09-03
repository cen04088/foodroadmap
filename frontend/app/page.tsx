"use client";

import { useState } from "react";
import SearchForm, { type SelectedPlace } from "../components/SearchForm";
import FilterBar, { type Filters } from "../components/FilterBar";
import MapView from "../components/MapView";
import RestaurantList from "../components/RestaurantList";
import { ApiError, fetchRouteRestaurants, type RouteRestaurantsResponse } from "../lib/api";

function errorMessageFor(error: unknown): string {
  if (error instanceof ApiError) {
    if (error.status === 0) return "서버에 연결할 수 없습니다";
    if (error.status === 500) return "일시적인 오류입니다, 잠시 후 다시 시도해주세요";
    if (error.status === 502) return "경로를 가져오지 못했습니다, 다시 시도해주세요";
    return "요청 중 오류가 발생했습니다";
  }
  return "알 수 없는 오류가 발생했습니다";
}

export default function Home() {
  const [origin, setOrigin] = useState<SelectedPlace | null>(null);
  const [destination, setDestination] = useState<SelectedPlace | null>(null);
  const [filters, setFilters] = useState<Filters>({ broadcast: "", category: "" });
  const [result, setResult] = useState<RouteRestaurantsResponse | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [hoveredId, setHoveredId] = useState<string | null>(null);
  const [mapCenter, setMapCenter] = useState<{ lat: number; lng: number } | null>(null);

  async function runSearch(
    searchOrigin: SelectedPlace,
    searchDestination: SelectedPlace,
    searchFilters: Filters
  ) {
    setIsLoading(true);
    setErrorMessage(null);
    try {
      const response = await fetchRouteRestaurants({
        originLat: searchOrigin.lat,
        originLng: searchOrigin.lng,
        destinationLat: searchDestination.lat,
        destinationLng: searchDestination.lng,
        broadcast: searchFilters.broadcast || undefined,
        category: searchFilters.category || undefined,
      });
      setResult(response);
    } catch (error) {
      setErrorMessage(errorMessageFor(error));
    } finally {
      setIsLoading(false);
    }
  }

  function handleSearch(searchOrigin: SelectedPlace, searchDestination: SelectedPlace) {
    setOrigin(searchOrigin);
    setDestination(searchDestination);
    runSearch(searchOrigin, searchDestination, filters);
  }

  function handleFiltersChange(newFilters: Filters) {
    setFilters(newFilters);
    if (origin && destination) {
      runSearch(origin, destination, newFilters);
    }
  }

  function handleOriginSelect(place: SelectedPlace) {
    setMapCenter({ lat: place.lat, lng: place.lng });
  }

  return (
    <main className="flex h-screen flex-col gap-4 p-4">
      <div className="flex flex-col gap-2">
        <SearchForm onOriginSelect={handleOriginSelect} onSearch={handleSearch} isLoading={isLoading} />
        <FilterBar filters={filters} onChange={handleFiltersChange} />
      </div>

      {errorMessage && <p className="text-sm text-red-600">{errorMessage}</p>}

      <div className="flex flex-1 flex-col gap-4 overflow-hidden sm:flex-row">
        <div className="sm:w-2/3">
          <MapView
            route={result?.route.points ?? []}
            restaurants={result?.restaurants ?? []}
            highlightedRestaurantId={hoveredId}
            center={mapCenter}
          />
        </div>
        <div className="sm:w-1/3 sm:overflow-y-auto">
          {result ? (
            <RestaurantList restaurants={result.restaurants} hoveredId={hoveredId} onHover={setHoveredId} />
          ) : (
            <p className="p-4 text-center text-gray-500">출발지와 도착지를 검색해주세요</p>
          )}
        </div>
      </div>
    </main>
  );
}
