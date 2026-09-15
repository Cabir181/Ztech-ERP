import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

/**
 * The interface is served from the same origin as the API in every deployed
 * environment. In development the Vite server proxies /api to Django so the
 * browser still sees a single origin and the session/CSRF cookie pair keeps
 * working exactly as it does in production.
 */
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    strictPort: true,
    proxy: {
      "/api": {
        target: process.env.VITE_API_TARGET ?? "http://127.0.0.1:8000",
        changeOrigin: false,
      },
    },
  },
  build: {
    outDir: "dist",
    sourcemap: true,
    // Assets are content-hashed, so they can be cached indefinitely while
    // index.html is served with no-store.
    assetsDir: "assets",
  },
});
