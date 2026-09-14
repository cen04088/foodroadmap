// The SDK surface used by this app. Keep external data typed at the boundary.
export interface KakaoLatLng {
  getLat(): number;
  getLng(): number;
}

export interface KakaoMap {
  getBounds(): { getSouthWest(): KakaoLatLng; getNorthEast(): KakaoLatLng };
  panTo(position: KakaoLatLng): void;
  relayout(): void;
}

export interface KakaoOverlay { setMap(map: KakaoMap | null): void }
export interface KakaoMarker extends KakaoOverlay {
  setImage(image: object): void;
  getPosition(): KakaoLatLng;
}

export interface KakaoPlace {
  place_name: string;
  road_address_name: string;
  address_name: string;
  x: string;
  y: string;
}

export interface KakaoSdk {
  maps: {
    load(callback: () => void): void;
    LatLng: new (lat: number, lng: number) => KakaoLatLng;
    Map: new (element: HTMLElement, options: { center: KakaoLatLng; level: number }) => KakaoMap;
    Size: new (width: number, height: number) => object;
    Point: new (x: number, y: number) => object;
    MarkerImage: new (src: string, size: object, options: { offset: object }) => object;
    Marker: new (options: { position: KakaoLatLng; image: object; map: KakaoMap }) => KakaoMarker;
    Polyline: new (options: { path: KakaoLatLng[]; strokeWeight: number; strokeColor: string; strokeOpacity: number }) => KakaoOverlay;
    CustomOverlay: new (options: { position: KakaoLatLng; xAnchor: number; yAnchor: number; content: string }) => KakaoOverlay;
    event: { addListener(target: KakaoMap | KakaoMarker, type: string, callback: () => void): void };
    services: {
      Places: new () => { keywordSearch(keyword: string, callback: (data: KakaoPlace[], status: string) => void): void };
      Status: { OK: string; ZERO_RESULT: string };
    };
  };
}

declare global {
  interface Window {
    kakao?: KakaoSdk;
    __foodmapShowDetail?: (id: string) => void;
    __foodmapCloseOverlay?: () => void;
    __foodmapToggleFavorite?: (id: string) => void;
  }
}
