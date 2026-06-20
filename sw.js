/* HOT 스포츠 쇼츠 — 서비스워커 (오프라인 최소 캐시)
   ───────────────────────────────────────────────
   ▸ 앱 껍데기(화면·아이콘)만 캐시해서 오프라인에서도 화면이 뜨게 합니다.
   ▸ data.json(골 목록)은 절대 캐시하지 않습니다 → 항상 최신.
   ▸ 화면(index.html)은 '인터넷 먼저' 방식 → 새로 배포하면 바로 반영됩니다.
   ▸ 코드를 고쳐 새로 올릴 때는 아래 CACHE 끝 숫자를 v2, v3 … 로 올리세요.
     (그래야 옛 화면을 붙잡지 않습니다)
*/
const CACHE = 'hot-sports-v3';
const SHELL = [
  './',
  './index.html',
  './manifest.webmanifest',
  './icons/icon-192.png',
  './icons/icon-512.png',
  './icons/maskable-192.png',
  './icons/maskable-512.png',
  './icons/apple-touch-icon.png'
];

self.addEventListener('install', (e) => {
  e.waitUntil(
    caches.open(CACHE).then((c) => c.addAll(SHELL)).then(() => self.skipWaiting())
  );
});

self.addEventListener('activate', (e) => {
  e.waitUntil(
    caches.keys()
      .then((keys) => Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k))))
      .then(() => self.clients.claim())
  );
});

self.addEventListener('fetch', (e) => {
  const req = e.request;
  const url = new URL(req.url);

  // 우리 사이트(같은 출처)의 GET 요청만 다룸. 유튜브·썸네일 등 외부는 건드리지 않음.
  if (req.method !== 'GET' || url.origin !== location.origin) return;

  // data.json: 항상 인터넷에서 새로(캐시 안 함). 오프라인이면 마지막 응답이라도.
  if (url.pathname.endsWith('data.json')) {
    e.respondWith(fetch(req).catch(() => caches.match(req)));
    return;
  }

  // 화면(이동/네비게이션 또는 index.html): 인터넷 먼저, 실패 시 캐시.
  if (req.mode === 'navigate' || url.pathname.endsWith('/') || url.pathname.endsWith('index.html')) {
    e.respondWith(
      fetch(req).then((r) => {
        const cp = r.clone();
        caches.open(CACHE).then((c) => c.put('./index.html', cp));
        return r;
      }).catch(() => caches.match(req).then((m) => m || caches.match('./index.html')))
    );
    return;
  }

  // 그 외 정적 파일(아이콘 등): 캐시 먼저, 없으면 인터넷.
  e.respondWith(
    caches.match(req).then((m) => m || fetch(req).then((r) => {
      const cp = r.clone();
      caches.open(CACHE).then((c) => c.put(req, cp));
      return r;
    }))
  );
});
