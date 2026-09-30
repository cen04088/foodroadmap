"use client";

import { useEffect, useState } from "react";

type Kind = "improvement" | "broadcast";

interface Suggestion {
  id: number;
  kind: Kind;
  body: string;
  contact: string | null;
  created_at: string;
}

const KIND_LABEL: Record<Kind, string> = { improvement: "개선사항", broadcast: "방송 추가 요청" };
const PAGE_SIZE = 200;
// 토큰은 번들에 넣지 않고 입력받아 탭이 닫히면 사라지는 sessionStorage에만 둔다.
const TOKEN_KEY = "foodroad-admin-token";

function readStoredToken(): string {
  try {
    return sessionStorage.getItem(TOKEN_KEY) ?? "";
  } catch {
    return "";
  }
}

function storeToken(token: string | null) {
  try {
    if (token) sessionStorage.setItem(TOKEN_KEY, token);
    else sessionStorage.removeItem(TOKEN_KEY);
  } catch {}
}

async function fetchSuggestions(token: string, offset: number): Promise<Suggestion[]> {
  const baseUrl = process.env.NEXT_PUBLIC_API_BASE_URL ?? "";
  let response: Response;
  try {
    response = await fetch(`${baseUrl}/api/suggestions?limit=${PAGE_SIZE}&offset=${offset}`, {
      headers: { "X-Admin-Token": token },
      cache: "no-store",
    });
  } catch {
    throw new Error("서버에 연결할 수 없습니다");
  }
  if (response.status === 401) throw new Error("토큰이 올바르지 않습니다");
  if (!response.ok) throw new Error(`불러오지 못했습니다 (${response.status})`);
  const data = (await response.json()) as { suggestions: Suggestion[] };
  return data.suggestions;
}

function formatDate(iso: string): string {
  // 서버는 UTC 기준 naive ISO 문자열을 준다 — 한국 시간으로 보여준다.
  const date = new Date(/[zZ]|[+-]\d\d:?\d\d$/.test(iso) ? iso : `${iso}Z`);
  return date.toLocaleString("ko-KR", { timeZone: "Asia/Seoul", dateStyle: "short", timeStyle: "short" });
}

export default function AdminPage() {
  const [tokenInput, setTokenInput] = useState("");
  const [token, setToken] = useState<string | null>(null);
  const [items, setItems] = useState<Suggestion[]>([]);
  const [hasMore, setHasMore] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [filter, setFilter] = useState<Kind | "all">("all");

  async function load(nextToken: string, offset: number) {
    setLoading(true);
    setError(null);
    try {
      const page = await fetchSuggestions(nextToken, offset);
      setItems((prev) => (offset === 0 ? page : [...prev, ...page]));
      setHasMore(page.length === PAGE_SIZE);
      setToken(nextToken);
      storeToken(nextToken);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "불러오지 못했습니다");
      if (offset === 0) {
        setToken(null);
        storeToken(null);
      }
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    const stored = readStoredToken();
    // eslint-disable-next-line react-hooks/set-state-in-effect -- 마운트 시 한 번 저장된 토큰으로 자동 조회
    if (stored) void load(stored, 0);
  }, []);

  const visible = filter === "all" ? items : items.filter((s) => s.kind === filter);
  const counts = {
    all: items.length,
    improvement: items.filter((s) => s.kind === "improvement").length,
    broadcast: items.filter((s) => s.kind === "broadcast").length,
  };

  if (!token) {
    return (
      <main className="mx-auto flex min-h-screen w-full max-w-sm flex-col justify-center px-4">
        <h1 className="mb-4 text-xl font-bold">건의함 관리</h1>
        <form
          onSubmit={(e) => {
            e.preventDefault();
            if (tokenInput.trim()) void load(tokenInput.trim(), 0);
          }}
          className="flex flex-col gap-3"
        >
          <input
            type="password"
            value={tokenInput}
            onChange={(e) => setTokenInput(e.target.value)}
            placeholder="관리자 토큰"
            autoComplete="off"
            className="rounded-lg border border-gray-300 px-3 py-2"
          />
          <button
            type="submit"
            disabled={loading || !tokenInput.trim()}
            className="rounded-lg bg-gray-900 px-3 py-2 font-medium text-white disabled:opacity-50"
          >
            {loading ? "확인 중…" : "열기"}
          </button>
          {error && <p className="text-sm text-red-600">{error}</p>}
        </form>
      </main>
    );
  }

  return (
    <main className="mx-auto w-full max-w-4xl px-4 py-8">
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <h1 className="text-xl font-bold">건의함 ({counts.all}건)</h1>
        <div className="flex gap-2">
          <button
            onClick={() => void load(token, 0)}
            disabled={loading}
            className="rounded-lg border border-gray-300 px-3 py-1.5 text-sm disabled:opacity-50"
          >
            새로고침
          </button>
          <button
            onClick={() => {
              storeToken(null);
              setToken(null);
              setItems([]);
              setTokenInput("");
            }}
            className="rounded-lg border border-gray-300 px-3 py-1.5 text-sm"
          >
            잠그기
          </button>
        </div>
      </div>

      <div className="mb-4 flex flex-wrap gap-2">
        {(["all", "improvement", "broadcast"] as const).map((key) => (
          <button
            key={key}
            onClick={() => setFilter(key)}
            className={`rounded-full px-3 py-1 text-sm ${filter === key ? "bg-gray-900 text-white" : "bg-gray-100 text-gray-700"}`}
          >
            {key === "all" ? "전체" : KIND_LABEL[key]} {counts[key]}
          </button>
        ))}
      </div>

      {error && <p className="mb-4 text-sm text-red-600">{error}</p>}

      {visible.length === 0 ? (
        <p className="py-12 text-center text-gray-500">{loading ? "불러오는 중…" : "건의가 없습니다"}</p>
      ) : (
        <ul className="flex flex-col gap-3">
          {visible.map((s) => (
            <li key={s.id} className="rounded-xl border border-gray-200 p-4">
              <div className="mb-2 flex flex-wrap items-center gap-2 text-xs text-gray-500">
                <span
                  className={`rounded-full px-2 py-0.5 font-medium ${s.kind === "broadcast" ? "bg-amber-100 text-amber-800" : "bg-sky-100 text-sky-800"}`}
                >
                  {KIND_LABEL[s.kind] ?? s.kind}
                </span>
                <span>#{s.id}</span>
                <span>{formatDate(s.created_at)}</span>
                {s.contact && <span className="break-all">연락처: {s.contact}</span>}
              </div>
              <p className="whitespace-pre-wrap break-words text-sm">{s.body}</p>
            </li>
          ))}
        </ul>
      )}

      {hasMore && (
        <button
          onClick={() => void load(token, items.length)}
          disabled={loading}
          className="mt-4 w-full rounded-lg border border-gray-300 py-2 text-sm disabled:opacity-50"
        >
          {loading ? "불러오는 중…" : "더 보기"}
        </button>
      )}
    </main>
  );
}
