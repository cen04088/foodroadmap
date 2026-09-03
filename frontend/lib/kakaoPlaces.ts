export interface PlaceResult {
  name: string;
  address: string;
  lat: number;
  lng: number;
}

export function searchPlaces(kakao: any, keyword: string): Promise<PlaceResult[]> {
  return new Promise((resolve, reject) => {
    const places = new kakao.maps.services.Places();
    places.keywordSearch(keyword, (data: any[], status: string) => {
      if (status === kakao.maps.services.Status.OK) {
        resolve(
          data.map((item) => ({
            name: item.place_name,
            address: item.road_address_name || item.address_name,
            lat: Number(item.y),
            lng: Number(item.x),
          }))
        );
        return;
      }
      if (status === kakao.maps.services.Status.ZERO_RESULT) {
        resolve([]);
        return;
      }
      reject(new Error("장소 검색에 실패했습니다"));
    });
  });
}
