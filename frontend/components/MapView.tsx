"use client";

import { useEffect, useRef, useState } from "react";
import { loadKakaoMapsSdk } from "../lib/kakaoMap";
import type { RestaurantResult, RoutePoint } from "../lib/api";
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

// 활성 방송 필터에 해당하는 방송이 있으면 그 방송, 없으면 첫 번째 방송 기준으로 마커 색을 정한다.
function pickBroadcastName(restaurant: RestaurantResult, activeBroadcast: string | null): string | null {
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
      const { color, letter } = getBroadcastColor(broadcastName ?? "");
      const isHighlighted = highlightedRestaurantId === restaurant.id;
      const size = isHighlighted ? MARKER_SIZE_HIGHLIGHTED : MARKER_SIZE;
      const markerImage = new kakao.maps.MarkerImage(
        markerImageDataUrl(color, letter, isHighlighted),
        new kakao.maps.Size(size, size),
        { offset: new kakao.maps.Point(size / 2, size / 2) }
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
