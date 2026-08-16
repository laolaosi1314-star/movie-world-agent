import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// 前端开发服务器。后端默认运行在 http://localhost:8000（uvicorn）。
// 生产环境请用 VITE_API_BASE 指向真实域名；H5 跨域需后端 CORS_ALLOW_ORIGINS 放行。
export default defineConfig({
  base: "./",
  plugins: [react()],
  server: {
    port: 5173,
    // 可选：把 /worlds 代理到后端，避免 CORS（开发期也可用 * 放开）。
    // proxy: { "/worlds": { target: "http://localhost:8000", changeOrigin: true } },
  },
});
