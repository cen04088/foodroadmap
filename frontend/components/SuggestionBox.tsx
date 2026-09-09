"use client";

import { useState } from "react";
import { ApiError, submitSuggestion, type SuggestionKind } from "../lib/api";

const BODY_MAX = 2000;

const KINDS: { value: SuggestionKind; label: string; placeholder: string }[] = [
  {
    value: "broadcast",
    label: "방송·유튜버 추가 요청",
    placeholder: "예: 성시경의 먹을텐데를 추가해주세요. 유튜브 채널이라 회차가 꾸준히 올라와요.",
  },
  {
    value: "improvement",
    label: "개선 의견",
    placeholder: "예: 경로 검색 결과를 거리순으로도 정렬할 수 있으면 좋겠어요.",
  },
];

function errorMessageFor(error: unknown): string {
  if (error instanceof ApiError) {
    if (error.status === 0) return "서버에 연결할 수 없습니다";
    if (error.status === 429) return "한 시간에 보낼 수 있는 건의는 5건입니다. 잠시 후 다시 시도해주세요";
    if (error.status === 422) return "내용을 다시 확인해주세요";
    return "보내지 못했습니다, 잠시 후 다시 시도해주세요";
  }
  return "알 수 없는 오류가 발생했습니다";
}

export default function SuggestionBox() {
  const [kind, setKind] = useState<SuggestionKind>("broadcast");
  const [body, setBody] = useState("");
  const [contact, setContact] = useState("");
  const [isSending, setIsSending] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [isSent, setIsSent] = useState(false);

  const activeKind = KINDS.find((k) => k.value === kind) ?? KINDS[0];
  const trimmed = body.trim();
  const canSend = trimmed.length > 0 && trimmed.length <= BODY_MAX && !isSending;

  async function handleSubmit() {
    if (!canSend) return;
    setIsSending(true);
    setErrorMessage(null);
    try {
      await submitSuggestion({ kind, body: trimmed, contact: contact.trim() || undefined });
      setIsSent(true);
      setBody("");
      setContact("");
    } catch (error) {
      setErrorMessage(errorMessageFor(error));
    } finally {
      setIsSending(false);
    }
  }

  if (isSent) {
    return (
      <div className="mx-auto max-w-2xl">
        <div className="rounded-2xl border border-white/10 bg-surface p-8 text-center">
          <p className="text-lg font-bold text-ink">보내주셔서 감사합니다</p>
          <p className="mt-2 text-sm text-ink-muted">
            남겨주신 의견은 하나씩 확인하고 있어요. 반영되면 목록에서 만나실 수 있습니다.
          </p>
          <button
            type="button"
            onClick={() => setIsSent(false)}
            className="mt-5 rounded-full bg-accent px-4 py-2 text-sm font-bold text-[#171310] transition hover:bg-accent-hover"
          >
            하나 더 보내기
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-2xl">
      <p className="text-sm text-ink-muted">
        빠진 방송이나 유튜버, 불편했던 점을 알려주세요. 로그인 없이 바로 보낼 수 있습니다.
      </p>

      <div className="mt-5 flex flex-wrap gap-2">
        {KINDS.map((option) => (
          <button
            key={option.value}
            type="button"
            onClick={() => setKind(option.value)}
            aria-pressed={kind === option.value}
            className={`rounded-full px-4 py-2 text-sm transition ${
              kind === option.value
                ? "bg-accent font-semibold text-[#171310]"
                : "bg-surface text-ink-muted hover:bg-surface-hover"
            }`}
          >
            {option.label}
          </button>
        ))}
      </div>

      <label className="mt-5 block">
        <span className="mb-1.5 block text-sm font-semibold text-ink">내용</span>
        <textarea
          value={body}
          onChange={(e) => setBody(e.target.value)}
          rows={6}
          maxLength={BODY_MAX}
          placeholder={activeKind.placeholder}
          className="w-full resize-y rounded-xl border border-line bg-surface px-4 py-3 text-sm text-ink placeholder:text-ink-muted outline-none transition focus:border-accent focus:ring-4 focus:ring-accent-soft"
        />
      </label>
      <p className="mt-1 text-right text-xs text-ink-muted">
        {trimmed.length} / {BODY_MAX}
      </p>

      <label className="mt-3 block">
        <span className="mb-1.5 block text-sm font-semibold text-ink">
          연락처 <span className="font-normal text-ink-muted">(선택 — 답장이 필요할 때만)</span>
        </span>
        <input
          type="text"
          value={contact}
          onChange={(e) => setContact(e.target.value)}
          maxLength={200}
          placeholder="이메일 또는 SNS 계정"
          className="w-full rounded-xl border border-line bg-surface px-4 py-3 text-sm text-ink placeholder:text-ink-muted outline-none transition focus:border-accent focus:ring-4 focus:ring-accent-soft"
        />
      </label>

      {errorMessage && (
        <div className="mt-4 rounded-xl border border-danger/20 bg-danger-soft px-4 py-3 text-sm text-danger-ink">
          {errorMessage}
        </div>
      )}

      <button
        type="button"
        disabled={!canSend}
        onClick={handleSubmit}
        className="mt-5 w-full rounded-xl bg-accent px-6 py-3.5 text-base font-bold text-[#171310] transition hover:bg-accent-hover disabled:cursor-not-allowed disabled:bg-line disabled:text-ink-muted"
      >
        {isSending ? "보내는 중" : "건의 보내기"}
      </button>
    </div>
  );
}
