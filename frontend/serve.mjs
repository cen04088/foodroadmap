// `next build`(output: "export")가 만든 out/ 정적 파일을 서빙하는 의존성 없는 서버.
// 페이지가 전부 클라이언트 렌더링이라 Next 서버(SSR 런타임, ~100MB+)를 상주시킬 이유가 없다 —
// Railway는 상주 메모리로 과금하므로 이 서버로 바꿔 프론트 메모리를 줄인다.
import { createReadStream } from "node:fs";
import { stat } from "node:fs/promises";
import { createServer } from "node:http";
import { extname, join, normalize, resolve, sep } from "node:path";
import { createGzip } from "node:zlib";

const ROOT = resolve(import.meta.dirname, "out");
const PORT = Number(process.env.PORT) || 3000;

const MIME = {
  ".html": "text/html; charset=utf-8",
  ".js": "text/javascript; charset=utf-8",
  ".css": "text/css; charset=utf-8",
  ".json": "application/json; charset=utf-8",
  ".txt": "text/plain; charset=utf-8",
  ".svg": "image/svg+xml",
  ".png": "image/png",
  ".jpg": "image/jpeg",
  ".jpeg": "image/jpeg",
  ".webp": "image/webp",
  ".ico": "image/x-icon",
  ".woff2": "font/woff2",
  ".woff": "font/woff",
};
// next start가 하던 gzip 압축을 유지한다 — 이미 압축된 이미지·폰트는 제외.
const COMPRESSIBLE = new Set([".html", ".js", ".css", ".json", ".txt", ".svg"]);
// _next/static은 파일명에 해시가 붙어 내용이 바뀌면 이름도 바뀌므로 오래 캐싱해도 안전하다.
const IMMUTABLE = "public, max-age=31536000, immutable";
const REVALIDATE = "public, max-age=0, must-revalidate";

async function resolveFile(urlPath) {
  const rel = normalize(decodeURIComponent(urlPath)).replace(/^([/\\])+/, "");
  const base = join(ROOT, rel);
  if (base !== ROOT && !base.startsWith(ROOT + sep)) return null;
  // /foo → foo, foo.html, foo/index.html 순으로 찾는다 (export의 trailingSlash=false 규칙).
  for (const candidate of [base, `${base}.html`, join(base, "index.html")]) {
    try {
      const info = await stat(candidate);
      if (info.isFile()) return { path: candidate, size: info.size };
    } catch {}
  }
  return null;
}

createServer(async (req, res) => {
  if (req.method !== "GET" && req.method !== "HEAD") {
    res.writeHead(405, { Allow: "GET, HEAD" }).end();
    return;
  }
  let file;
  try {
    file = await resolveFile(new URL(req.url, "http://localhost").pathname);
  } catch {
    file = null; // 잘못된 퍼센트 인코딩 등
  }
  const status = file ? 200 : 404;
  file ??= await resolveFile("/404.html");
  if (!file) {
    res.writeHead(404, { "Content-Type": "text/plain; charset=utf-8" }).end("Not Found");
    return;
  }
  const ext = extname(file.path);
  const gzip = COMPRESSIBLE.has(ext) && /\bgzip\b/.test(req.headers["accept-encoding"] ?? "");
  res.writeHead(status, {
    "Content-Type": MIME[ext] ?? "application/octet-stream",
    "Cache-Control": req.url.startsWith("/_next/static/") ? IMMUTABLE : REVALIDATE,
    Vary: "Accept-Encoding",
    ...(gzip ? { "Content-Encoding": "gzip" } : { "Content-Length": file.size }),
  });
  if (req.method === "HEAD") res.end();
  else if (gzip) createReadStream(file.path).pipe(createGzip()).pipe(res);
  else createReadStream(file.path).pipe(res);
}).listen(PORT, "0.0.0.0", () => console.log(`serving ${ROOT} on :${PORT}`));
