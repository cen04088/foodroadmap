"use client";

import { BROADCASTS } from "./FilterBar";

export interface MapFilterProps {
  value: string;
  onChange: (broadcast: string) => void;
}

function FilterIcon() {
  return (
    <svg viewBox="0 0 20 20" fill="none" className="h-4 w-4 shrink-0 text-[#ffb45a]" aria-hidden="true">
      <path d="M3 4h14M6 10h8M8.5 16h3" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" />
    </svg>
  );
}

export default function MapFilter({ value, onChange }: MapFilterProps) {
  return (
    <div className="pointer-events-auto flex items-center gap-2 rounded-xl border border-white/10 bg-[#171310]/95 px-3 py-2 shadow-xl shadow-black/30 backdrop-blur-xl">
      <FilterIcon />
      <div className="relative">
        <select
          value={value}
          onChange={(e) => onChange(e.target.value)}
          className="w-[150px] appearance-none rounded-lg bg-transparent py-1 pr-6 text-sm font-medium text-[#fff7ed] outline-none"
        >
          {BROADCASTS.map((b) => (
            <option key={b.value} value={b.value} style={{ backgroundColor: "#29201a", color: "#fff7ed" }}>
              {b.label}
            </option>
          ))}
        </select>
        <svg
          viewBox="0 0 20 20"
          fill="none"
          className="pointer-events-none absolute right-0 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-[#a89c91]"
          aria-hidden="true"
        >
          <path d="M5 7.5L10 12.5L15 7.5" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
      </div>
    </div>
  );
}
