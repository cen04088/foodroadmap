"use client";

import { useEffect, useRef, useState } from "react";
import { loadKakaoMapsSdk } from "../lib/kakaoMap";
import { searchPlaces, type PlaceResult } from "../lib/kakaoPlaces";

export interface SelectedPlace {
  label: string;
  lat: number;
  lng: number;
}

export interface SearchFormProps {
  // 선택이 풀렸을 때(사용자가 다시 타이핑) null도 올라온다 — 부모가 폼 상태를 그대로
  // 들고 있어야 "저장한 곳 -> 출발지로"로 한쪽만 바꿔 넣어도 나머지가 살아남는다.
  onOriginChange?: (place: SelectedPlace | null) => void;
  onDestinationChange?: (place: SelectedPlace | null) => void;
  onSearch: (origin: SelectedPlace, destination: SelectedPlace) => void;
  isLoading: boolean;
  // 부모가 밖에서 넣어주는 장소("저장한 곳 -> 출발지로" 등). 마운트 시 입력창을 채워두어
  // 사용자가 어떤 경로를 보고 있는지 알 수 있고, 한쪽만 바꿔 다시 검색할 수 있다.
  initialOrigin?: SelectedPlace | null;
  initialDestination?: SelectedPlace | null;
}

function PlaceInput({
  label,
  initialPlace,
  onSelect,
}: {
  label: string;
  initialPlace?: SelectedPlace | null;
  onSelect: (place: SelectedPlace | null) => void;
}) {
  const [query, setQuery] = useState(initialPlace?.label ?? "");
  const [suggestions, setSuggestions] = useState<PlaceResult[]>([]);
  const [selected, setSelected] = useState<SelectedPlace | null>(initialPlace ?? null);
  const [hasSearched, setHasSearched] = useState(false);
  const [sdkError, setSdkError] = useState(false);
  const kakaoRef = useRef<any>(null);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    loadKakaoMapsSdk()
      .then((kakao) => {
        kakaoRef.current = kakao;
      })
      .catch(() => {
        setSdkError(true);
      });
  }, []);

  function handleQueryChange(value: string) {
    setQuery(value);
    setSelected(null);
    onSelect(null);
    setHasSearched(false);

    if (debounceRef.current) {
      clearTimeout(debounceRef.current);
    }

    if (!value.trim() || !kakaoRef.current) {
      setSuggestions([]);
      return;
    }

    debounceRef.current = setTimeout(() => {
      searchPlaces(kakaoRef.current, value)
        .then((results) => {
          setSuggestions(results);
          setHasSearched(true);
        })
        .catch(() => {
          setSuggestions([]);
          setHasSearched(true);
        });
    }, 300);
  }

  function handleSelect(place: PlaceResult) {
    const selectedPlace: SelectedPlace = { label: place.name, lat: place.lat, lng: place.lng };
    setSelected(selectedPlace);
    setQuery(place.name);
    setSuggestions([]);
    onSelect(selectedPlace);
  }

  const showDropdown = !sdkError && (suggestions.length > 0 || (query && hasSearched && !selected));

  return (
    <div className="relative w-full">
      <label className="mb-1.5 block text-sm font-semibold text-[#fff7ed] sm:short:mb-1">{label}</label>
      <input
        type="text"
        value={query}
        onChange={(e) => handleQueryChange(e.target.value)}
        placeholder={label === "어디서 출발하시나요?" ? "예: 서울역" : "예: 헤이리 예술마을"}
        disabled={sdkError}
        className="w-full rounded-xl border border-white/10 bg-[#171310]/80 px-4 py-3 text-base text-[#fff7ed] sm:short:py-2 sm:short:text-sm placeholder:text-[#a89c91] outline-none transition focus:border-[#ff7a1a] focus:ring-4 focus:ring-[#ff7a1a]/15 disabled:bg-[#3a2a1e] disabled:text-[#a89c91]"
      />
      {sdkError && <p className="mt-1.5 text-xs text-ink-muted">장소 검색을 사용할 수 없어요</p>}
      {showDropdown && (
        <div className="absolute z-10 mt-2 w-full overflow-hidden rounded-xl border border-white/10 bg-[#29201a] shadow-lg shadow-black/30">
          {suggestions.length > 0 ? (
            <ul>
              {suggestions.map((s) => (
                <li key={`${s.lat}-${s.lng}-${s.name}`}>
                  <button
                    type="button"
                    onClick={() => handleSelect(s)}
                    className="block w-full px-4 py-3 text-left transition hover:bg-[#3a2a1e]"
                  >
                    <div className="text-[15px] font-medium text-[#fff7ed]">{s.name}</div>
                    <div className="text-sm text-[#a89c91]">{s.address}</div>
                  </button>
                </li>
              ))}
            </ul>
          ) : (
            <p className="px-4 py-3 text-sm text-[#a89c91]">검색 결과가 없어요</p>
          )}
        </div>
      )}
    </div>
  );
}

function SearchIcon() {
  return (
    <svg viewBox="0 0 20 20" fill="none" className="h-4 w-4" aria-hidden="true">
      <circle cx="9" cy="9" r="6" stroke="currentColor" strokeWidth="1.7" />
      <path d="M13.5 13.5L17 17" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" />
    </svg>
  );
}

function Spinner() {
  return (
    <svg viewBox="0 0 20 20" fill="none" className="h-4 w-4 animate-spin" aria-hidden="true">
      <circle cx="10" cy="10" r="8" stroke="currentColor" strokeWidth="2.5" opacity="0.25" />
      <path d="M18 10a8 8 0 0 0-8-8" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" />
    </svg>
  );
}

export default function SearchForm({
  onOriginChange,
  onDestinationChange,
  onSearch,
  isLoading,
  initialOrigin,
  initialDestination,
}: SearchFormProps) {
  const [origin, setOrigin] = useState<SelectedPlace | null>(initialOrigin ?? null);
  const [destination, setDestination] = useState<SelectedPlace | null>(initialDestination ?? null);

  function handleOriginSelect(place: SelectedPlace | null) {
    setOrigin(place);
    onOriginChange?.(place);
  }

  function handleDestinationSelect(place: SelectedPlace | null) {
    setDestination(place);
    onDestinationChange?.(place);
  }

  function handleSubmit() {
    if (origin && destination) {
      onSearch(origin, destination);
    }
  }

  return (
    <div className="flex flex-col gap-2">
      <div className="flex flex-col gap-2">
        <PlaceInput label="어디서 출발하시나요?" initialPlace={initialOrigin} onSelect={handleOriginSelect} />
        <div className="flex items-center gap-3 pl-1 sm:short:hidden" aria-hidden="true">
          <span className="h-4 w-px bg-line" />
          <svg viewBox="0 0 20 20" fill="none" className="h-3.5 w-3.5 text-ink-muted">
            <path d="M10 3v14M10 17l-4-4M10 17l4-4" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
        </div>
        <PlaceInput label="어디까지 가시나요?" initialPlace={initialDestination} onSelect={handleDestinationSelect} />
      </div>
      <button
        type="button"
        disabled={!origin || !destination || isLoading}
        onClick={handleSubmit}
        className="mt-2 flex w-full items-center justify-center gap-2 rounded-xl bg-[#ff7a1a] px-6 py-3.5 text-base font-bold sm:short:mt-1 sm:short:py-2.5 sm:short:text-sm text-[#171310] shadow-[0_8px_28px_-6px_rgba(255,122,26,.45)] transition hover:bg-[#ffb45a] disabled:cursor-not-allowed disabled:bg-[#5c4736] disabled:text-[#a89c91] disabled:shadow-none"
      >
        {isLoading ? <Spinner /> : <SearchIcon />}
        {isLoading ? "경로를 찾는 중" : "경로에서 맛집 찾기"}
      </button>
    </div>
  );
}
