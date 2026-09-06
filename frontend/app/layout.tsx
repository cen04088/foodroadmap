import type { Metadata } from "next";
import Script from "next/script";
import "./globals.css";

const ADSENSE_CLIENT_ID = process.env.NEXT_PUBLIC_ADSENSE_CLIENT_ID;

export const metadata: Metadata = {
  title: "FOODMAP — 미식 로드트립",
  description: "목적지까지 가는 길을 방송 맛집 여행으로 만들어드려요",
  // 스크립트 태그 방식 확인이 안 될 때를 대비한 두 번째 소유권 확인 경로 — 둘 다 있어도 무방하다.
  ...(ADSENSE_CLIENT_ID && { verification: { other: { "google-adsense-account": ADSENSE_CLIENT_ID } } }),
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="ko" className="h-full antialiased">
      <body className="min-h-full flex flex-col font-sans">
        {ADSENSE_CLIENT_ID && (
          // strategy="beforeInteractive"면 이 태그를 어디에 두든 Next.js가 알아서
          // 문서 <head>로 끌어올려 넣어준다 — 직접 <head> 엘리먼트를 만들 필요 없음.
          <Script
            async
            src={`https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js?client=${ADSENSE_CLIENT_ID}`}
            crossOrigin="anonymous"
            strategy="beforeInteractive"
          />
        )}
        {children}
      </body>
    </html>
  );
}
