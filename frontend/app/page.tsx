"use client";

import { Suspense, useEffect, useRef, useState } from "react";
import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import SearchForm, { type SelectedPlace } from "../components/SearchForm";
import FilterBar, { type Filters } from "../components/FilterBar";
import MapFilter from "../components/MapFilter";
import MapView from "../components/MapView";
import RestaurantList from "../components/RestaurantList";
import RestaurantDetail from "../components/RestaurantDetail";
import RestaurantListView from "../components/RestaurantListView";
import SavedPlacesView from "../components/SavedPlacesView";
import {
  ApiError,
  fetchAllRestaurants,
  fetchRouteRestaurants,
  type MapBounds,
  type RestaurantSummary,
  type RouteRestaurantsResponse,
} from "../lib/api";
import { formatDuration } from "../lib/format";
import { useFavorites, type FavoritePlace } from "../lib/favorites";
import { matchesFilters } from "../lib/restaurantFilter";

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

// 출발지·목적지는 이름과 좌표가 모두 있어야 복원되므로 세 개의 파라미터로 나눠 싣는다 —
// "이름@위도,경도" 한 덩어리로 넣으면 이름에 쉼표나 @가 들어갔을 때 다시 못 쪼갠다.
function placeFromParams(
  params: URLSearchParams,
  prefix: "from" | "to"
): SelectedPlace | null {
  const label = params.get(prefix);
  const lat = Number(params.get(`${prefix}_lat`));
  const lng = Number(params.get(`${prefix}_lng`));
  if (!label || !Number.isFinite(lat) || !Number.isFinite(lng)) return null;
  return { label, lat, lng };
}

function CrosshairIcon({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 20 20" fill="none" className={className} aria-hidden="true">
      <circle cx="10" cy="10" r="4" stroke="currentColor" strokeWidth="1.6" />
      <path d="M10 1.5v3M10 15.5v3M1.5 10h3M15.5 10h3" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" />
    </svg>
  );
}

function Chevron({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 20 20" fill="none" className={className} aria-hidden="true">
      <path d="M5 8l5 5 5-5" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

function HomeContent() {
  const searchParams = useSearchParams();
  const router = useRouter();
  const pathname = usePathname();
  // 최초 렌더의 URL을 한 번만 붙잡아 둔다 — 이후로는 상태가 URL을 쓰는 단방향이라,
  // 매 렌더에 searchParams를 다시 읽으면 우리가 쓴 값을 되읽어 루프가 된다.
  // (ref가 아니라 state인 이유: 렌더 중에 읽어야 하는 값이다.)
  const [initialParams] = useState(() => new URLSearchParams(searchParams.toString()));
  const [origin, setOrigin] = useState<SelectedPlace | null>(() => placeFromParams(initialParams, "from"));
  const [destination, setDestination] = useState<SelectedPlace | null>(() => placeFromParams(initialParams, "to"));
  const [filters, setFilters] = useState<Filters>(() => ({
    broadcast: initialParams.get("broadcast") ?? "",
    category: initialParams.get("category") ?? "",
  }));
  const [result, setResult] = useState<RouteRestaurantsResponse | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [detailId, setDetailId] = useState<string | null>(null);
  const [listScrollTarget, setListScrollTarget] = useState<string | null>(null);
  const [mapCenter, setMapCenter] = useState<{ lat: number; lng: number } | null>(null);
  const [mapRestaurants, setMapRestaurants] = useState<RestaurantSummary[]>([]);
  const [browseBroadcast, setBrowseBroadcast] = useState(() => initialParams.get("broadcast") ?? "");
  // geolocation 상태 — 권한 거부/미지원을 사용자에게 알려줘야 버튼이 먹통처럼 보이지 않는다.
  const [geoStatus, setGeoStatus] = useState<"idle" | "locating" | "denied" | "unavailable">("idle");
  // 검색 폼에 지금 들어 있는 값. 검색된 경로(origin/destination)와는 별개다 — 결과를
  // 보는 중에 한쪽만 바꿔도 위쪽 요약은 그대로여야 한다.
  const [formOrigin, setFormOrigin] = useState<SelectedPlace | null>(() => placeFromParams(initialParams, "from"));
  const [formDestination, setFormDestination] = useState<SelectedPlace | null>(() => placeFromParams(initialParams, "to"));
  // "저장한 곳 -> 출발지로"처럼 밖에서 폼 값을 넣을 때만 올린다. SearchForm의 key로
  // 써서 새 초기값으로 다시 마운트시킨다 — 입력창의 표시 텍스트를 부모가 직접
  // 밀어 넣으려면 타이핑 중인 값과 싸우게 되고, 그 동기화가 버그의 온상이다.
  const [formSeedKey, setFormSeedKey] = useState(0);
  const [isSavedViewOpen, setIsSavedViewOpen] = useState(false);
  // viewBounds: 실제로 데이터를 불러온 영역. pendingBounds: 지도가 지금 보여주고 있는 영역.
  // 이 둘이 달라지면(=사용자가 지도를 옮기면) "이 지역에서 다시 검색" 버튼을 보여주고,
  // 버튼을 눌러야 viewBounds가 갱신되어 그 영역 데이터를 불러온다 — 드래그할 때마다
  // 자동으로 다시 불러오지 않는다.
  const [viewBounds, setViewBounds] = useState<MapBounds | null>(null);
  const [pendingBounds, setPendingBounds] = useState<MapBounds | null>(null);
  const [isListViewOpen, setIsListViewOpen] = useState(false);
  // 검색 결과가 나오면 검색 카드를 한 줄 요약으로 접어 목록에 세로 공간을 넘긴다.
  // 결과를 보는 동안 입력창 두 개는 쓸 일이 없고, 세로가 짧은 화면에서는 그 높이가
  // 목록을 한두 칸으로 짜부라뜨리는 주범이다.
  const [isSearchCollapsed, setIsSearchCollapsed] = useState(false);
  // 좌측 패널 전체를 화면 왼쪽으로 밀어 지도를 가리지 않게 하는 상태 (데스크톱 전용 —
  // 모바일에서는 패널이 지도 위에 떠 있지 않고 세로로 쌓여 있어 접을 이유가 없다).
  const [isSidebarCollapsed, setIsSidebarCollapsed] = useState(false);
  const [headerHeight, setHeaderHeight] = useState(0);
  const [logoFailed, setLogoFailed] = useState(false);
  const { favorites } = useFavorites();
  const searchSeqRef = useRef(0);
  const browseSeqRef = useRef(0);
  // 지도를 프로그램이 옮긴 직후(내 위치로 이동 등)에는 "이 지역에서 다시 검색"을 또
  // 누르게 하지 않고 그 영역을 바로 불러온다.
  const autoLoadNextIdleRef = useRef(false);
  const mapContainerRef = useRef<HTMLDivElement>(null);
  const headerRef = useRef<HTMLElement>(null);
  const logoRef = useRef<HTMLImageElement>(null);

  useEffect(() => {
    const el = headerRef.current;
    if (!el) return;
    const updateHeight = () => setHeaderHeight(el.getBoundingClientRect().height);
    updateHeight();
    const observer = new ResizeObserver(updateHeight);
    observer.observe(el);
    return () => observer.disconnect();
  }, []);

  useEffect(() => {
    // 서버에서 렌더된 <img>는 하이드레이션 전에 이미 로드를 시도하므로, 그 사이에
    // 실패하면 onError가 아니라 이 마운트 시점 체크로만 잡힌다.
    const img = logoRef.current;
    if (img && img.complete && img.naturalWidth === 0) {
      setLogoFailed(true);
    }
  }, []);

  useEffect(() => {
    if (!viewBounds) return;
    const seq = ++browseSeqRef.current;
    fetchAllRestaurants({ broadcast: browseBroadcast || undefined, bounds: viewBounds })
      .then((restaurants) => {
        if (seq !== browseSeqRef.current) return;
        setMapRestaurants(restaurants);
      })
      .catch(() => {
        if (seq !== browseSeqRef.current) return;
        setMapRestaurants([]);
      });
  }, [browseBroadcast, viewBounds]);

  // 상태 -> URL 단방향 동기화. 검색한 경로와 필터가 주소에 남아야 새로고침해도
  // 유지되고, 링크로 공유했을 때 상대가 같은 화면을 본다.
  useEffect(() => {
    const params = new URLSearchParams();
    if (origin) {
      params.set("from", origin.label);
      // 소수점 6자리면 약 11cm — 좌표를 그대로 넣으면 주소가 쓸데없이 길어진다.
      params.set("from_lat", origin.lat.toFixed(6));
      params.set("from_lng", origin.lng.toFixed(6));
    }
    if (destination) {
      params.set("to", destination.label);
      params.set("to_lat", destination.lat.toFixed(6));
      params.set("to_lng", destination.lng.toFixed(6));
    }
    // 경로 모드와 브라우즈 모드는 각자 필터를 들고 있다 — 지금 보고 있는 쪽을 싣는다.
    const broadcast = result ? filters.broadcast : browseBroadcast;
    if (broadcast) params.set("broadcast", broadcast);
    if (result && filters.category) params.set("category", filters.category);

    const qs = params.toString();
    router.replace(qs ? `${pathname}?${qs}` : pathname, { scroll: false });
  }, [origin, destination, filters, browseBroadcast, result, router, pathname]);

  function roundedBoundsKey(bounds: MapBounds): string {
    return `${bounds.minLat.toFixed(4)},${bounds.maxLat.toFixed(4)},${bounds.minLng.toFixed(4)},${bounds.maxLng.toFixed(4)}`;
  }

  function handleBoundsIdle(bounds: MapBounds) {
    setPendingBounds(bounds);
    if (autoLoadNextIdleRef.current) {
      // 사용자가 드래그한 게 아니라 우리가 옮긴 것 — 그 동네를 바로 불러준다.
      autoLoadNextIdleRef.current = false;
      setViewBounds(bounds);
      return;
    }
    // 최초 idle에서만 곧바로 viewBounds를 채워 첫 화면 영역 기준으로 자동 로드한다 —
    // 그 이후로는 사용자가 "다시 검색" 버튼을 눌러야 viewBounds가 바뀐다.
    setViewBounds((current) => current ?? bounds);
  }

  function handleUseMyLocation() {
    if (typeof navigator === "undefined" || !navigator.geolocation) {
      setGeoStatus("unavailable");
      return;
    }
    setGeoStatus("locating");
    navigator.geolocation.getCurrentPosition(
      (position) => {
        setGeoStatus("idle");
        autoLoadNextIdleRef.current = true;
        setMapCenter({ lat: position.coords.latitude, lng: position.coords.longitude });
      },
      () => setGeoStatus("denied"),
      // 맛집을 찾는 데 미터 단위 정확도는 필요 없다 — 고정밀을 끄면 실내에서도
      // 훨씬 빨리 잡히고 배터리도 덜 쓴다. 5분 이내 캐시는 그대로 재사용한다.
      { enableHighAccuracy: false, timeout: 10000, maximumAge: 300000 }
    );
  }

  function handleRefreshArea() {
    if (pendingBounds) setViewBounds(pendingBounds);
  }

  const showRefreshArea = Boolean(
    !result && pendingBounds && viewBounds && roundedBoundsKey(pendingBounds) !== roundedBoundsKey(viewBounds)
  );

  async function runSearch(searchOrigin: SelectedPlace, searchDestination: SelectedPlace) {
    const seq = ++searchSeqRef.current;
    setIsLoading(true);
    setErrorMessage(null);
    setDetailId(null);
    try {
      // 방송/업종 필터는 백엔드에 안 보낸다 — 경로 후보 전체를 한 번만 받아두고,
      // 필터를 바꿀 때마다 재검색(카카오 길찾기 재호출 포함) 없이 클라이언트에서
      // 강조/흐림 처리만 한다 (MapView/RestaurantList에 넘기는 activeFilters).
      const response = await fetchRouteRestaurants({
        originLat: searchOrigin.lat,
        originLng: searchOrigin.lng,
        destinationLat: searchDestination.lat,
        destinationLng: searchDestination.lng,
      });
      if (seq !== searchSeqRef.current) return;
      setResult(response);
      setIsSearchCollapsed(true);
    } catch (error) {
      if (seq !== searchSeqRef.current) return;
      setErrorMessage(errorMessageFor(error));
    } finally {
      if (seq !== searchSeqRef.current) return;
      setIsLoading(false);
    }
  }

  // 출발지·목적지가 실린 링크로 들어왔으면 바로 검색해준다 — 공유받은 사람이
  // 버튼을 한 번 더 누르지 않아도 같은 화면을 본다.
  const didRestoreSearchRef = useRef(false);
  useEffect(() => {
    if (didRestoreSearchRef.current) return;
    didRestoreSearchRef.current = true;
    const from = placeFromParams(initialParams, "from");
    const to = placeFromParams(initialParams, "to");
    // runSearch가 곧바로 setIsLoading을 부르므로, effect 안에서 동기로 호출하면
    // 마운트 렌더에 연쇄 렌더가 붙는다. 한 틱 미뤄 첫 페인트를 막지 않는다.
    // (cleanup으로 취소하지 않는 건 의도적 — StrictMode의 이중 실행은 위 ref가
    //  막아주는데, 여기서 clearTimeout까지 하면 개발 모드에서 검색이 아예 안 뜬다.)
    if (from && to) setTimeout(() => runSearch(from, to), 0);
    // 최초 1회만 — initialParams는 첫 렌더에 고정된 값이라 의존성이 바뀌지 않는다.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  function handleSearch(searchOrigin: SelectedPlace, searchDestination: SelectedPlace) {
    setOrigin(searchOrigin);
    setDestination(searchDestination);
    setFormOrigin(searchOrigin);
    setFormDestination(searchDestination);
    runSearch(searchOrigin, searchDestination);
  }

  function handleBackToMap() {
    // 진행 중인 검색이 있으면 그 응답이 뒤늦게 도착해 경로 모드로 되돌려버린다 —
    // runSearch가 자기 seq를 확인하므로 여기서 seq를 올려 무효화한다.
    searchSeqRef.current += 1;
    setIsLoading(false);
    setResult(null);
    setOrigin(null);
    setDestination(null);
    setSelectedId(null);
    setDetailId(null);
    setListScrollTarget(null);
    setErrorMessage(null);
    // 검색 카드를 다시 펼친다. SearchForm은 언마운트되지 않아 입력해둔 장소가 남아
    // 있으므로, 바로 다시 검색할 수 있다.
    setIsSearchCollapsed(false);
    // 경로용 방송/업종 필터는 브라우즈 모드에서 안 쓰이니 비운다 (지도 필터는 별도).
    setFilters({ broadcast: "", category: "" });
    // 경로를 따라 지도를 옮겨왔을 수 있어서, viewBounds가 지금 보이는 영역과 다르다.
    // 지금 영역으로 갱신해두면 "이 지역에서 다시 검색"을 한 번 더 누르지 않아도
    // 곧바로 그 동네 맛집이 찍힌다.
    if (pendingBounds) setViewBounds(pendingBounds);
  }

  function handleFiltersChange(newFilters: Filters) {
    setFilters(newFilters);
  }

  function handleFormOriginChange(place: SelectedPlace | null) {
    setFormOrigin(place);
    if (place) setMapCenter({ lat: place.lat, lng: place.lng });
  }

  function seedForm(place: FavoritePlace, as: "origin" | "destination") {
    const selected: SelectedPlace = { label: place.name, lat: place.latitude, lng: place.longitude };
    if (as === "origin") setFormOrigin(selected);
    else setFormDestination(selected);
    setFormSeedKey((key) => key + 1);
    setIsSavedViewOpen(false);
    setIsSidebarCollapsed(false);
    setIsSearchCollapsed(false);
    setMapCenter({ lat: place.latitude, lng: place.longitude });
  }

  function handleShowFavoriteOnMap(place: FavoritePlace) {
    setIsSavedViewOpen(false);
    autoLoadNextIdleRef.current = true;
    setMapCenter({ lat: place.latitude, lng: place.longitude });
  }

  function handleSelectRestaurant(id: string) {
    setSelectedId(id);
  }

  function handleShowDetail(id: string) {
    setDetailId(id);
    setSelectedId(id);
    // 상세는 좌측 패널 안에 그려진다 — 접혀 있으면 눌러도 아무 일도 안 일어난 것처럼
    // 보이므로 펼쳐준다.
    setIsSidebarCollapsed(false);
  }

  function handleMarkerClick(id: string) {
    setDetailId(null);
    setSelectedId(id);
    setListScrollTarget(id);
  }

  const activeRestaurants = result ? result.restaurants : mapRestaurants;
  const detailRestaurant = detailId ? activeRestaurants.find((r) => r.id === detailId) ?? null : null;

  const isJourneyReady = Boolean(result && origin && destination);
  // 검색 후 부제에 쓰는 개수 — RestaurantList는 필터를 강조/흐림에만 쓰고 경로 후보
  // 전체를 그리므로, 이 값이 실제로 목록에 보이는 칸 수와 같다.
  const routeCount = result?.restaurants.length ?? 0;
  // 결과가 있을 때만 접을 수 있다 — 검색 전에 접히면 아무것도 할 수 없는 화면이 된다.
  const isSearchCardCollapsed = isJourneyReady && isSearchCollapsed;
  const hasActiveRouteFilter = Boolean(filters.broadcast || filters.category);
  const filteredMatchCount = result
    ? result.restaurants.filter((r) => matchesFilters(r, filters)).length
    : 0;
  const noFilterMatches = hasActiveRouteFilter && result !== null && result.restaurants.length > 0 && filteredMatchCount === 0;

  return (
    <main className="relative flex min-h-screen w-full flex-col overflow-hidden sm:h-screen sm:min-h-0">
      {/* 지도 — 데스크톱에서는 화면 전체를 채우는 배경, 모바일에서는 지금처럼 목록 위에 고정 높이로 위치.
          검색 전에는 전체 맛집을, 검색 후에는 경로상 맛집만 보여준다. */}
      <div ref={mapContainerRef} className="relative order-3 min-h-0 p-4 pb-0 sm:absolute sm:inset-0 sm:p-0">
        <MapView
          route={result?.route.points ?? []}
          restaurants={activeRestaurants}
          highlightedRestaurantId={selectedId}
          center={mapCenter}
          activeBroadcast={(result ? filters.broadcast : browseBroadcast) || null}
          activeFilters={result ? filters : null}
          onBoundsIdle={handleBoundsIdle}
          onMarkerClick={handleMarkerClick}
          onShowDetail={handleShowDetail}
        />
        <div className="absolute right-6 top-4 z-10 sm:top-24">
          {result ? (
            <button
              type="button"
              onClick={handleBackToMap}
              className="pointer-events-auto rounded-xl border border-white/10 bg-[#171310]/95 px-3 py-2 text-sm font-medium text-[#fff7ed] shadow-xl shadow-black/30 backdrop-blur-xl transition hover:bg-[#29201a]"
            >
              전체 지도 보기
            </button>
          ) : (
            <MapFilter value={browseBroadcast} onChange={setBrowseBroadcast} />
          )}
        </div>
        {/* 내 주변 — 지도 좌측 하단. 우측 상단(필터/전체 지도 보기)과 중앙 상단
            ("이 지역에서 다시 검색")이 이미 차 있어서 겹치지 않는 자리에 둔다. */}
        <div className="pointer-events-none absolute bottom-6 right-6 z-10 flex flex-col items-end gap-2">
          {geoStatus !== "idle" && geoStatus !== "locating" && (
            <span className="pointer-events-auto rounded-lg bg-[#171310]/95 px-3 py-1.5 text-xs text-[#fca5a5] shadow-lg backdrop-blur-xl">
              {geoStatus === "denied"
                ? "위치 권한이 없어요 — 브라우저 설정에서 허용해주세요"
                : "이 브라우저는 위치를 지원하지 않아요"}
            </span>
          )}
          <button
            type="button"
            onClick={handleUseMyLocation}
            disabled={geoStatus === "locating"}
            className="pointer-events-auto flex items-center gap-2 rounded-xl border border-white/10 bg-[#171310]/95 px-3 py-2 text-sm font-medium text-[#fff7ed] shadow-xl shadow-black/30 backdrop-blur-xl transition hover:bg-[#29201a] disabled:cursor-not-allowed disabled:text-[#a89c91]"
          >
            <CrosshairIcon className="h-4 w-4 shrink-0 text-[#ffb45a]" />
            {geoStatus === "locating" ? "위치 찾는 중" : "내 주변"}
          </button>
        </div>
        {showRefreshArea && (
          <div className="absolute left-1/2 top-4 z-10 -translate-x-1/2 sm:top-24">
            <button
              type="button"
              onClick={handleRefreshArea}
              className="rounded-full bg-[#ff7a1a] px-4 py-2 text-sm font-bold text-[#171310] shadow-[0_4px_16px_-4px_rgba(255,122,26,0.6)] transition hover:bg-[#ffb45a]"
            >
              이 지역에서 다시 검색
            </button>
          </div>
        )}
      </div>

      {/* 검색+필터+목록 — 모바일에서는 지금처럼 세로로 쌓이고(display: contents로 위 지도 사이에 끼워짐),
          데스크톱에서는 지도 위에 뜨는 좌측 사이드바 하나로 묶인다.
          두 패널의 z-20 / z-0: 각 패널의 backdrop-blur가 stacking context를 만들어서
          방송 드롭다운이 자기 z-20으로는 카드 밖으로 못 올라온다. 카드가 DOM에서 목록보다
          앞이라 순서를 안 정해주면 목록이 위에 그려져 펼친 드롭다운을 덮어버린다. */}
      <header ref={headerRef} className="pointer-events-none relative z-20 flex items-center justify-between bg-[#171310]/95 px-5 py-4 text-[#fff7ed] shadow-lg shadow-black/10 backdrop-blur-xl sm:absolute sm:inset-x-0 sm:top-0 sm:bg-[#171310]/85 sm:px-7">
        <Link href="/" className="pointer-events-auto">
          {logoFailed ? (
            <span className="text-lg font-black tracking-tight text-[#fff7ed] sm:text-xl">
              맛집<span className="text-[#ff7a1a]">로드</span>
            </span>
          ) : (
            // eslint-disable-next-line @next/next/no-img-element
            <img
              ref={logoRef}
              src="/logo.png"
              alt="맛집로드"
              className="h-7 w-auto sm:h-8"
              onError={() => setLogoFailed(true)}
            />
          )}
        </Link>
        <nav className="pointer-events-auto flex items-center gap-3 text-sm text-[#a89c91] sm:gap-4">
          <button
            type="button"
            onClick={() => setIsSavedViewOpen(true)}
            className="flex items-center gap-1.5 rounded-full border border-white/10 px-3 py-1.5 text-sm font-medium text-[#fff7ed] transition hover:bg-white/10"
          >
            저장한 곳
            {favorites.length > 0 && (
              <span className="grid h-5 min-w-5 place-items-center rounded-full bg-[#ff7a1a] px-1 text-xs font-bold text-[#171310]">
                {favorites.length}
              </span>
            )}
          </button>
          <button
            type="button"
            onClick={() => setIsListViewOpen(true)}
            className="rounded-full bg-[#ff7a1a] px-4 py-1.5 text-sm font-bold text-[#171310] shadow-[0_4px_16px_-4px_rgba(255,122,26,0.6)] transition hover:bg-[#ffb45a]"
          >
            🍽 맛집 목록 보기
          </button>
        </nav>
      </header>

      {isListViewOpen && (
        <RestaurantListView onClose={() => setIsListViewOpen(false)} topOffset={headerHeight} />
      )}

      {isSavedViewOpen && (
        <SavedPlacesView
          onClose={() => setIsSavedViewOpen(false)}
          topOffset={headerHeight}
          onShowOnMap={handleShowFavoriteOnMap}
          onSetAsOrigin={(place) => seedForm(place, "origin")}
          onSetAsDestination={(place) => seedForm(place, "destination")}
        />
      )}

      {/* 사이드바 접기/펼치기 손잡이 — 데스크톱 전용. 화면 세로 중앙에 혼자 떠 있으면
          지도 위에 붕 뜬 요소처럼 보여서, 패널 상단 모서리에 붙여 패널의 일부처럼
          보이게 한다. top 값은 패널을 감싸는 아래 div와 동일하게 맞춰 붙어 보이게 한다.
          접으면 자기 위치만큼 왼쪽으로 이동해 화면 왼쪽 가장자리에 남는다 — 패널과
          함께 translate로 움직이므로 두 요소가 같은 속도로 붙어서 미끄러진다. */}
      <button
        type="button"
        onClick={() => setIsSidebarCollapsed((collapsed) => !collapsed)}
        aria-expanded={!isSidebarCollapsed}
        aria-label={isSidebarCollapsed ? "검색 패널 펼치기" : "검색 패널 접기"}
        className={`hidden sm:absolute sm:left-[calc(var(--sidebar-gap)+var(--sidebar-w))] sm:top-24 sm:z-10 sm:flex sm:h-12 sm:w-7 sm:items-center sm:justify-center sm:rounded-r-xl sm:border sm:border-l-0 sm:border-white/10 sm:bg-[#171310]/95 sm:text-[#a89c91] sm:shadow-xl sm:shadow-black/30 sm:backdrop-blur-xl sm:transition sm:duration-300 sm:hover:text-[#fff7ed] sm:short:top-[84px] ${
          isSidebarCollapsed ? "sm:-translate-x-[calc(var(--sidebar-gap)+var(--sidebar-w))]" : ""
        }`}
      >
        <Chevron className={`h-4 w-4 ${isSidebarCollapsed ? "-rotate-90" : "rotate-90"}`} />
      </button>

      <div
        className={`contents sm:pointer-events-none sm:absolute sm:bottom-[var(--sidebar-gap)] sm:left-[var(--sidebar-gap)] sm:top-20 sm:z-10 sm:flex sm:w-[var(--sidebar-w)] sm:flex-col sm:gap-3 sm:transition-transform sm:duration-300 sm:short:top-[68px] sm:short:gap-2 ${
          isSidebarCollapsed ? "sm:-translate-x-[calc(var(--sidebar-w)+var(--sidebar-gap))]" : ""
        }`}
      >
        <div className="relative z-20 order-1 shrink-0 p-4 pb-0 sm:pointer-events-auto sm:p-0">
          <div className="rounded-2xl border border-white/10 bg-[#29201a]/95 p-5 shadow-xl shadow-black/25 backdrop-blur-xl sm:short:p-4">
            {isSearchCardCollapsed && (
              <button
                type="button"
                onClick={() => setIsSearchCollapsed(false)}
                aria-expanded={false}
                className="flex w-full items-center gap-2 text-left transition hover:opacity-80"
              >
                <span className="min-w-0 flex-1 truncate text-sm font-semibold text-[#fff7ed]">
                  {origin?.label} <span className="text-[#a89c91]">→</span> {destination?.label}
                </span>
                {result && (
                  <span className="shrink-0 text-xs text-[#ffb45a]">
                    {formatDuration(result.route.total_duration_sec)}
                    {routeCount > 0 && ` · ${routeCount}곳`}
                  </span>
                )}
                <Chevron className="h-4 w-4 shrink-0 text-[#a89c91]" />
              </button>
            )}
            {/* 언마운트하지 않고 숨긴다 — SearchForm이 입력값을 직접 들고 있어서
                언마운트하면 다시 펼쳤을 때 입력해둔 장소가 사라진다. */}
            <div className={isSearchCardCollapsed ? "hidden" : undefined}>
              <div className="mb-5 sm:short:mb-3">
                <p className="text-xs font-bold tracking-[0.16em] text-[#ffb45a]">ON-AIR FOOD ROAD</p>
                <div className="flex items-start justify-between gap-2">
                  <h1 className="mt-1 text-xl font-bold tracking-tight text-[#fff7ed] sm:short:text-lg">{isJourneyReady ? "가는 길의 방송 맛집" : "가는 길에서 방송 맛집을 확인하세요"}</h1>
                  {isJourneyReady && (
                    <button
                      type="button"
                      onClick={() => setIsSearchCollapsed(true)}
                      aria-expanded
                      aria-label="검색창 접기"
                      className="mt-1 shrink-0 rounded-full p-1 text-[#a89c91] transition hover:bg-white/10 hover:text-[#fff7ed]"
                    >
                      <Chevron className="h-4 w-4 rotate-180" />
                    </button>
                  )}
                </div>
                <p className="mt-1 text-sm text-[#a89c91] sm:short:hidden">
                  {!isJourneyReady
                    ? "TV·유튜브에 나온 맛집만 골라 경로 위에 놓아드려요"
                    : routeCount > 0
                      ? `지나가는 순서대로 ${routeCount}곳`
                      : "경로 근처에서 방송 맛집을 찾지 못했어요"}
                </p>
              </div>
              <SearchForm
                key={formSeedKey}
                onOriginChange={handleFormOriginChange}
                onDestinationChange={setFormDestination}
                onSearch={handleSearch}
                isLoading={isLoading}
                initialOrigin={formOrigin}
                initialDestination={formDestination}
              />
            </div>
            {isJourneyReady && <><div className="my-4 border-t border-white/10 sm:short:my-3" /><FilterBar filters={filters} onChange={handleFiltersChange} /></>}
          </div>
        </div>

        {errorMessage && (
          <div className="order-2 shrink-0 px-4 sm:pointer-events-auto sm:px-0">
            <div className="rounded-xl border border-danger/20 bg-danger-soft px-4 py-3 text-sm text-danger-ink">
              {errorMessage}
            </div>
          </div>
        )}

        <div className="relative z-0 order-4 p-4 pt-0 sm:min-h-0 sm:flex-1 sm:overflow-hidden sm:p-0 sm:pointer-events-auto">
          <div className="no-scrollbar sm:h-full sm:overflow-y-auto sm:rounded-2xl sm:border sm:border-white/10 sm:bg-[#29201a]/95 sm:p-3 sm:shadow-xl sm:shadow-black/25 sm:backdrop-blur-xl sm:short:p-2">
            {detailRestaurant ? (
              <RestaurantDetail restaurant={detailRestaurant} onBack={() => setDetailId(null)} />
            ) : result ? (
              <>
                {!isSearchCardCollapsed && (
                  <div className="mb-3 flex items-center justify-between px-1 pt-1 text-sm">
                    <span className="font-semibold text-[#fff7ed]">{origin?.label} <span className="text-[#a89c91]">→</span> {destination?.label}</span>
                    <span className="text-xs text-[#ffb45a]">{formatDuration(result.route.total_duration_sec)}</span>
                  </div>
                )}
                {noFilterMatches && (
                  <div className="mb-3 rounded-xl bg-white/5 px-3 py-2 text-xs text-[#a89c91]">
                    이 조건에 맞는 곳이 없어요 — 경로 전체 결과를 보여드려요
                  </div>
                )}
                <RestaurantList
                  restaurants={result.restaurants}
                  selectedId={selectedId}
                  activeFilters={filters}
                  onSelect={handleSelectRestaurant}
                  onShowDetail={handleShowDetail}
                  scrollToId={listScrollTarget}
                />
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
