"use client";

import { useEffect, useRef, useState } from "react";
import { loadKakaoMapsSdk } from "../lib/kakaoMap";
import type { RestaurantResult, RoutePoint } from "../lib/api";
import { formatDuration } from "../lib/format";
import { getBroadcastColor } from "../lib/broadcastColors";

const DEFAULT_CENTER = { lat: 37.5665, lng: 126.978 }; // 서울시청
const MARKER_WIDTH = 46;
const MARKER_HEIGHT = 54;

function escapeHtml(value: string): string {
  return value
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}

// 활성 방송 필터에 해당하는 방송이 있으면 그 방송, 없으면 첫 번째 방송 기준으로 마커 색을 정한다.
function pickBroadcastName(restaurant: RestaurantResult, activeBroadcast: string | null): string | null {
  if (activeBroadcast && restaurant.broadcasts.includes(activeBroadcast)) {
    return activeBroadcast;
  }
  return restaurant.broadcasts[0] ?? null;
}

function markerImageDataUrl(color: string, order: number, isHighlighted: boolean): string {
  const ring = isHighlighted ? "#FFB45A" : color;
  const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="${MARKER_WIDTH}" height="${MARKER_HEIGHT}" viewBox="0 0 ${MARKER_WIDTH} ${MARKER_HEIGHT}"><path d="M23 51C23 51 6 34 6 21a17 17 0 1 1 34 0c0 13-17 30-17 30Z" fill="#FF7A1A" stroke="${ring}" stroke-width="3"/><circle cx="23" cy="21" r="11" fill="#171310"/><text x="23" y="26" font-family="Pretendard, sans-serif" font-size="14" font-weight="800" fill="#FFF7ED" text-anchor="middle">${order}</text></svg>`;
  return `data:image/svg+xml;charset=UTF-8,${encodeURIComponent(svg)}`;
}

export interface MapViewProps {
  route: RoutePoint[];
  restaurants: RestaurantResult[];
  highlightedRestaurantId: string | null;
  center: { lat: number; lng: number } | null;
  activeBroadcast?: string | null;
  onMarkerClick?: (id: string) => void;
}

export default function MapView({
  route,
  restaurants,
  highlightedRestaurantId,
  center,
  activeBroadcast = null,
  onMarkerClick,
}: MapViewProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<any>(null);
  const kakaoRef = useRef<any>(null);
  const polylineRef = useRef<any>(null);
  const markersRef = useRef<Map<string, any>>(new Map());
  const infoWindowRef = useRef<any>(null);
  const centerRef = useRef(center);
  const onMarkerClickRef = useRef(onMarkerClick);
  const [loadError, setLoadError] = useState(false);

  useEffect(() => {
    centerRef.current = center;
  }, [center]);

  useEffect(() => {
    onMarkerClickRef.current = onMarkerClick;
  }, [onMarkerClick]);

  useEffect(() => {
    let cancelled = false;
    loadKakaoMapsSdk()
      .then((kakao) => {
        if (cancelled || !containerRef.current) return;
        kakaoRef.current = kakao;
        const initialCenter = centerRef.current ?? DEFAULT_CENTER;
        mapRef.current = new kakao.maps.Map(containerRef.current, {
          center: new kakao.maps.LatLng(initialCenter.lat, initialCenter.lng),
          level: 6,
        });
      })
      .catch(() => {
        if (cancelled) return;
        setLoadError(true);
      });
    return () => {
      cancelled = true;
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
      infoWindowRef.current.close();
      infoWindowRef.current = null;
    }

    markersRef.current.forEach((marker) => marker.setMap(null));
    markersRef.current.clear();

    restaurants.forEach((restaurant, index) => {
      const broadcastName = pickBroadcastName(restaurant, activeBroadcast);
      const { color } = getBroadcastColor(broadcastName ?? "");
      const markerImage = new kakao.maps.MarkerImage(
        markerImageDataUrl(color, index + 1, highlightedRestaurantId === restaurant.id),
        new kakao.maps.Size(MARKER_WIDTH, MARKER_HEIGHT),
        { offset: new kakao.maps.Point(MARKER_WIDTH / 2, MARKER_HEIGHT) }
      );
      const marker = new kakao.maps.Marker({
        position: new kakao.maps.LatLng(restaurant.latitude, restaurant.longitude),
        image: markerImage,
        map,
      });
      kakao.maps.event.addListener(marker, "click", () => {
        if (infoWindowRef.current) {
          infoWindowRef.current.close();
        }
        infoWindowRef.current = new kakao.maps.InfoWindow({
          content: `<div style="padding:10px 12px;font-family:'Pretendard Variable',Pretendard,sans-serif;min-width:120px;">
            <div style="font-size:12px;font-weight:700;color:#ff7a1a;">${index + 1}번째 STOP · ${escapeHtml(broadcastName ?? "방송 맛집")}</div>
            <div style="margin-top:3px;font-size:14px;font-weight:700;color:#1c1917;">${escapeHtml(restaurant.name)}</div>
            <div style="margin-top:3px;font-size:12px;color:#78716c;">출발 후 ${formatDuration(restaurant.cumulative_time_sec)} · 경로에서 ${restaurant.distance_from_route_km.toFixed(1)}km</div>
          </div>`,
        });
        infoWindowRef.current.open(map, marker);
        onMarkerClickRef.current?.(restaurant.id);
      });
      markersRef.current.set(restaurant.id, marker);
    });
  }, [restaurants, activeBroadcast, highlightedRestaurantId]);

  useEffect(() => {
    if (!highlightedRestaurantId) return;
    const marker = markersRef.current.get(highlightedRestaurantId);
    const map = mapRef.current;
    if (!marker || !map) return;
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
    <div className="h-full min-h-[400px] w-full overflow-hidden rounded-2xl border border-line shadow-sm shadow-black/5 sm:rounded-none sm:border-0 sm:shadow-none">
      <div ref={containerRef} className="h-full w-full" />
    </div>
  );
}
