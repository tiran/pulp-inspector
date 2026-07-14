import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  build: {
    outDir: "../src/pulp_inspector/static",
    emptyOutDir: true,
    rollupOptions: {
      output: {
        manualChunks: {
          patternfly: [
            "@patternfly/react-core",
            "@patternfly/react-table",
            "@patternfly/react-icons",
          ],
          react: ["react", "react-dom", "react-router-dom"],
        },
      },
    },
  },
  server: {
    port: 5173,
    proxy: {
      "/api": {
        target: "http://localhost:8080",
        changeOrigin: true,
      },
    },
  },
});
