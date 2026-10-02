# Exact Span grounding (Issue #88)

Stage A extractors turn messy documents into UC-fixed `ExtractionResult` envelopes ([schemas](schemas/README.md), Issue #87). **Exact Span** is the next gate: critical fields may reach Stage B only when their values are grounded in source text (and optionally a PDF page bbox), or when the caller explicitly opts into paste mode.

| Layer | Guarantees |
| :--- | :--- |
| **#87 shape** | Envelope matches Zod / JSON Schema (`assertValidForStageB`) |
| **#88 grounding** | Critical `source_quote`s exist (and match source when provided) unless `paste_bypass` |

Without Exact Span, a well-formed envelope can still carry fabricated repair lines, judgment excerpts, or PSC codes into Rule D5 / COLREGS / PSC scorers. Claims demos then look “correct” while provenance is missing, and CI cannot gate ungrounded / fabricated rates.

## Flow

```text
PDF / OCR / heuristics
        │
        ▼
Exact Span (findGroundedQuote) ──reject──► discarded (ungrounded)
        │
        ▼
ExtractionResult.grounding[]  (+ page_number / pdf_coordinates when available)
        │
        ▼
assertValidForStageB  →  assertGroundingForStageB
        │                      │
        │                      ├─ require_span (default for document paths)
        │                      └─ paste_bypass (hand-pasted JSON / fixtures / synthetic UI)
        ▼
Stage B scorers
```

## Modes

| `groundingMode` | When |
| :--- | :--- |
| `require_span` | PDF / OCR / document extract paths. Critical fields need `grounding[].source_quote`; if `sourceText` is passed, quotes must appear in that text (NFKC + whitespace-normalized match). |
| `paste_bypass` | PSC paste JSON/CSV, PSC fixtures, synthetic Rule D5 UI, catalog COLREGS without a source document. **Must be set explicitly** on the runner / adapter. |

Mode lives on runner / `build*Extraction` options (not on the published envelope) so #87 contracts stay stable.

## Critical fields by UC

| `schema_id` | Required grounding fields |
| :--- | :--- |
| `rule_d5.v1` | `lines.pdf-*` (PDF-derived ids). Synthetic injects (`dock-1`, `hull-1`, …) are not Exact-Span critical. |
| `colregs.v1` | `facts_excerpt` / `ruling_excerpt` when present; telemetry fields (`geometry.*`) when those grounding entries exist (#91). Slider-only geometry with no excerpts is allowed with empty grounding. |
| `psc.v1` | `deficiencies.{i}.code` for each row — unless `paste_bypass`. PDF/OCR path lands in #92 on top of this gate. |

## Envelope fields

Each `grounding[]` entry:

| Field | Role |
| :--- | :--- |
| `field` | Payload path (e.g. `facts_excerpt`, `lines.pdf-1`) |
| `source_quote` | Contiguous span from the source (required, min length 1) |
| `page_number` | 1-based page when known |
| `pdf_coordinates` | `{ page, x0, y0, x1, y1 }` from the PDF text layer (or later OCR). `null` when unknown |

## Implementation map

| Piece | Path |
| :--- | :--- |
| Span match | `web/src/pipeline/spanValidate.ts` |
| Grounding gate | `web/src/pipeline/groundingGate.ts` |
| Repair-spec Exact Span | `web/src/pipeline/extractSpec.ts` |
| Quote → page/bbox | `web/src/pipeline/pdfLocate.ts` |
| pdf.js text + bbox | `web/src/pdf/parseTender.ts` (`extractPdfContent`) |
| Runners | `web/src/core/{ruleD5,colregs,psc}.ts` |
| Adapters | `web/src/schemas/adapters.ts` |

## Tests / CI

```bash
cd web
npm test
npm run gate-a   # includes tests/groundingGate.test.ts + span A4
```

Expectations covered in Vitest:

- Ungrounded COLREGS / Rule D5 / PSC candidates → reject
- Grounded quotes → accept and attach `grounding`
- PSC paste / fixtures → accept only with `paste_bypass`
- Optional bbox attachment when `pdfContent` is supplied

## Follow-ons

| Issue | Adds |
| :--- | :--- |
| #91 | COLREGS telemetry extraction (headings / bearings) — must carry grounding |
| #92 | PSC MOU PDF/HTML/image → deficiencies under `require_span` |
| #45 / #94 | OCR bboxes into the same `pdf_coordinates` shape |
| #93 | Broader Stage A eval harness / ungrounded-rate gates across corpora |
