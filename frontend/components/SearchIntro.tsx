"use client";

import { useEffect, useState } from "react";
import { fetchBroadcastOverview } from "../lib/api";
import type { SelectedPlace } from "./SearchForm";

// 검색 전 첫 화면의 원탭 예시 경로. 좌표는 역·명소의 대표 지점 고정값이다 — 구간을 바꾸려면 여기만 고친다.
// 심사·투표하는 사람은 어디를 넣을지 몰라 첫 검색 전에 이탈하기 쉬워서, 타이핑 없이 핵심 화면까지 보내는 용도.
export const PRESET_ROUTES: { origin: SelectedPlace; destination: SelectedPlace; hint: string }[] = [
  { origin: { label: "서울역", lat: 37.5547, lng: 126.9707 }, destination: { label: "강릉역", lat: 37.7637, lng: 128.8999 }, hint: "동해안 여행길" },
  { origin: { label: "강남역", lat: 37.4979, lng: 127.0276 }, destination: { label: "속초 해수욕장", lat: 38.1908, lng: 128.6018 }, hint: "설악·속초" },
  { origin: { label: "서울역", lat: 37.5547, lng: 126.9707 }, destination: { label: "전주 한옥마을", lat: 35.8151, lng: 127.1531 }, hint: "호남 맛기행" },
  { origin: { label: "대전역", lat: 36.3315, lng: 127.4346 }, destination: { label: "부산역", lat: 35.1152, lng: 129.0403 }, hint: "경부선 따라" },
];

const STEPS = [
  { title: "출발지와 목적지를 정하세요", body: "가는 길 반경 2km 안의 방송 맛집을 찾아요." },
  { title: "출발 후 N분 순으로 확인", body: "지나가는 순서대로 목록과 지도에 표시돼요." },
  { title: "AI 추천 보기로 조건 말하기", body: "“한 시간 뒤 한식, 2만 원 이하”처럼 물어보세요." },
];

export interface SearchIntroProps {
  onPickRoute: (origin: SelectedPlace, destination: SelectedPlace) => void;
  disabled?: boolean;
}

export default function SearchIntro({ onPickRoute, disabled = false }: SearchIntroProps) {
  const [overview, setOverview] = useState<{ programs: number; restaurants: number } | null>(null);

  useEffect(() => {
    let cancelled = false;
    fetchBroadcastOverview()
      .then((data) => {
        // 백엔드가 아직 이전 버전이면 total_restaurants가 없다 — 그때는 줄 자체를 숨긴다.
        if (cancelled || typeof data.total_restaurants !== "number") return;
        setOverview({ programs: data.broadcasts.length, restaurants: data.total_restaurants });
      })
      .catch(() => {
        // 숫자 한 줄은 없어도 되는 정보다 — 실패하면 조용히 숨긴다.
      });
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    // justify-center 대신 안쪽 래퍼의 my-auto로 가운데 맞춘다 — 세로가 짧은 화면에서 내용이 패널보다 길어지면
    // justify-center는 위아래를 똑같이 잘라 맨 위 라벨이 스크롤로도 닿지 않는 곳으로 밀려난다.
    <section aria-label="시작하기" className="flex min-h-full flex-col px-1 py-2">
      <div className="my-auto flex min-h-[200px] flex-col gap-5 sm:short:gap-3">
      <div>
        <p className="text-[11px] font-bold tracking-[0.15em] text-[#ffb45a]">바로 시작하기</p>
        <h2 className="mt-1 text-base font-bold text-[#fff7ed]">이런 길은 어떠세요?</h2>
        <div className="mt-3 grid grid-cols-2 gap-2">
          {PRESET_ROUTES.map((route) => (
            <button
              key={`${route.origin.label}-${route.destination.label}`}
              type="button"
              disabled={disabled}
              aria-label={`${route.origin.label} → ${route.destination.label} · ${route.hint}`}
              onClick={() => onPickRoute(route.origin, route.destination)}
              className="flex min-w-0 flex-col items-start rounded-xl border border-white/15 bg-white/[0.03] px-3 py-2.5 text-left transition hover:border-[#ffb45a]/60 hover:bg-[#ffb45a]/10 disabled:cursor-not-allowed disabled:opacity-50"
            >
              <span className="block text-xs leading-5 text-[#a89c91]">
                {route.origin.label} <span aria-hidden="true">→</span>
              </span>
              <span className="block break-keep text-sm font-semibold leading-snug text-[#fff7ed]">
                {route.destination.label}
              </span>
              <span className="mt-auto block break-keep pt-1 text-[11px] text-[#a89c91]">{route.hint}</span>
            </button>
          ))}
        </div>
      </div>

      <ol className="space-y-2.5">
        {STEPS.map((step, index) => (
          <li key={step.title} className="flex items-start gap-3">
            <span className="grid h-6 w-6 shrink-0 place-items-center rounded-full bg-[#ffb45a] text-xs font-bold text-[#211a14]">{index + 1}</span>
            <div>
              <p className="text-sm font-semibold text-[#fff7ed]">{step.title}</p>
              <p className="text-xs leading-5 text-[#a89c91]">{step.body}</p>
            </div>
          </li>
        ))}
      </ol>

      {overview && (
        <p className="text-[11px] text-[#a89c91]">
          {overview.programs}개 방송 프로그램 · {overview.restaurants.toLocaleString("ko-KR")}곳, 방송에 나온 곳만 모았어요
        </p>
      )}
      </div>
    </section>
  );
}
