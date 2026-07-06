/**
 * seat-predictor 서비스 워커 — PWA 오프라인 지원.
 *
 * - 앱 셸(HTML/CSS/JS/아이콘)은 설치 시 프리캐시.
 * - HTML 탐색 요청은 network-first (배포 후 새 버전을 바로 받기 위해),
 *   오프라인이면 캐시된 셸로 폴백.
 * - 그 외 GET(Plotly CDN 포함)은 cache-first + 백그라운드 갱신.
 * - 서울시 API(openapi.seoul.go.kr)는 데이터 신선도를 위해 관여하지 않음
 *   (앱 레벨에서 이미 localStorage로 캐시함).
 */
const CACHE_NAME = "seat-predictor-v2";

const PRECACHE_URLS = [
  "./",
  "./index.html",
  "./style.css",
  "./app.js",
  "./seoul_api.js",
  "./manifest.webmanifest",
  "./icons/icon-192.png",
  "./icons/icon-512.png",
  "./icons/icon-maskable-512.png",
  "./icons/apple-touch-icon.png",
];

// CDN이 일시적으로 안 되더라도 SW 설치 자체는 막지 않는다
// (fetch 핸들러의 stale-while-revalidate가 나중에 캐시해 줌)
const OPTIONAL_PRECACHE_URLS = [
  "https://cdn.plot.ly/plotly-2.35.2.min.js",
  "https://cdn.jsdelivr.net/gh/orioncactus/pretendard@v1.3.9/dist/web/variable/pretendardvariable-dynamic-subset.min.css",
];

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches
      .open(CACHE_NAME)
      .then((cache) =>
        Promise.all([
          cache.addAll(PRECACHE_URLS),
          ...OPTIONAL_PRECACHE_URLS.map((url) => cache.add(url).catch(() => {})),
        ])
      )
      .then(() => self.skipWaiting())
  );
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches
      .keys()
      .then((keys) =>
        Promise.all(keys.filter((k) => k !== CACHE_NAME).map((k) => caches.delete(k)))
      )
      .then(() => self.clients.claim())
  );
});

self.addEventListener("fetch", (event) => {
  const request = event.request;
  if (request.method !== "GET") return;

  const url = new URL(request.url);
  if (url.hostname === "openapi.seoul.go.kr") return; // 실데이터 API는 그대로 통과

  // 페이지 탐색: network-first, 실패 시 캐시된 셸
  if (request.mode === "navigate") {
    event.respondWith(
      fetch(request)
        .then((resp) => {
          const copy = resp.clone();
          caches.open(CACHE_NAME).then((cache) => cache.put(request, copy));
          return resp;
        })
        .catch(() => caches.match(request).then((c) => c || caches.match("./index.html")))
    );
    return;
  }

  // 정적 자원: cache-first + 백그라운드 갱신 (stale-while-revalidate)
  event.respondWith(
    caches.match(request).then((cached) => {
      const network = fetch(request)
        .then((resp) => {
          if (resp.ok || resp.type === "opaque") {
            const copy = resp.clone();
            caches.open(CACHE_NAME).then((cache) => cache.put(request, copy));
          }
          return resp;
        })
        .catch(() => cached);
      return cached || network;
    })
  );
});
