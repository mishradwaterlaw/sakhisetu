import { fileURLToPath, URL } from "node:url";
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

export default defineConfig({
  resolve: { alias: { "@": fileURLToPath(new URL("./src", import.meta.url)) } },
  plugins: [react(), tailwindcss()],
  build: {
    rollupOptions: {
      output: {
        manualChunks(id) {
          if (/node_modules\/(react|react-dom|scheduler)\//.test(id)) return "react-runtime";
          if (id.includes("/node_modules/recharts/")) return "charts";
        },
      },
    },
  },
  server: {
    port: 5173,
    proxy: {
      "/api": process.env.SAKHI_API_PROXY || "http://localhost:8000",
    },
  },
});
