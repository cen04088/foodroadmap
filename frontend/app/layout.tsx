import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "foodmap — 경로 맛집",
  description: "가는 길에 있는 방송 맛집을 찾아드려요",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="ko" className="h-full antialiased">
      <body className="min-h-full flex flex-col font-sans">{children}</body>
    </html>
  );
}
