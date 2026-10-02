# Gate A Priority 1 (Issue #58) — WASM / Vitest harness

**Canonical implementation:** `web/src/benchmarks/` (TypeScript).

```bash
cd web
npm install
npm run gate-a
# or: npm test
```

Zero-tolerance (must pass):

- Critical FA = 0 (`evaluateA1A2Synthetic` / pipeline)
- Rule D5 reconciliation error = 0 JPY (`evaluateA3RuleD5Synthetic` + `evaluateA3RuleD5Pipeline`)

PDF-free lite report: `runGateAPriority1Lite()` in [`web/src/benchmarks/gateAPriority1.ts`](../web/src/benchmarks/gateAPriority1.ts).

Also covered in the WASM path:

- **A4** exact-span grounding (`web/src/pipeline/spanValidate.ts`) on in-memory fixtures; Issue #88 extends the same gate to COLREGS / PSC / Rule D5 runners ([exact_span_grounding.md](exact_span_grounding.md))
- **A8** Field3 MAPE (`web/src/benchmarks/verify3Fields.ts`) with yard tolerance 1.03

The former Python Gate A harness was removed; use Vitest only.
