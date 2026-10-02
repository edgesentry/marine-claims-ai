# Stage A ExtractionResult JSON Schemas

Published contracts for Issue #87 (aligned with open schema work in #71).

| File | `schema_id` |
| :--- | :--- |
| `rule_d5.v1.json` | Rule D5 repair lines + docking context |
| `colregs.v1.json` | COLREGS geometry + narrative excerpts |
| `psc.v1.json` | PSC deficiencies (+ optional priors) |
| `extraction_result.v1.json` | Discriminated union of all envelopes |
| `index.json` | Catalog + guided-decode system hints |

Source of truth: Zod schemas in `web/src/schemas/`. Regenerate:

```bash
cd web && npm run build:schemas
```

Invalid envelopes must not reach Stage B scorers.
