import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import path from "node:path";

// Static SPA build. No server-side runtime; the frontend talks only to the
// configured Governance Studio API over HTTP. Deterministic asset names where
// practical are handled by Vite's content hashing.
export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: { "@": path.resolve(__dirname, "src") },
  },
  build: {
    outDir: "dist",
    sourcemap: false, // production source maps are intentionally OFF (documented, FRONTEND_SECURITY.md)
    chunkSizeWarningLimit: 900,
  },
  server: { host: "127.0.0.1", port: 5173 },
});
