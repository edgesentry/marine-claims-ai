# Confidence scoring and HUMAN_REVIEW abstention (Issue #89)

Stage A extractors emit UC-fixed `ExtractionResult` envelopes ([schemas](schemas/README.md), Issues #87 / #88). **Confidence abstention** is the next safety rail: when document- or field-level confidence is below engineering thresholds, Stage B scorers must not run until a human confirms or edits the structured fields.

| Layer | Guarantees |
| :--- | :--- |
| **#87 shape** | Envelope matches Zod / JSON Schema (`assertValidForStageB`) |
| **#88 grounding** | Critical `source_quote`s exist (unless `paste_bypass`) |
| **#89 confidence** | Document / field confidence meets thresholds, or `HUMAN_REVIEW_REQUIRED` abstains Stage B |

Abstention is an **engineering safety rail**, not a legal opinion, warranty finding, or statutory determination.

## Try it in the PWA

```bash
cd web && npm run build && npm run preview
# open http://127.0.0.1:4173/
```

If an older Service Worker is serving a stale bundle, hard-reload or unregister the SW once after upgrading.

| Tab | What to upload | Hard-coded Stage A `confidence` | Expected UI |
| :--- | :--- | :--- | :--- |
| **1. Rule D5** | Drydock / repair-spec PDF (text layer; lines with yen amounts) | `0.65` (`< document_min 0.70`) | Right panel: `HUMAN_REVIEW_REQUIRED` + editable lines + **Confirm & score**. No Rule D5 split until confirm. |
| **2. COLREGS** | Judgment / JTSB-style narrative PDF (facts / ruling extractable) | `0.55` | Same abstention panel for geometry + excerpts; Confirm & score then classifies. |
| **3. PSC** | — | fixtures / paste use `bypass` | Auto-scores (no abstention on the default path). |

### Does not abstain

- Rule D5 **Use synthetic demo lines** (`confidence` 0.85, `bypass`)
- COLREGS catalog cases (not `case_id: upload`)
- PSC fixtures and pasted JSON/CSV

### Local PDFs (gitignored Zero-Dataset caches — never commit)

After `scripts/fetch_public_datasets.py` (or an existing `_inputs/` / `_data/` cache):

| Path (examples) | Use on tab |
| :--- | :--- |
| `_inputs/poc_datasets/fukuoka_kaiyomaru_spec.pdf` (or `_data/poc_datasets/…`) | Rule D5 |
| `_inputs/poc_datasets/jtsb_cargo_collision_report.pdf` / other `jtsb_*.pdf` | COLREGS |

Image-only PDFs fail earlier (“no text extracted”) and never reach the confidence gate. Repair specs need extractable cost lines; otherwise the UI reports “no repair line items”.

After **Confirm & score**, Stage B runs with `confidenceMode: "confirmed"`.

## Engineering defaults (not statutory)

| Knob | Default | Notes |
| :--- | :--- | :--- |
| `document_min` | `0.70` | Document-level `confidence` must be ≥ this under `enforce` |
| `field_min` | `0.60` | Critical fields with `field_confidence` entries must be ≥ this |
| Config | [`web/src/config/confidenceThresholds.ts`](../web/src/config/confidenceThresholds.ts) | Overridable per `schema_id` |

These cut-offs exist for demo / CI clarity. They are **not** statutory warranty or COLREGS thresholds.

## Modes

| `confidenceMode` | When |
| :--- | :--- |
| `enforce` | Default for document / `require_span` paths (PDF upload). Low confidence → stamp `abstain` and skip scorers. |
| `confirmed` | After PWA **Confirm & score** (human reviewed / edited fields). |
| `bypass` | Default when `groundingMode` is `paste_bypass` (synthetic UI, PSC paste, fixtures). |

Mode lives on runner / `build*Extraction` options (not on the published envelope).

## Flow

```text
PDF / OCR / heuristics
        │
        ▼
assertValidForStageB  →  assertGroundingForStageB  →  applyConfidenceGate
        │                        │                         │
        │                        │                         ├─ ok → Stage B scorers
        │                        │                         └─ abstain → HUMAN_REVIEW_REQUIRED
        │                        │                              │
        │                        │                              ▼
        │                        │                         PWA review panel
        │                        │                              │
        │                        │                         Confirm & score (confirmed)
        │                        │                              │
        │                        │                              ▼
        │                        │                         Stage B scorers
```

## Envelope fields

| Field | Role |
| :--- | :--- |
| `confidence` | Document-level score in `[0, 1]` |
| `field_confidence` | Optional map of payload path → `[0, 1]` |
| `abstain` | Optional `{ code: "HUMAN_REVIEW_REQUIRED", reason }` — Stage A shape stays valid; Stage B must not run under `enforce` |

## Logging (Zero-Dataset)

`logAbstain` emits structured console info with **reason codes**, `schema_id`, and numeric confidence only. It must never log `source_quote`, PDF text, or other Zero-Dataset content.

## Implementation map

| Piece | Path |
| :--- | :--- |
| Thresholds | `web/src/config/confidenceThresholds.ts` |
| Confidence gate | `web/src/pipeline/confidenceGate.ts` |
| Adapters | `web/src/schemas/adapters.ts` |
| Runners | `web/src/core/{ruleD5,colregs,psc}.ts` |
| PWA review UI | `web/src/main.ts`, `web/src/i18n.ts` |

## Tests / CI

```bash
cd web
npm test
npm run gate-a   # includes tests/confidenceGate.test.ts + tests/issue89DoD.test.ts
```
