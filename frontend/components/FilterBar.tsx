"use client";

import BroadcastDropdown from "./BroadcastDropdown";
import { BROADCAST_COLORS } from "../lib/broadcastColors";

export interface Filters {
  broadcast: string;
  category: string;
}

// 방송 색 목록이 곧 서비스에 노출하는 방송 목록이다 — 따로 적어두면 새 방송을 추가할 때 필터만 빠진다.
export const BROADCASTS: { value: string; label: string }[] = [
  { value: "", label: "전체" },
  ...Object.keys(BROADCAST_COLORS).map((name) => ({ value: name, label: name })),
];

export interface FilterBarProps {
  filters: Filters;
  onChange: (filters: Filters) => void;
}

export default function FilterBar({ filters, onChange }: FilterBarProps) {
  return (
    <div className="flex flex-col gap-2 sm:flex-row">
      <div className="flex-1 sm:max-w-[220px]">
        <BroadcastDropdown
          value={filters.broadcast}
          onChange={(broadcast) => onChange({ ...filters, broadcast })}
          triggerClassName="flex w-full items-center justify-between gap-2 rounded-xl border border-line bg-surface px-4 py-2.5 text-sm text-ink outline-none transition focus:border-accent focus:ring-4 focus:ring-accent-soft"
          chevronClassName="h-4 w-4 text-ink-muted"
        />
      </div>
      <input
        type="text"
        value={filters.category}
        onChange={(e) => onChange({ ...filters, category: e.target.value })}
        placeholder="업종 (예: 한식, 일식)"
        className="flex-1 rounded-xl border border-line bg-surface px-4 py-2.5 text-sm text-ink placeholder:text-ink-muted outline-none transition focus:border-accent focus:ring-4 focus:ring-accent-soft sm:max-w-[220px]"
      />
    </div>
  );
}
