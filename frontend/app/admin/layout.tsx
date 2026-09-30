import type { Metadata } from "next";
import type { ReactNode } from "react";

// 관리자 전용 화면 — 검색 결과에 노출되지 않게 한다.
export const metadata: Metadata = {
  title: "건의함 관리 — 맛집로드",
  robots: { index: false, follow: false },
};

export default function AdminLayout({ children }: { children: ReactNode }) {
  return children;
}
