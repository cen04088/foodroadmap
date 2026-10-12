"use client";

import { Fragment, useEffect, useMemo, useRef } from "react";
import RestaurantCard from "./RestaurantCard";
import type { RestaurantResult } from "../lib/api";
import { formatClock } from "../lib/format";
import { groupByMealWindow, type RouteSection } from "../lib/mealSections";
import { matchesFilters, type RestaurantFilterCriteria } from "../lib/restaurantFilter";

export interface RestaurantListProps {
  restaurants: RestaurantResult[];
  selectedId: string | null;
  // 지정하면 필터에 안 맞는 카드를 지우지 않고 흑백+반투명으로 죽인다 (재검색 없이).
  activeFilters?: RestaurantFilterCriteria;
  onSelect: (id: string) => void;
  onShowDetail: (id: string) => void;
  scrollToId?: string | null;
  // AI 식사 플래너가 고른 식당 id — 경로 전체 목록에서도 "AI 추천" 배지로 구분한다.
  aiPickIds?: string[] | null;
  // 경로 결과를 받은 시각(ms). 지금 출발한다고 보고 식사 시간대 구간 제목을 붙인다. 없으면 제목 없이 그린다.
  departureTime?: number | null;
}

// 첫 식사 구간 제목에 붙는 표식. 경로 결과가 오면 page.tsx가 이걸 찾아 패널을 그 구간으로 내린다.
export const MEAL_JUMP_ATTR = "data-meal-jump";

function arrivalRange(section: RouteSection<RestaurantResult>): string {
  const first = formatClock(section.firstArrival);
  const last = formatClock(section.lastArrival);
  return first === last ? first : `${first}–${last}`;
}

export default function RestaurantList({
  restaurants,
  selectedId,
  activeFilters,
  onSelect,
  onShowDetail,
  scrollToId,
  aiPickIds,
  departureTime,
}: RestaurantListProps) {
  const itemRefs = useRef<Map<string, HTMLDivElement>>(new Map());
  const jumpRef = useRef<HTMLDivElement>(null);

  const sections = useMemo(
    () => (departureTime ? groupByMealWindow(restaurants, new Date(departureTime)) : null),
    [restaurants, departureTime],
  );
  const firstMeal = sections?.find((section) => section.meal) ?? null;

  useEffect(() => {
    if (!scrollToId) return;
    itemRefs.current.get(scrollToId)?.scrollIntoView({ behavior: "smooth", block: "nearest" });
  }, [scrollToId]);

  if (restaurants.length === 0) {
    return (
      <div className="flex h-full min-h-[200px] items-center justify-center rounded-2xl border border-dashed border-line px-4 text-center text-sm text-ink-muted">
        이 경로 근처엔 방송 맛집이 없어요
      </div>
    );
  }

  function renderCard(restaurant: RestaurantResult, index: number) {
    return (
      <div
        key={restaurant.id}
        ref={(el) => {
          if (el) itemRefs.current.set(restaurant.id, el);
          else itemRefs.current.delete(restaurant.id);
        }}
      >
        <RestaurantCard
          restaurant={restaurant}
          order={index + 1}
          isSelected={selectedId === restaurant.id}
          isDimmed={activeFilters ? !matchesFilters(restaurant, activeFilters) : false}
          isAiPick={aiPickIds?.includes(restaurant.id) ?? false}
          onSelect={onSelect}
          onShowDetail={onShowDetail}
        />
      </div>
    );
  }

  return (
    <div className="no-scrollbar flex flex-col gap-3 overflow-y-auto">
      {/* 데스크톱은 결과가 오면 패널이 첫 식사 구간으로 내려가지만, 모바일은 페이지 전체가 스크롤돼서
          자동으로 내리면 지도가 밀려난다 — 대신 목록 맨 위에서 한 번에 건너뛰게 한다. */}
      {firstMeal && firstMeal.startIndex > 0 && (
        <div className="flex items-center gap-3 rounded-xl border border-[#ffb45a]/30 bg-[#ffb45a]/10 px-3 py-2 text-xs leading-5 text-[#ffd19a]">
          <span className="min-w-0 flex-1">
            지금 출발하면 {firstMeal.meal!.name} 시간대에 {firstMeal.items.length}곳을 지나요
          </span>
          <button
            type="button"
            onClick={() => jumpRef.current?.scrollIntoView({ behavior: "smooth", block: "start" })}
            className="shrink-0 font-semibold text-[#ffb45a] transition hover:text-[#fff7ed]"
          >
            바로 보기
          </button>
        </div>
      )}
      {sections
        ? sections.map((section) => {
            const isJumpTarget = section === firstMeal;
            return (
              <Fragment key={section.startIndex}>
                {/* scroll-mt: 모바일에서는 뷰포트 상단의 sticky 토글 밴드 아래에 제목이 오게 한다.
                    데스크톱 패널은 컨테이너의 scroll-padding이 같은 일을 하므로 0으로 되돌린다. */}
                <div
                  ref={isJumpTarget ? jumpRef : undefined}
                  {...(isJumpTarget ? { [MEAL_JUMP_ATTR]: "" } : {})}
                  className="flex scroll-mt-20 items-baseline justify-between gap-2 px-1 pt-1 text-xs sm:scroll-mt-0"
                >
                  <span className={section.meal ? "font-bold text-[#ffb45a]" : "font-semibold text-[#a89c91]"}>
                    {section.label}
                  </span>
                  <span className="text-[#a89c91]">
                    {arrivalRange(section)} 도착 · {section.items.length}곳
                  </span>
                </div>
                {section.items.map((restaurant, offset) => renderCard(restaurant, section.startIndex + offset))}
              </Fragment>
            );
          })
        : restaurants.map(renderCard)}
    </div>
  );
}
