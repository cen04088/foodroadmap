import { describe, expect, it } from "vitest";
import type { KakaoAddress, KakaoPlace, KakaoSdk } from "../types/kakao";
import { searchPlaces } from "./kakaoPlaces";

const OK = "OK";
const ZERO_RESULT = "ZERO_RESULT";
const ERROR = "ERROR";

type Reply<T> = { data: T[]; status: string };

function fakeSdk(keyword: Reply<KakaoPlace>, address: Reply<KakaoAddress>): KakaoSdk {
  return {
    maps: {
      services: {
        Places: class {
          keywordSearch(_: string, callback: (data: KakaoPlace[], status: string) => void) {
            callback(keyword.data, keyword.status);
          }
        },
        Geocoder: class {
          addressSearch(_: string, callback: (data: KakaoAddress[], status: string) => void) {
            callback(address.data, address.status);
          }
        },
        Status: { OK, ZERO_RESULT },
      },
    },
  } as unknown as KakaoSdk;
}

const station: KakaoPlace = {
  place_name: "서울역",
  road_address_name: "서울 중구 한강대로 405",
  address_name: "서울 중구 봉래동2가 122",
  x: "126.9707",
  y: "37.5547",
};

const home: KakaoAddress = {
  address_name: "서울 강남구 테헤란로 212",
  x: "127.0396",
  y: "37.5013",
  road_address: { address_name: "서울 강남구 테헤란로 212", building_name: "멀티캠퍼스" },
  address: { address_name: "서울 강남구 역삼동 718-5" },
};

describe("searchPlaces", () => {
  it("finds a home address that keyword search misses", async () => {
    const results = await searchPlaces(fakeSdk({ data: [], status: ZERO_RESULT }, { data: [home], status: OK }), "테헤란로 212");
    expect(results).toEqual([{ name: "서울 강남구 테헤란로 212", address: "멀티캠퍼스", lat: 37.5013, lng: 127.0396 }]);
  });

  it("lists address matches before keyword matches", async () => {
    const results = await searchPlaces(fakeSdk({ data: [station], status: OK }, { data: [home], status: OK }), "q");
    expect(results.map((r) => r.name)).toEqual(["서울 강남구 테헤란로 212", "서울역"]);
  });

  it("falls back to the jibun address when there is no building name", async () => {
    const noBuilding: KakaoAddress = { ...home, road_address: { address_name: "서울 강남구 테헤란로 212", building_name: "" } };
    const [result] = await searchPlaces(fakeSdk({ data: [], status: ZERO_RESULT }, { data: [noBuilding], status: OK }), "q");
    expect(result.address).toBe("서울 강남구 역삼동 718-5");
  });

  it("uses the jibun address as the name when there is no road address", async () => {
    const jibunOnly: KakaoAddress = { ...home, address_name: "서울 강남구 역삼동 718-5", road_address: null };
    const [result] = await searchPlaces(fakeSdk({ data: [], status: ZERO_RESULT }, { data: [jibunOnly], status: OK }), "q");
    expect(result).toMatchObject({ name: "서울 강남구 역삼동 718-5", address: "주소" });
  });

  it("keeps keyword results when address search fails", async () => {
    const results = await searchPlaces(fakeSdk({ data: [station], status: OK }, { data: [], status: ERROR }), "서울역");
    expect(results.map((r) => r.name)).toEqual(["서울역"]);
  });

  it("rejects only when both searches fail", async () => {
    await expect(searchPlaces(fakeSdk({ data: [], status: ERROR }, { data: [], status: ERROR }), "q")).rejects.toThrow();
  });

  it("drops results with unusable coordinates", async () => {
    const broken: KakaoPlace = { ...station, x: "", y: "not-a-number" };
    const results = await searchPlaces(fakeSdk({ data: [broken, station], status: OK }, { data: [], status: ZERO_RESULT }), "q");
    expect(results).toHaveLength(1);
  });
});
