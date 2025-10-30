import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { resolve } from "node:path";

// https://vite.dev/config/
export default defineConfig({
  base: "/static/",
  plugins: [react()],
  build: {
    outDir: resolve(__dirname, "../qBitrr/static"),
    emptyOutDir: true,
    sourcemap: true,
    chunkSizeWarningLimit: 1000,
    rollupOptions: {
      output: {
        entryFileNames: "assets/app.js",
        chunkFileNames: "assets/[name].js",
        assetFileNames: ({ name }) => {
          if (name && name.endsWith(".css")) {
            return "assets/app.css";
          }
          if (name && name.endsWith(".js.map")) {
            return "assets/app.js.map";
          }
          return "assets/[name][extname]";
        },
        manualChunks: {
          vendor: ['react', 'react-dom'],
          mantine: ['@mantine/core', '@mantine/hooks', '@mantine/dates'],
          table: ['@tanstack/react-table'],
          syntax: ['react-syntax-highlighter'],
        },
      },
    },
  },
});
