import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    port: 5174,
    proxy: {
      "/api/buyer": process.env.SAKHI_API_PROXY || "http://localhost:8000",
      "/api/bootstrap": process.env.SAKHI_API_PROXY || "http://localhost:8000",
    },
  },
});
