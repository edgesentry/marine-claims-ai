#!/usr/bin/env node
/**
 * Export Stage A ExtractionResult JSON Schemas to docs/schemas/ (Issue #87 / #71 align).
 */
import { mkdirSync, writeFileSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { createServer } from "vite";

const __dirname = dirname(fileURLToPath(import.meta.url));
const webRoot = resolve(__dirname, "..");
const repoRoot = resolve(webRoot, "..");
const outDir = join(repoRoot, "docs", "schemas");

async function main() {
  const server = await createServer({
    root: webRoot,
    configFile: false,
    logLevel: "error",
    server: { middlewareMode: true },
    appType: "custom",
    optimizeDeps: { noDiscovery: true, include: [] },
  });

  const mod = await server.ssrLoadModule("/src/schemas/jsonSchema.ts");
  const {
    allSchemaIds,
    extractionJsonSchema,
    allExtractionJsonSchema,
    guidedDecodeSpec,
  } = mod;

  mkdirSync(outDir, { recursive: true });

  /** @type {Record<string, unknown>} */
  const index = {
    description:
      "Stage A ExtractionResult contracts shared by Tier 1–3 (Issue #87). " +
      "Invalid envelopes must not reach Rule D5 / COLREGS / PSC scorers.",
    schema_ids: [...allSchemaIds()],
    files: {},
  };

  for (const id of allSchemaIds()) {
    const schema = extractionJsonSchema(id);
    const fileName = `${id}.json`;
    writeFileSync(join(outDir, fileName), JSON.stringify(schema, null, 2) + "\n");
    const spec = guidedDecodeSpec(id);
    index.files[id] = {
      json_schema: fileName,
      system_hint: spec.system_hint,
    };
  }

  writeFileSync(
    join(outDir, "extraction_result.v1.json"),
    JSON.stringify(allExtractionJsonSchema(), null, 2) + "\n",
  );
  writeFileSync(join(outDir, "index.json"), JSON.stringify(index, null, 2) + "\n");

  console.log(`Wrote Stage A schemas to ${outDir}`);

  // Hard-exit after successful write to avoid Vite middlewareMode teardown races.
  process.exit(0);
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
