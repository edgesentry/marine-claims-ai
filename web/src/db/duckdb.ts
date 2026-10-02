/**
 * Browser DuckDB-WASM bootstrap (local WASM/worker — no CDN fetch at runtime).
 */
import * as duckdb from "@duckdb/duckdb-wasm";

export type DuckConn = duckdb.AsyncDuckDBConnection;

let dbPromise: Promise<duckdb.AsyncDuckDB> | null = null;

export async function getDuckDb(): Promise<duckdb.AsyncDuckDB> {
  if (!dbPromise) {
    dbPromise = (async () => {
      const workerUrl = (
        await import("@duckdb/duckdb-wasm/dist/duckdb-browser-eh.worker.js?url")
      ).default;
      const wasmUrl = (await import("@duckdb/duckdb-wasm/dist/duckdb-eh.wasm?url")).default;
      const logger = new duckdb.ConsoleLogger(duckdb.LogLevel.WARNING);
      const worker = new Worker(workerUrl, { type: "module" });
      const db = new duckdb.AsyncDuckDB(logger, worker);
      await db.instantiate(wasmUrl);
      return db;
    })();
  }
  return dbPromise;
}

export async function withConnection<T>(fn: (conn: DuckConn) => Promise<T>): Promise<T> {
  const db = await getDuckDb();
  const conn = await db.connect();
  try {
    return await fn(conn);
  } finally {
    await conn.close();
  }
}

/** Resolve a public/ asset URL that works under Vite base `./`. */
export function dataUrl(name: string): string {
  const base = import.meta.env.BASE_URL || "./";
  return `${base}data/${name}`.replace(/\/{2,}/g, "/").replace(":/", "://");
}
