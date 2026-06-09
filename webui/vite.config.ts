import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { resolve } from "node:path";

// https://vite.dev/config/
export default defineConfig({
  // Use relative URLs so the same build works at / and /qbitrr.
  base: "./",
  plugins: [react()],
  server: {
    fs: {
      allow: [resolve(__dirname, "..")],
    },
    proxy: {
      "/web": "http://127.0.0.1:6969",
      "/api": "http://127.0.0.1:6969",
      "/ui": "http://127.0.0.1:6969",
      "/static": "http://127.0.0.1:6969",
      "/sw.js": "http://127.0.0.1:6969",
      "/login": "http://127.0.0.1:6969",
      "/health": "http://127.0.0.1:6969",
    },
  },
  build: {
    outDir: resolve(__dirname, "../qBitrr/static"),
    emptyOutDir: true,
    sourcemap: true,
    chunkSizeWarningLimit: 1000,
  },
});
