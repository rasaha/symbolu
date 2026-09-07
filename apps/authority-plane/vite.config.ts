import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import path from "node:path";

// The authority plane is its own deployable (AP-2). It talks to the governed runtime
// worker's private TLS listener (default 127.0.0.1:8444), proxied under /api in dev.
// The worker's certificate is private, so the dev proxy does not verify it; a
// production front must sit inside the same private segment (CR-3).
export default defineConfig({
  plugins: [react()],
  resolve: { alias: { "@": path.resolve(__dirname, "src") } },
  build: { outDir: "dist", sourcemap: false },
  server: {
    host: "127.0.0.1",
    port: 3200,
    proxy: {
      "/api": {
        target: process.env.WORKER_URL || "https://127.0.0.1:8444",
        changeOrigin: true,
        secure: false,
        rewrite: (p) => p.replace(/^\/api/, ""),
      },
    },
  },
});
