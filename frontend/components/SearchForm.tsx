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

  return (
    <div className="relative flex-1">
      <input
        type="text"
        value={query}
        onChange={(e) => handleQueryChange(e.target.value)}
        placeholder={label}
        className="w-full rounded border border-gray-300 px-3 py-2"
      />
      {suggestions.length > 0 && (
        <ul className="absolute z-10 mt-1 w-full rounded border border-gray-200 bg-white shadow-lg">
          {suggestions.map((s) => (
            <li key={`${s.lat}-${s.lng}-${s.name}`}>
              <button
                type="button"
                onClick={() => handleSelect(s)}
                className="block w-full px-3 py-2 text-left hover:bg-gray-100"
              >
                <div className="font-medium">{s.name}</div>
                <div className="text-sm text-gray-500">{s.address}</div>
              </button>
            </li>
          ))}
        </ul>
      )}
      {query && hasSearched && suggestions.length === 0 && !selected && (
        <div className="absolute z-10 mt-1 w-full rounded border border-gray-200 bg-white px-3 py-2 text-sm text-gray-500 shadow-lg">
          검색 결과가 없어요
        </div>
      )}
      {sdkError && (
        <div className="absolute z-10 mt-1 w-full rounded border border-gray-200 bg-white px-3 py-2 text-sm text-gray-500 shadow-lg">
          장소 검색을 사용할 수 없어요
        </div>
      )}
    </div>
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
    <div className="flex flex-col gap-2 sm:flex-row">
      <PlaceInput label="출발지" onSelect={handleOriginSelect} />
      <PlaceInput label="도착지" onSelect={setDestination} />
      <button
        type="button"
        disabled={!origin || !destination || isLoading}
        onClick={handleSubmit}
        className="rounded bg-blue-600 px-4 py-2 text-white disabled:bg-gray-300"
      >
        {isLoading ? "검색 중..." : "검색"}
      </button>
    </div>
  );
}
