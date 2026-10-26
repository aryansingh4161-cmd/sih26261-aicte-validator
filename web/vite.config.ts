import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react";

// Live mode proxies /api to the FastAPI server (uvicorn api.main:app --port 8600).
// Demo mode (npm run build:demo) reads the static snapshot in public/snapshot; BASE_PATH sets the GitHub Pages sub-path.
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), "");
  return {
    base: env.BASE_PATH || "/",
    plugins: [react()],
    server: { port: 5173, proxy: { "/api": "http://127.0.0.1:8600" } },
    build: { outDir: "dist", sourcemap: false },
  };
});
