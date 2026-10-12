import type { KakaoAddress, KakaoPlace, KakaoSdk } from "../types/kakao";

export interface PlaceResult {
  name: string;
  address: string;
  lat: number;
  lng: number;
}

// 키워드 검색은 상호·명소(POI)만 찾는다 — 집 주소("테헤란로 212", "역삼동 123-45")는 POI가 없어
// 결과가 0건이다. 주소 검색을 함께 돌려 주소로 찾은 지점을 앞에 붙이고, 한쪽이 실패해도 다른 쪽 결과는 보여준다.
export async function searchPlaces(kakao: KakaoSdk, keyword: string): Promise<PlaceResult[]> {
  const [addresses, places] = await Promise.allSettled([searchAddress(kakao, keyword), searchKeyword(kakao, keyword)]);
  if (addresses.status === "rejected" && places.status === "rejected") {
    throw new Error("장소 검색에 실패했습니다");
  }

  const merged = [
    ...(addresses.status === "fulfilled" ? addresses.value : []),
    ...(places.status === "fulfilled" ? places.value : []),
  ];
  const seen = new Set<string>();
  return merged.filter((place) => {
    if (!Number.isFinite(place.lat) || !Number.isFinite(place.lng)) return false;
    const key = `${place.lat}-${place.lng}-${place.name}`;
    if (seen.has(key)) return false;
    seen.add(key);
    return true;
  });
}

function searchKeyword(kakao: KakaoSdk, keyword: string): Promise<PlaceResult[]> {
  return new Promise((resolve, reject) => {
    const places = new kakao.maps.services.Places();
    places.keywordSearch(keyword, (data, status) => {
      if (status === kakao.maps.services.Status.OK) {
        resolve(data.map(fromPlace));
        return;
      }
      if (status === kakao.maps.services.Status.ZERO_RESULT) {
        resolve([]);
        return;
      }
      reject(new Error("키워드 검색에 실패했습니다"));
    });
  });
}

function searchAddress(kakao: KakaoSdk, query: string): Promise<PlaceResult[]> {
  return new Promise((resolve, reject) => {
    const geocoder = new kakao.maps.services.Geocoder();
    geocoder.addressSearch(query, (data, status) => {
      if (status === kakao.maps.services.Status.OK) {
        resolve(data.map(fromAddress));
        return;
      }
      if (status === kakao.maps.services.Status.ZERO_RESULT) {
        resolve([]);
        return;
      }
      reject(new Error("주소 검색에 실패했습니다"));
    });
  });
}

function fromPlace(item: KakaoPlace): PlaceResult {
  return {
    name: item.place_name,
    address: item.road_address_name || item.address_name,
    lat: Number(item.y),
    lng: Number(item.x),
  };
}

// 입력창에는 도로명 주소를 이름으로 보여주고, 아래 줄에는 건물명이나 지번 주소를 덧붙여 같은 지점인지 확인하게 한다.
function fromAddress(item: KakaoAddress): PlaceResult {
  const road = item.road_address?.address_name;
  const jibun = item.address?.address_name;
  const name = road || jibun || item.address_name;
  const detail = item.road_address?.building_name || (road && jibun) || "";
  return {
    name,
    address: detail && detail !== name ? detail : "주소",
    lat: Number(item.y),
    lng: Number(item.x),
  };
}
