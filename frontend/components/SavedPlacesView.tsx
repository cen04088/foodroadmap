"use client";

import { useFavorites, type FavoritePlace } from "../lib/favorites";

export interface SavedPlacesViewProps {
  onClose: () => void;
  topOffset: number;
  onShowOnMap: (place: FavoritePlace) => void;
  onSetAsOrigin: (place: FavoritePlace) => void;
  onSetAsDestination: (place: FavoritePlace) => void;
}

export default function SavedPlacesView({
  onClose,
  topOffset,
  onShowOnMap,
  onSetAsOrigin,
  onSetAsDestination,
}: SavedPlacesViewProps) {
  const { favorites, remove, clear } = useFavorites();

  return (
    <div
      className="fixed inset-x-0 bottom-0 z-30 overflow-y-auto bg-[#171310]"
      style={{ top: topOffset }}
    >
      <div className="mx-auto max-w-3xl px-5 py-6">
        <div className="mb-5 flex items-start justify-between gap-4">
          <div>
            <h2 className="text-xl font-bold tracking-tight text-[#fff7ed]">저장한 곳</h2>
            <p className="mt-1 text-sm text-[#a89c91]">
              {favorites.length > 0
                ? "출발지와 목적지를 지정하면 저장한 곳을 잇는 코스를 만들어드려요."
                : "맛집 카드의 북마크를 눌러 가고 싶은 곳을 모아보세요."}
            </p>
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label="닫기"
            className="shrink-0 rounded-full p-1.5 text-[#a89c91] transition hover:bg-white/10 hover:text-[#fff7ed]"
          >
            <svg viewBox="0 0 20 20" fill="none" className="h-5 w-5" aria-hidden="true">
              <path d="M5 5l10 10M15 5L5 15" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" />
            </svg>
          </button>
        </div>

        {favorites.length === 0 ? (
          <div className="rounded-2xl border border-dashed border-white/10 px-4 py-12 text-center text-sm text-[#a89c91]">
            아직 저장한 곳이 없어요.
          </div>
        ) : (
          <>
            <ul className="flex flex-col gap-2">
              {favorites.map((place) => (
                <li
                  key={place.id}
                  className="rounded-xl border border-white/10 bg-[#29201a] p-4"
                >
                  <div className="flex items-start gap-3">
                    <div className="min-w-0 flex-1">
                      <div className="flex items-center gap-2">
                        <span className="truncate text-[15px] font-semibold text-[#fff7ed]">{place.name}</span>
                        {place.category && (
                          <span className="shrink-0 rounded-full bg-white/5 px-2.5 py-0.5 text-xs font-medium text-[#a89c91]">
                            {place.category}
                          </span>
                        )}
                      </div>
                      {place.address && (
                        <p className="mt-1 truncate text-sm text-[#a89c91]">{place.address}</p>
                      )}
                    </div>
                    <button
                      type="button"
                      onClick={() => remove(place.id)}
                      aria-label={`${place.name} 저장 목록에서 삭제`}
                      className="shrink-0 rounded-full p-1 text-[#a89c91] transition hover:bg-white/10 hover:text-[#fca5a5]"
                    >
                      <svg viewBox="0 0 20 20" fill="none" className="h-4 w-4" aria-hidden="true">
                        <path d="M5 5l10 10M15 5L5 15" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" />
                      </svg>
                    </button>
                  </div>

                  <div className="mt-3 flex flex-wrap gap-2 text-xs">
                    <button
                      type="button"
                      onClick={() => onSetAsOrigin(place)}
                      className="rounded-full bg-[#ff7a1a] px-3 py-1.5 font-semibold text-[#171310] transition hover:bg-[#ffb45a]"
                    >
                      출발지로
                    </button>
                    <button
                      type="button"
                      onClick={() => onSetAsDestination(place)}
                      className="rounded-full bg-[#ff7a1a] px-3 py-1.5 font-semibold text-[#171310] transition hover:bg-[#ffb45a]"
                    >
                      목적지로
                    </button>
                    <button
                      type="button"
                      onClick={() => onShowOnMap(place)}
                      className="rounded-full bg-white/5 px-3 py-1.5 text-[#a89c91] transition hover:bg-white/10 hover:text-[#fff7ed]"
                    >
                      지도에서 보기
                    </button>
                  </div>
                </li>
              ))}
            </ul>

            <button
              type="button"
              onClick={clear}
              className="mt-5 text-xs text-[#a89c91] underline underline-offset-4 transition hover:text-[#fca5a5]"
            >
              저장한 곳 전체 삭제
            </button>
          </>
        )}
      </div>
    </div>
  );
}
