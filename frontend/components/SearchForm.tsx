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
  onOriginSelect?: (place: SelectedPlace) => void;
  onSearch: (origin: SelectedPlace, destination: SelectedPlace) => void;
  isLoading: boolean;
}

function PlaceInput({
  label,
  onSelect,
}: {
  label: string;
  onSelect: (place: SelectedPlace | null) => void;
}) {
  const [query, setQuery] = useState("");
  const [suggestions, setSuggestions] = useState<PlaceResult[]>([]);
  const [selected, setSelected] = useState<SelectedPlace | null>(null);
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
    <div className="relative flex-1">
      <input
        type="text"
        value={query}
        onChange={(e) => handleQueryChange(e.target.value)}
        placeholder={label}
        disabled={sdkError}
        className="w-full rounded-xl border border-line bg-surface px-4 py-3 text-[15px] text-ink placeholder:text-ink-muted outline-none transition focus:border-accent focus:ring-4 focus:ring-accent-soft disabled:bg-surface-hover disabled:text-ink-muted"
      />
      {sdkError && <p className="mt-1.5 text-xs text-ink-muted">장소 검색을 사용할 수 없어요</p>}
      {showDropdown && (
        <div className="absolute z-10 mt-2 w-full overflow-hidden rounded-xl border border-line bg-surface shadow-lg shadow-black/5">
          {suggestions.length > 0 ? (
            <ul>
              {suggestions.map((s) => (
                <li key={`${s.lat}-${s.lng}-${s.name}`}>
                  <button
                    type="button"
                    onClick={() => handleSelect(s)}
                    className="block w-full px-4 py-3 text-left transition hover:bg-surface-hover"
                  >
                    <div className="text-[15px] font-medium text-ink">{s.name}</div>
                    <div className="text-sm text-ink-muted">{s.address}</div>
                  </button>
                </li>
              ))}
            </ul>
          ) : (
            <p className="px-4 py-3 text-sm text-ink-muted">검색 결과가 없어요</p>
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

export default function SearchForm({ onOriginSelect, onSearch, isLoading }: SearchFormProps) {
  const [origin, setOrigin] = useState<SelectedPlace | null>(null);
  const [destination, setDestination] = useState<SelectedPlace | null>(null);

  function handleOriginSelect(place: SelectedPlace | null) {
    setOrigin(place);
    if (place) {
      onOriginSelect?.(place);
    }
  }

  function handleSubmit() {
    if (origin && destination) {
      onSearch(origin, destination);
    }
  }

  return (
    <div className="flex flex-col gap-3 sm:flex-row sm:items-start">
      <div className="flex flex-1 flex-col gap-2 sm:flex-row sm:items-center">
        <PlaceInput label="출발지" onSelect={handleOriginSelect} />
        <span className="hidden shrink-0 text-ink-muted sm:block" aria-hidden="true">
          →
        </span>
        <PlaceInput label="도착지" onSelect={setDestination} />
      </div>
      <button
        type="button"
        disabled={!origin || !destination || isLoading}
        onClick={handleSubmit}
        className="flex shrink-0 items-center justify-center gap-2 rounded-xl bg-accent px-6 py-3 text-[15px] font-semibold text-white transition hover:bg-accent-hover disabled:cursor-not-allowed disabled:bg-line disabled:text-ink-muted"
      >
        {isLoading ? <Spinner /> : <SearchIcon />}
        {isLoading ? "검색 중" : "검색"}
      </button>
    </div>
  );
}
