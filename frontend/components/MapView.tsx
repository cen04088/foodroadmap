"use client";

import { useEffect, useRef } from "react";
import { loadKakaoMapsSdk } from "../lib/kakaoMap";
import type { RestaurantResult, RoutePoint } from "../lib/api";

const DEFAULT_CENTER = { lat: 37.5665, lng: 126.978 }; // 서울시청

export interface MapViewProps {
  route: RoutePoint[];
  restaurants: RestaurantResult[];
  highlightedRestaurantId: string | null;
  center: { lat: number; lng: number } | null;
}

export default function MapView({ route, restaurants, highlightedRestaurantId, center }: MapViewProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<any>(null);
  const kakaoRef = useRef<any>(null);
  const polylineRef = useRef<any>(null);
  const markersRef = useRef<Map<string, any>>(new Map());
  const infoWindowRef = useRef<any>(null);

  useEffect(() => {
    let cancelled = false;
    loadKakaoMapsSdk().then((kakao) => {
      if (cancelled || !containerRef.current) return;
      kakaoRef.current = kakao;
      const initialCenter = center ?? DEFAULT_CENTER;
      mapRef.current = new kakao.maps.Map(containerRef.current, {
        center: new kakao.maps.LatLng(initialCenter.lat, initialCenter.lng),
        level: 6,
      });
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
        strokeWeight: 4,
        strokeColor: "#2563eb",
        strokeOpacity: 0.8,
      });
      polylineRef.current.setMap(map);
    }
  }, [route]);

  useEffect(() => {
    const kakao = kakaoRef.current;
    const map = mapRef.current;
    if (!kakao || !map) return;

    markersRef.current.forEach((marker) => marker.setMap(null));
    markersRef.current.clear();

    restaurants.forEach((restaurant) => {
      const marker = new kakao.maps.Marker({
        position: new kakao.maps.LatLng(restaurant.latitude, restaurant.longitude),
        map,
      });
      kakao.maps.event.addListener(marker, "click", () => {
        if (infoWindowRef.current) {
          infoWindowRef.current.close();
        }
        infoWindowRef.current = new kakao.maps.InfoWindow({
          content: `<div style="padding:8px;font-size:13px;">
            <strong>${restaurant.name}</strong><br/>
            ${restaurant.distance_from_route_km.toFixed(1)}km · ${Math.floor(restaurant.cumulative_time_sec / 60)}분 지점
          </div>`,
        });
        infoWindowRef.current.open(map, marker);
      });
      markersRef.current.set(restaurant.id, marker);
    });
  }, [restaurants]);

  useEffect(() => {
    if (!highlightedRestaurantId) return;
    const marker = markersRef.current.get(highlightedRestaurantId);
    const map = mapRef.current;
    if (!marker || !map) return;
    map.panTo(marker.getPosition());
  }, [highlightedRestaurantId]);

  return <div ref={containerRef} className="h-full min-h-[400px] w-full rounded" />;
}
