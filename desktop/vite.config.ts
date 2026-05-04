import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Tauri 2 expects the dev server on a fixed port so the Rust shell can attach
// to it. 5173 is the Tauri default.
export default defineConfig({
  plugins: [react()],
  clearScreen: false,
  server: {
    port: 5173,
    strictPort: true,
    host: "127.0.0.1",
  },
  build: {
    target: "es2021",
    sourcemap: true,
  },
  envPrefix: ["VITE_", "TAURI_ENV_"],
});
