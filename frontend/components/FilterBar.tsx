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
  { value: "쯔양 몇끼", label: "쯔양 몇끼" },
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
      <select
        value={filters.broadcast}
        onChange={(e) => onChange({ ...filters, broadcast: e.target.value })}
        className="rounded border border-gray-300 px-3 py-2"
      >
        {BROADCASTS.map((b) => (
          <option key={b.value} value={b.value}>
            {b.label}
          </option>
        ))}
      </select>
      <input
        type="text"
        value={filters.category}
        onChange={(e) => onChange({ ...filters, category: e.target.value })}
        placeholder="업종 (예: 한식, 일식)"
        className="rounded border border-gray-300 px-3 py-2"
      />
    </div>
  );
}
