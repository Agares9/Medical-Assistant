import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      "/api": "http://127.0.0.1:7864",
      "/icon.png": "http://127.0.0.1:7864"
    }
  },
  build: {
    outDir: "dist",
    emptyOutDir: true
  }
});
