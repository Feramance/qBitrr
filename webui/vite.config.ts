import { defineConfig, type Plugin } from "vite";
import react from "@vitejs/plugin-react";
import { createHash } from "node:crypto";
import { readFileSync, writeFileSync, existsSync } from "node:fs";
import { resolve } from "node:path";

const SW_VERSION_PLACEHOLDER = "__QBITRR_CACHE_VERSION__";

function resolveCacheVersion(): string {
  // Prefer packaged app version + short content hash so SW updates track deploys.
  let packageVersion = "0.0.0";
  try {
    const pkg = JSON.parse(readFileSync(resolve(__dirname, "package.json"), "utf8")) as {
      version?: string;
    };
    if (pkg.version) {
      packageVersion = pkg.version;
    }
  } catch {
    // ignore
  }
  try {
    const setup = readFileSync(resolve(__dirname, "../setup.cfg"), "utf8");
    const match = setup.match(/^version\s*=\s*(.+)$/m);
    if (match?.[1]?.trim()) {
      packageVersion = match[1].trim();
    }
  } catch {
    // ignore
  }
  const stamp = createHash("sha256")
    .update(`${packageVersion}:${process.env.GITHUB_SHA ?? process.env.SOURCE_DATE_EPOCH ?? "dev"}`)
    .digest("hex")
    .slice(0, 10);
  return `${packageVersion}-${stamp}`;
}

function injectServiceWorkerCacheVersion(): Plugin {
  const cacheVersion = resolveCacheVersion();

  const rewriteSw = (filePath: string): void => {
    if (!existsSync(filePath)) {
      return;
    }
    const source = readFileSync(filePath, "utf8");
    if (!source.includes(SW_VERSION_PLACEHOLDER)) {
      return;
    }
    writeFileSync(filePath, source.replaceAll(SW_VERSION_PLACEHOLDER, cacheVersion), "utf8");
  };

  return {
    name: "inject-sw-cache-version",
    apply: "build",
    closeBundle() {
      rewriteSw(resolve(__dirname, "../qBitrr/static/sw.js"));
    },
  };
}

// https://vite.dev/config/
export default defineConfig({
  // Use relative URLs so the same build works at / and /qbitrr.
  base: "./",
  plugins: [react(), injectServiceWorkerCacheVersion()],
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
    sourcemap: false,
    chunkSizeWarningLimit: 600,
    rollupOptions: {
      output: {
        manualChunks(id: string): string | undefined {
          if (id.includes("node_modules/react-dom") || id.includes("node_modules/react/")) {
            return "react";
          }
          if (id.includes("node_modules/react-select")) {
            return "react-select";
          }
          if (id.includes("node_modules/@tanstack/react-table")) {
            return "table";
          }
          return undefined;
        },
      },
    },
  },
});
