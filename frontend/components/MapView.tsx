"use client";

import { useEffect, useRef, useState } from "react";
import { loadKakaoMapsSdk } from "../lib/kakaoMap";
import type { RestaurantResult, RestaurantSummary, RoutePoint } from "../lib/api";
import { formatDuration } from "../lib/format";
import { getBroadcastColor } from "../lib/broadcastColors";

const DEFAULT_CENTER = { lat: 37.5665, lng: 126.978 }; // 서울시청
const MARKER_SIZE = 30;
const MARKER_SIZE_HIGHLIGHTED = 38;

function escapeHtml(value: string): string {
  return value
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}

function hasRouteInfo(restaurant: RestaurantSummary): restaurant is RestaurantResult {
  return "distance_from_route_km" in restaurant && "cumulative_time_sec" in restaurant;
}

// 활성 방송 필터에 해당하는 방송이 있으면 그 방송, 없으면 첫 번째 방송 기준으로 마커 색을 정한다.
function pickBroadcastName(restaurant: RestaurantSummary, activeBroadcast: string | null): string | null {
  if (activeBroadcast && restaurant.broadcasts.includes(activeBroadcast)) {
    return activeBroadcast;
  }
  return restaurant.broadcasts[0] ?? null;
}

function markerImageDataUrl(color: string, letter: string, isHighlighted: boolean): string {
  const size = isHighlighted ? MARKER_SIZE_HIGHLIGHTED : MARKER_SIZE;
  const ringColor = isHighlighted ? "#FF7A1A" : "#FFFFFF";
  const ringWidth = isHighlighted ? 3 : 2;
  const r = size / 2 - ringWidth;
  const fontSize = Math.round(size * 0.42);
  const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="${size}" height="${size}" viewBox="0 0 ${size} ${size}">${
    isHighlighted ? `<circle cx="${size / 2}" cy="${size / 2}" r="${size / 2}" fill="${color}" opacity="0.25"/>` : ""
  }<circle cx="${size / 2}" cy="${size / 2}" r="${r}" fill="${color}" stroke="${ringColor}" stroke-width="${ringWidth}"/><text x="${size / 2}" y="${size / 2 + fontSize * 0.35}" font-family="Pretendard, sans-serif" font-size="${fontSize}" font-weight="800" fill="#FFFFFF" text-anchor="middle">${letter}</text></svg>`;
  return `data:image/svg+xml;charset=UTF-8,${encodeURIComponent(svg)}`;
}

export interface MapViewProps {
  route: RoutePoint[];
  restaurants: RestaurantSummary[];
  highlightedRestaurantId: string | null;
  center: { lat: number; lng: number } | null;
  activeBroadcast?: string | null;
  // 경로 검색 결과는 스탑 순서가 중요해 마커를 뭉치면 안 되고, 전체 브라우징(수천 개)에서만 뭉쳐야 한다.
  enableClustering?: boolean;
  onMarkerClick?: (id: string) => void;
  onShowDetail?: (id: string) => void;
}

export default function MapView({
  route,
  restaurants,
  highlightedRestaurantId,
  center,
  activeBroadcast = null,
  enableClustering = false,
  onMarkerClick,
  onShowDetail,
}: MapViewProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<any>(null);
  const kakaoRef = useRef<any>(null);
  const polylineRef = useRef<any>(null);
  const clustererRef = useRef<any>(null);
  const markersRef = useRef<Map<string, any>>(new Map());
  const markerMetaRef = useRef<Map<string, { color: string; letter: string }>>(new Map());
  const highlightedIdRef = useRef<string | null>(null);
  const infoWindowRef = useRef<any>(null);
  const centerRef = useRef(center);
  const onMarkerClickRef = useRef(onMarkerClick);
  const onShowDetailRef = useRef(onShowDetail);
  const [loadError, setLoadError] = useState(false);

  useEffect(() => {
    centerRef.current = center;
  }, [center]);

  useEffect(() => {
    onMarkerClickRef.current = onMarkerClick;
  }, [onMarkerClick]);

  useEffect(() => {
    onShowDetailRef.current = onShowDetail;
  }, [onShowDetail]);

  // 카카오 InfoWindow는 순수 HTML 문자열이라 React 이벤트 핸들러를 못 붙인다 —
  // "자세히 보기" 버튼의 onclick에서 호출할 전역 함수를 하나 등록해둔다.
  useEffect(() => {
    (window as any).__foodmapShowDetail = (id: string) => {
      onShowDetailRef.current?.(id);
    };
    return () => {
      delete (window as any).__foodmapShowDetail;
    };
  }, []);

  useEffect(() => {
    let cancelled = false;
    let resizeObserver: ResizeObserver | null = null;
    loadKakaoMapsSdk()
      .then((kakao) => {
        if (cancelled || !containerRef.current) return;
        kakaoRef.current = kakao;
        const initialCenter = centerRef.current ?? DEFAULT_CENTER;
        mapRef.current = new kakao.maps.Map(containerRef.current, {
          center: new kakao.maps.LatLng(initialCenter.lat, initialCenter.lng),
          level: 6,
        });
        // minLevel을 굳이 지정하지 않는다 — 지정하면 "그 레벨 이상(더 축소됐을 때)에서만
        // 클러스터링"이 되는데, 기본 줌 레벨(6)에서부터 곧바로 뭉쳐 보여야 초기 로딩 마커 수가
        // 실제로 줄어든다. 라이브러리 기본값은 거의 모든 축소 단계에서 클러스터링한다.
        clustererRef.current = new kakao.maps.MarkerClusterer({
          map: mapRef.current,
          averageCenter: true,
        });

        // 반응형 레이아웃에서 지도 컨테이너의 최종 크기가 지도 생성 이후에
        // 확정되면(예: 모바일에서 위쪽 카드 높이가 나중에 정해짐) 카카오맵이
        // 잘못된 크기로 굳어 검은 화면만 보일 수 있다 — 크기가 바뀔 때마다
        // relayout을 호출해 항상 컨테이너에 맞춰 다시 그리게 한다.
        resizeObserver = new ResizeObserver(() => {
          mapRef.current?.relayout();
        });
        resizeObserver.observe(containerRef.current);
      })
      .catch(() => {
        if (cancelled) return;
        setLoadError(true);
      });
    return () => {
      cancelled = true;
      resizeObserver?.disconnect();
    };
    // 최초 마운트 시 한 번만 지도를 생성한다 — 이후 center 변경은 아래 별도 effect가 panTo로 처리한다.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    if (!mapRef.current || !kakaoRef.current || !center) return;
    mapRef.current.panTo(new kakaoRef.current.maps.LatLng(center.lat, center.lng));
  }, [center]);

  useEffect(() => {
    const kakao = kakaoRef.current;
    const map = mapRef.current;
    if (!kakao || !map) return;

    if (polylineRef.current) {
      polylineRef.current.setMap(null);
      polylineRef.current = null;
    }
    if (route.length > 0) {
      const path = route.map((p) => new kakao.maps.LatLng(p.lat, p.lng));
      polylineRef.current = new kakao.maps.Polyline({
        path,
      strokeWeight: 5,
      strokeColor: "#FF7A1A",
        strokeOpacity: 0.85,
      });
      polylineRef.current.setMap(map);
    }
  }, [route]);

  useEffect(() => {
    const kakao = kakaoRef.current;
    const map = mapRef.current;
    if (!kakao || !map) return;

    if (infoWindowRef.current) {
      infoWindowRef.current.setMap(null);
      infoWindowRef.current = null;
    }

    clustererRef.current?.clear();
    markersRef.current.forEach((marker) => marker.setMap(null));
    markersRef.current.clear();
    markerMetaRef.current.clear();

    const markersToCluster: any[] = [];

    restaurants.forEach((restaurant, index) => {
      const broadcastName = pickBroadcastName(restaurant, activeBroadcast);
      const { color, letter } = getBroadcastColor(broadcastName ?? "");
      markerMetaRef.current.set(restaurant.id, { color, letter });
      const isHighlighted = highlightedIdRef.current === restaurant.id;
      const size = isHighlighted ? MARKER_SIZE_HIGHLIGHTED : MARKER_SIZE;
      const markerImage = new kakao.maps.MarkerImage(
        markerImageDataUrl(color, letter, isHighlighted),
        new kakao.maps.Size(size, size),
        { offset: new kakao.maps.Point(size / 2, size / 2) }
      );
      const marker = new kakao.maps.Marker({
        position: new kakao.maps.LatLng(restaurant.latitude, restaurant.longitude),
        image: markerImage,
        map: enableClustering ? null : map,
      });
      if (enableClustering) {
        markersToCluster.push(marker);
      }
      kakao.maps.event.addListener(marker, "click", () => {
        if (infoWindowRef.current) {
          infoWindowRef.current.setMap(null);
        }
        const broadcastLabel = `<span style="color:${color};">${escapeHtml(broadcastName ?? "방송 맛집")}</span>`;
        const topLine = hasRouteInfo(restaurant)
          ? `<span style="color:#78716c;">${index + 1}번째 STOP · </span>${broadcastLabel}`
          : broadcastLabel;
        const bottomLine = hasRouteInfo(restaurant)
          ? `출발 후 ${formatDuration(restaurant.cumulative_time_sec)} · 경로에서 ${restaurant.distance_from_route_km.toFixed(1)}km`
          : "";
        const detailButton = `<button type="button" onclick="window.__foodmapShowDetail && window.__foodmapShowDetail('${restaurant.id}')" style="margin-top:6px;padding:4px 10px;border-radius:9999px;border:1px solid #ff7a1a;background:transparent;color:#ff7a1a;font-family:'Pretendard Variable',Pretendard,sans-serif;font-size:12px;font-weight:700;cursor:pointer;">자세히 보기</button>`;
        // 카카오 InfoWindow는 자체 말풍선 배경(스킨)을 콘텐츠와 별도로 측정해서
        // 그리는데, 폰트 로딩 타이밍에 따라 실제 콘텐츠 높이와 어긋나 텍스트가
        // 흰 박스 밖으로 잘리는 버그가 반복됐다 — CustomOverlay는 우리가 만든
        // div 자체가 배경이라 이런 불일치가 구조적으로 생길 수 없다.
        infoWindowRef.current = new kakao.maps.CustomOverlay({
          position: new kakao.maps.LatLng(restaurant.latitude, restaurant.longitude),
          xAnchor: 0.5,
          yAnchor: 1.25,
          content: `<div style="box-sizing:border-box;width:210px;padding:10px 12px;background:#ffffff;border-radius:12px;box-shadow:0 6px 20px rgba(0,0,0,0.2);font-family:'Pretendard Variable',Pretendard,sans-serif;overflow-wrap:break-word;word-break:break-word;">
            <div style="font-size:12px;font-weight:700;">${topLine}</div>
            <div style="margin-top:3px;font-size:14px;font-weight:700;color:#1c1917;line-height:1.35;">${escapeHtml(restaurant.name)}</div>
            ${bottomLine ? `<div style="margin-top:3px;font-size:12px;color:#78716c;">${bottomLine}</div>` : ""}
            ${detailButton}
          </div>`,
        });
        infoWindowRef.current.setMap(map);
        onMarkerClickRef.current?.(restaurant.id);
      });
      markersRef.current.set(restaurant.id, marker);
    });

    if (enableClustering && markersToCluster.length > 0) {
      clustererRef.current?.addMarkers(markersToCluster);
    }
  }, [restaurants, activeBroadcast, enableClustering]);

  // 마커 수천 개를 다시 만들지 않고, 이전/새 강조 마커 두 개의 이미지만 교체한다.
  useEffect(() => {
    const kakao = kakaoRef.current;
    const map = mapRef.current;
    if (!kakao || !map) return;

    const previousId = highlightedIdRef.current;
    if (previousId && previousId !== highlightedRestaurantId) {
      const prevMarker = markersRef.current.get(previousId);
      const meta = markerMetaRef.current.get(previousId);
      if (prevMarker && meta) {
        prevMarker.setImage(
          new kakao.maps.MarkerImage(
            markerImageDataUrl(meta.color, meta.letter, false),
            new kakao.maps.Size(MARKER_SIZE, MARKER_SIZE),
            { offset: new kakao.maps.Point(MARKER_SIZE / 2, MARKER_SIZE / 2) }
          )
        );
      }
    }

    highlightedIdRef.current = highlightedRestaurantId;
    if (!highlightedRestaurantId) return;

    const marker = markersRef.current.get(highlightedRestaurantId);
    const meta = markerMetaRef.current.get(highlightedRestaurantId);
    if (!marker || !meta) return;

    marker.setImage(
      new kakao.maps.MarkerImage(
        markerImageDataUrl(meta.color, meta.letter, true),
        new kakao.maps.Size(MARKER_SIZE_HIGHLIGHTED, MARKER_SIZE_HIGHLIGHTED),
        { offset: new kakao.maps.Point(MARKER_SIZE_HIGHLIGHTED / 2, MARKER_SIZE_HIGHLIGHTED / 2) }
      )
    );
    map.panTo(marker.getPosition());
  }, [highlightedRestaurantId]);

  if (loadError) {
    return (
      <div className="flex h-full min-h-[400px] w-full items-center justify-center rounded-2xl border border-line bg-surface text-sm text-ink-muted sm:rounded-none sm:border-0">
        지도를 불러오지 못했습니다
      </div>
    );
  }

  return (
    <div className="relative h-full min-h-[400px] w-full overflow-hidden rounded-2xl border border-line shadow-sm shadow-black/5 sm:rounded-none sm:border-0 sm:shadow-none">
      {/* h-full(%)은 min-height로만 크기가 잡힌 부모에서는 0으로 무너질 수 있어
          absolute inset-0으로 부모의 실제 렌더링 박스를 그대로 채운다. */}
      <div ref={containerRef} className="absolute inset-0" />
    </div>
  );
}
