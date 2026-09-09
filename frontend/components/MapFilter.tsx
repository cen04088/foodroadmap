"use client";

import BroadcastDropdown from "./BroadcastDropdown";
import { PriceBucketPills } from "./FilterBar";

export interface MapFilterProps {
  value: string;
  onChange: (broadcast: string) => void;
  priceBucket: string;
  onPriceBucketChange: (value: string) => void;
}

function FilterIcon() {
  return (
    <svg viewBox="0 0 20 20" fill="none" className="h-4 w-4 shrink-0 text-[#ffb45a]" aria-hidden="true">
      <path d="M3 4h14M6 10h8M8.5 16h3" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" />
    </svg>
  );
}

export default function MapFilter({
  value,
  onChange,
  priceBucket,
  onPriceBucketChange,
}: MapFilterProps) {
  return (
    <div className="pointer-events-auto flex flex-col gap-2 rounded-xl border border-white/10 bg-[#171310]/95 px-3 py-2 shadow-xl shadow-black/30 backdrop-blur-xl">
      <div className="flex items-center gap-2">
        <FilterIcon />
        <BroadcastDropdown
          value={value}
          onChange={onChange}
          triggerClassName="flex w-[150px] items-center justify-between gap-2 border-0 bg-transparent py-1 text-sm font-medium text-[#fff7ed]"
          chevronClassName="h-3.5 w-3.5 text-[#a89c91]"
          listClassName="right-0 w-[180px]"
        />
      </div>
      {/* 브라우즈 모드의 가격 필터는 서버 쿼리로 나간다 — 경로 모드처럼 이미 받아둔
          결과를 거르는 게 아니라, 지도 영역 안에서 조건에 맞는 가게만 새로 불러온다. */}
      <PriceBucketPills value={priceBucket} onChange={onPriceBucketChange} />
    </div>
  );
}
