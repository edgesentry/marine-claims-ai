import { defineConfig } from "vitest/config";
import { VitePWA } from "vite-plugin-pwa";

export default defineConfig({
  base: "./",
  plugins: [
    VitePWA({
      registerType: "autoUpdate",
      minify: false,
      includeAssets: ["icons/icon.svg", "data/**/*"],
      manifest: {
        name: "MarineClaims AI — Executive Demo",
        short_name: "MarineClaims",
        description:
          "Offline Rule D5 / COLREGS / PSC claims appraisal suite (client-side WASM)",
        theme_color: "#0b1c2c",
        background_color: "#0b1c2c",
        display: "standalone",
        start_url: "./",
        icons: [
          {
            src: "icons/icon.svg",
            sizes: "any",
            type: "image/svg+xml",
            purpose: "any maskable",
          },
        ],
      },
      workbox: {
        globPatterns: ["**/*.{js,css,html,svg,wasm,parquet,json,ico,mjs}"],
        maximumFileSizeToCacheInBytes: 40 * 1024 * 1024,
        mode: "development",
      },
    }),
  ],
  worker: {
    format: "es",
  },
  optimizeDeps: {
    exclude: ["@duckdb/duckdb-wasm"],
  },
  test: {
    environment: "node",
    include: ["tests/**/*.test.ts"],
  },
});
