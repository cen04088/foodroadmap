"use client";

export interface Filters {
  broadcast: string;
  category: string;
}

export const BROADCASTS: { value: string; label: string }[] = [
  { value: "", label: "전체" },
  { value: "또간집", label: "또간집" },
  { value: "흑백요리사", label: "흑백요리사" },
  { value: "쯔양", label: "쯔양" },
  { value: "먹을텐데", label: "먹을텐데" },
  { value: "전현무계획", label: "전현무계획" },
  { value: "허영만의 백반기행", label: "허영만의 백반기행" },
  { value: "한국인의 밥상", label: "한국인의 밥상" },
  { value: "맛있는 녀석들", label: "맛있는 녀석들" },
  { value: "동네한바퀴", label: "동네한바퀴" },
  { value: "백년가게", label: "백년가게" },
  { value: "비밀이야", label: "비밀이야" },
  { value: "공간 탐닉", label: "공간 탐닉" },
  { value: "김사원세끼", label: "김사원세끼" },
];

export interface FilterBarProps {
  filters: Filters;
  onChange: (filters: Filters) => void;
}

export default function FilterBar({ filters, onChange }: FilterBarProps) {
  return (
    <div className="flex flex-col gap-2 sm:flex-row">
      <div className="relative flex-1 sm:max-w-[220px]">
        <select
          value={filters.broadcast}
          onChange={(e) => onChange({ ...filters, broadcast: e.target.value })}
          className="w-full appearance-none rounded-xl border border-line bg-surface px-4 py-2.5 text-sm text-ink outline-none transition focus:border-accent focus:ring-4 focus:ring-accent-soft"
        >
          {BROADCASTS.map((b) => (
            <option key={b.value} value={b.value} style={{ backgroundColor: "var(--surface)", color: "var(--ink)" }}>
              {b.label}
            </option>
          ))}
        </select>
        <svg
          viewBox="0 0 20 20"
          fill="none"
          className="pointer-events-none absolute right-3 top-1/2 h-4 w-4 -translate-y-1/2 text-ink-muted"
          aria-hidden="true"
        >
          <path d="M5 7.5L10 12.5L15 7.5" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
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
