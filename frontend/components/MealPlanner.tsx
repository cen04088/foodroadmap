"use client";

import { useEffect, useRef, useState } from "react";
import { ApiError, fetchMealRecommendations, type MealRecommendationResponse, type RestaurantResult } from "../lib/api";

const EXAMPLES = ["한 시간쯤 뒤, 한식으로 2만 원 이하", "가는 길에 국수 먹고 싶어", "가능한 일찍, 저렴한 메뉴로"];
const FOLLOWUPS = ["30분 더 일찍", "더 저렴하게", "시간 상관없이"];

interface Props {
  contextId: string | undefined;
  restaurants: RestaurantResult[];
  disabled: boolean;
  selectedId: string | null;
  onRecommendations: (ids: string[] | null) => void;
  onSelect: (id: string) => void;
  onDetail: (id: string) => void;
}

export default function MealPlanner({ contextId, restaurants, disabled, selectedId, onRecommendations, onSelect, onDetail }: Props) {
  const [message, setMessage] = useState("");
  const [submitted, setSubmitted] = useState("");
  const [answer, setAnswer] = useState<MealRecommendationResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [expired, setExpired] = useState(false);
  const controller = useRef<AbortController | null>(null);
  const sequence = useRef(0);
  const busy = disabled || loading || expired || !contextId || restaurants.length === 0;

  useEffect(() => () => { controller.current?.abort(); }, []);

  async function submit(text: string) {
    if (busy || !contextId || !text.trim()) return;
    const seq = ++sequence.current;
    controller.current?.abort();
    const pending = new AbortController();
    controller.current = pending;
    setLoading(true);
    setError(null);
    // Bound client waiting even if a proxy drops the connection without closing it.
    const timeout = window.setTimeout(() => pending.abort(), 45000);
    try {
      const response = await fetchMealRecommendations({
        route_context_id: contextId, message: text.trim(), previous: answer?.preferences ?? null,
      }, pending.signal);
      if (seq !== sequence.current || pending.signal.aborted) return;
      setAnswer(response);
      setSubmitted(text.trim());
      setMessage("");
      onRecommendations(response.preferences.clarification ? null : response.recommendations.map(r => r.restaurant_id));
    } catch (reason) {
      if (seq !== sequence.current) return;
      setError(pending.signal.aborted ? "응답이 늦어지고 있어요. 다시 시도해주세요." : reason instanceof Error ? reason.message : "추천을 불러오지 못했어요.");
      if (reason instanceof ApiError && reason.status === 410) setExpired(true);
    } finally {
      window.clearTimeout(timeout);
      if (seq === sequence.current) setLoading(false);
    }
  }

  function reset() {
    sequence.current += 1;
    controller.current?.abort();
    setAnswer(null);
    setSubmitted("");
    setMessage("");
    setError(null);
    setLoading(false);
    onRecommendations(null);
  }

  const p = answer?.preferences;
  const chips = p ? [
    ...(p.target_minutes !== null ? [`출발 ${p.target_minutes}분 후 ±${p.time_window_minutes}분`] : []),
    ...(p.max_price_won !== null ? [`메뉴 ${p.max_price_won.toLocaleString()}원 이하`] : []),
    ...p.categories, ...p.broadcasts, ...p.menu_keywords,
    ...p.excluded_keywords.map(k => `${k} 제외`),
    ...(p.sort === "price" ? ["낮은 메뉴 가격순"] : p.sort === "earliest" ? ["일찍 지나는 순"] : []),
  ] : [];

  return (
    <section className="mb-4 overflow-hidden rounded-2xl border border-[#ffb45a]/30 bg-[#211a14] text-[#fff7ed]" aria-label="AI 식사 추천" aria-busy={loading}>
      <div className="border-b border-white/10 px-4 py-4">
        <div className="flex items-center justify-between gap-2">
          <p className="text-[11px] font-bold tracking-[0.15em] text-[#ffb45a]">AI MEAL PLANNER</p>
          {(answer || loading) && <button type="button" onClick={reset} className="text-xs text-[#bfb1a4] underline underline-offset-4 hover:text-white">처음부터</button>}
        </div>
        <h2 className="mt-1 text-lg font-bold">가는 길, 뭐 먹을까요?</h2>
        <p className="mt-1 text-xs leading-5 text-[#bfb1a4]">식사 시간과 먹고 싶은 메뉴를 알려주세요.<br />지금 경로에서 최대 3곳을 골라드려요.</p>
      </div>

      <div className="space-y-3 p-4">
        {submitted && <p className="rounded-xl bg-white/5 px-3 py-2 text-sm leading-6">“{submitted}”</p>}
        {answer && <div className="space-y-3" aria-live="polite">
          <p className="text-sm leading-6">{answer.reply}</p>
          {chips.length > 0 && <div className="flex flex-wrap gap-1.5" aria-label="적용된 식사 조건">
            {chips.map((chip, index) => <span key={`${index}-${chip}`} className="rounded-md bg-[#ffb45a]/10 px-2 py-1 text-[11px] text-[#ffd19a]">{chip}</span>)}
          </div>}
          {answer.preferences.unverified.length > 0 && <p className="rounded-lg border border-[#ffb45a]/20 px-3 py-2 text-xs leading-5 text-[#ffd19a]">확인 필요 · {answer.preferences.unverified.join(", ")}<br />이 조건은 추천에 반영하지 못했어요.</p>}
          <div className="space-y-2">
            {answer.recommendations.map((item, index) => {
              const restaurant = restaurants.find(r => r.id === item.restaurant_id);
              if (!restaurant) return null;
              return <article key={item.restaurant_id} className={`rounded-xl border p-3 ${selectedId === restaurant.id ? "border-[#ffb45a] bg-[#ffb45a]/10" : "border-white/10 bg-white/[0.03]"}`}>
                <button type="button" onClick={() => onSelect(restaurant.id)} className="flex w-full items-center gap-2 text-left hover:text-[#ffb45a]" aria-label={`${restaurant.name} 지도에서 보기`}>
                  <span className="grid h-6 w-6 shrink-0 place-items-center rounded-full bg-[#ffb45a] text-xs font-bold text-[#211a14]">{index + 1}</span>
                  <span className="text-sm font-bold">{restaurant.name}</span>
                </button>
                <ul className="mt-2 space-y-1 text-xs leading-5 text-[#cabbad]">{item.reasons.map(reason => <li key={reason}>{reason}</li>)}</ul>
                <div className="mt-3 flex gap-3 text-xs font-semibold text-[#ffb45a]">
                  <button type="button" onClick={() => onSelect(restaurant.id)} className="hover:underline">지도에서 보기 ↗</button>
                  <button type="button" onClick={() => onDetail(restaurant.id)} className="hover:underline">메뉴·방송 상세</button>
                </div>
              </article>;
            })}
          </div>
          <details className="text-[11px] leading-5 text-[#bfb1a4]">
            <summary className="cursor-pointer hover:text-white">추천 기준과 확인할 점</summary>
            <ul className="mt-2 space-y-1">{answer.notes.map(note => <li key={note}>{note}</li>)}</ul>
          </details>
          <p className="text-[11px] leading-4 text-[#bfb1a4]">표시 시간은 경로상 예상 통과 시점이며 우회 시간은 제외돼요.</p>
        </div>}

        <form onSubmit={event => { event.preventDefault(); void submit(message); }}>
          <label htmlFor="meal-request" className="mb-2 block text-xs font-medium text-[#ffd19a]">{answer ? "조건을 바꿔볼까요?" : "어떤 식사를 원하세요?"}</label>
          <textarea id="meal-request" value={message} onChange={event => setMessage(event.target.value)} maxLength={1000} rows={2} disabled={busy} placeholder="예: 한 시간 뒤, 한식으로 2만 원 이하" className="w-full resize-y rounded-xl border border-white/15 bg-[#171310] px-3 py-2.5 text-sm leading-6 text-[#fff7ed] outline-none placeholder:text-[#8d8074] focus:border-[#ffb45a] disabled:opacity-50" />
          <button type="submit" disabled={busy || !message.trim()} className="mt-2 w-full rounded-xl bg-[#ffb45a] px-3 py-2.5 text-sm font-bold text-[#211a14] transition hover:bg-[#ffd19a] disabled:cursor-not-allowed disabled:opacity-40">{loading ? "식사 조건을 읽고 있어요…" : answer ? "조건 바꿔 추천받기" : "내 경로에서 추천받기"}</button>
        </form>
        <div className="flex flex-wrap gap-1.5">
          {(answer ? FOLLOWUPS : EXAMPLES).map(example => <button key={example} type="button" disabled={busy} onClick={() => void submit(example)} className="rounded-full border border-white/15 px-2.5 py-1.5 text-[11px] text-[#cabbad] hover:border-[#ffb45a]/60 hover:text-[#ffb45a] disabled:opacity-40">{example}</button>)}
        </div>
        {error && <p role="alert" className="rounded-lg bg-red-400/10 px-3 py-2 text-xs leading-5 text-red-200">{error}</p>}
        {!contextId && <p className="text-xs leading-5 text-[#bfb1a4]">AI 추천을 위한 경로 정보가 없어요. 경로를 다시 검색해주세요.</p>}
        {restaurants.length === 0 && <p className="text-xs leading-5 text-[#bfb1a4]">이 경로에는 추천할 방송 맛집이 없어요. 다른 경로를 검색해보세요.</p>}
        {!answer && <p className="text-[10px] leading-4 text-[#a99a8d]">입력한 식사 조건은 AI에 전달돼요. 추천 근거는 등록된 메뉴·가격·방송 정보로 확인합니다.</p>}
      </div>
    </section>
  );
}
