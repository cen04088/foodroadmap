import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "FOODMAP — 미식 로드트립",
  description: "목적지까지 가는 길을 방송 맛집 여행으로 만들어드려요",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="ko" className="h-full antialiased">
      <body className="min-h-full flex flex-col font-sans">{children}</body>
    </html>
  );
}
