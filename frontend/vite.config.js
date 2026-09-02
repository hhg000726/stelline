import { rmSync } from "node:fs";
import { resolve } from "node:path";

import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

const OUT_DIR = resolve(import.meta.dirname, "../stelline/static");
const BUNDLE_DIR = resolve(OUT_DIR, "app");

/* 지난 빌드의 조각을 지운다.
 *
 * 파일 이름에 해시가 붙어 있어 빌드할 때마다 새 이름이 나온다. outDir 를 통째로
 * 비울 수는 없으므로(같은 폴더에 파비콘·안내 그림 등이 함께 있다) 번들 폴더만 지운다.
 * 그러지 않으면 저장소에 쓰지 않는 파일이 계속 쌓인다.
 */
function cleanBundleDir() {
  return {
    name: "stelline-clean-bundle-dir",
    apply: "build",
    buildStart() {
      rmSync(BUNDLE_DIR, { recursive: true, force: true });
    },
  };
}

/* 빌드 결과는 Flask 가 그대로 내려주는 stelline/static 아래에 놓는다.
 *
 * - outDir 를 비우지 않는다(emptyOutDir: false). 같은 폴더에 파비콘·og 이미지·
 *   검색 안내 그림·firebase-messaging-sw.js 처럼 빌드와 무관한 파일이 함께 있고,
 *   그림 주소는 관리자 콘텐츠 기본값(/search/1.PNG 등)으로도 쓰여 옮길 수 없다.
 * - 번들은 app/ 아래로 모은다. 서버가 그리는 관리자 화면이 쓰는 assets/ 와 겹치지 않는다.
 * - 서버는 Python 패키지만 있으면 되도록 빌드 산출물을 저장소에 커밋한다.
 */
export default defineConfig({
  plugins: [react(), cleanBundleDir()],
  publicDir: false,
  build: {
    outDir: OUT_DIR,
    emptyOutDir: false,
    assetsDir: "app",
    sourcemap: false,
    rollupOptions: {
      output: {
        // 해시가 없으면 배포한 뒤에도 옛 파일이 캐시된다.
        entryFileNames: "app/[name]-[hash].js",
        chunkFileNames: "app/[name]-[hash].js",
        assetFileNames: "app/[name]-[hash][extname]",
      },
    },
  },
  server: {
    port: 5173,
    /* 개발 중에는 API 와, 빌드에 들어가지 않는 정적 파일(파비콘·안내 그림 등)을
       Flask 개발 서버로 넘긴다. 관리자·로그인 화면도 그쪽이 그린다. */
    proxy: Object.fromEntries(
      [
        "/api",
        "/admin",
        "/auth",
        "/assets",
        "/search/1",
        "/search/2",
        "/search/3",
        "/search/4",
        "/favicon.svg",
        "/favicon.ico",
        "/favicon.png",
        "/apple-touch-icon.png",
        "/og-image.png",
        "/firebase-messaging-sw.js",
      ].map((path) => [path, "http://127.0.0.1:5000"]),
    ),
  },
});
