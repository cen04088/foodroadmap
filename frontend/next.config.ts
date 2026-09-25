import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // 페이지가 전부 클라이언트 렌더링이라 정적 파일(out/)로 내보내고 serve.mjs로 서빙한다 —
  // Next 서버를 상주시키지 않아 Railway 메모리 과금이 줄어든다.
  output: "export",
};

export default nextConfig;
