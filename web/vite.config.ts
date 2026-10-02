import { defineConfig } from "vitest/config";
import { VitePWA } from "vite-plugin-pwa";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = dirname(fileURLToPath(import.meta.url));
const repoRoot = resolve(__dirname, "..");

export default defineConfig({
  base: "./",
  server: {
    fs: {
      // Allow importing lexicon SoT from config/ (Issue #90; Zero-Dataset).
      allow: [repoRoot],
    },
  },
  plugins: [
    VitePWA({
      registerType: "autoUpdate",
      minify: false,
      includeAssets: [
        "icons/icon.svg",
        "data/**/*",
        "tessdata/**/*",
        "tesseract/**/*",
      ],
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
        globPatterns: [
          "**/*.{js,css,html,svg,wasm,parquet,json,ico,mjs}",
          "tessdata/**/*.gz",
          "tesseract/**/*",
        ],
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
