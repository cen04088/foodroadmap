"use client";

import { useEffect, useRef, useState } from "react";
import { BROADCASTS } from "./FilterBar";

export interface BroadcastDropdownProps {
  value: string;
  onChange: (value: string) => void;
  triggerClassName: string;
  chevronClassName?: string;
  listClassName?: string;
}

function ChevronIcon({ className, isOpen }: { className?: string; isOpen: boolean }) {
  return (
    <svg
      viewBox="0 0 20 20"
      fill="none"
      className={`shrink-0 transition-transform ${isOpen ? "rotate-180" : ""} ${className ?? ""}`}
      aria-hidden="true"
    >
      <path d="M5 7.5L10 12.5L15 7.5" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

// 네이티브 <select>는 드롭다운이 열렸을 때 현재 선택된/포커스된 옵션에 브라우저(OS)가 자체
// 강조색(윈도우 기본 파란색)을 강제로 씌워서, CSS로 아무리 다크 테마를 줘도 그 항목만 계속
// 파랗게 번쩍인다 — inline style이나 :checked/:hover !important로도 못 이기는 크로미움의
// 알려진 제약이라, 아예 직접 그린 드롭다운으로 바꿔서 모든 상태를 우리가 통제한다.
export default function BroadcastDropdown({
  value,
  onChange,
  triggerClassName,
  chevronClassName,
  listClassName,
}: BroadcastDropdownProps) {
  const [isOpen, setIsOpen] = useState(false);
  const rootRef = useRef<HTMLDivElement>(null);
  const label = BROADCASTS.find((b) => b.value === value)?.label ?? "전체";

  useEffect(() => {
    if (!isOpen) return;
    function handlePointerDown(e: MouseEvent) {
      if (rootRef.current && !rootRef.current.contains(e.target as Node)) setIsOpen(false);
    }
    function handleKeyDown(e: KeyboardEvent) {
      if (e.key === "Escape") setIsOpen(false);
    }
    document.addEventListener("mousedown", handlePointerDown);
    document.addEventListener("keydown", handleKeyDown);
    return () => {
      document.removeEventListener("mousedown", handlePointerDown);
      document.removeEventListener("keydown", handleKeyDown);
    };
  }, [isOpen]);

  return (
    <div ref={rootRef} className="relative">
      <button type="button" onClick={() => setIsOpen((open) => !open)} className={triggerClassName}>
        <span className="truncate">{label}</span>
        <ChevronIcon isOpen={isOpen} className={chevronClassName} />
      </button>
      {isOpen && (
        <ul
          role="listbox"
          className={`absolute z-20 mt-1.5 max-h-72 overflow-y-auto rounded-xl border border-line bg-surface py-1 shadow-xl shadow-black/30 ${listClassName ?? "w-full"}`}
        >
          {BROADCASTS.map((b) => (
            <li key={b.value} role="option" aria-selected={b.value === value}>
              <button
                type="button"
                onClick={() => {
                  onChange(b.value);
                  setIsOpen(false);
                }}
                className={`block w-full px-3 py-2 text-left text-sm transition ${
                  b.value === value ? "bg-accent-soft font-semibold text-accent-soft-ink" : "text-ink hover:bg-surface-hover"
                }`}
              >
                {b.label}
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
