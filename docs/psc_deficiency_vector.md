# PSC Deficiency Vector: Taxonomy & Seaworthiness Scoring

This document records the **Port State Control deficiency taxonomy and action codes** that bound GitHub Issue [#31](https://github.com/edgesentry/marine-claims-AI/issues/31) (Paris & Tokyo MOU Statutory Deficiency Vector Parser for Seaworthiness Scoring), and maps each clause to the open-core implementation after verification against public primary texts.

Related docs: [Symbolic AI Implementation Framework](symbolic_ai_implementation_framework.md) · [R&D Roadmap](research_and_development_roadmap.md) Stage 1 · [Public Benchmarks & Accuracy Evaluation](public_benchmarks_and_accuracy_evaluation.md) §5 · [Technical Stack](technical_stack.md).

Local primary-text cache (gitignored): `_inputs/psc/` — see [`_inputs/psc/SOURCES.md`](../_inputs/psc/SOURCES.md).

---

## 1. Scope of Issue #31

Issue #31 asks for a normalized parser and risk scoring engine over Tokyo MOU / Paris MOU deficiency records so claims pipelines can screen for latent breaches of statutory safety conventions and the Marine Insurance Warranty of Seaworthiness **before** casualty appraisal.

| In scope | Out of scope (this issue) |
| :--- | :--- |
| IMO / MOU **5-digit deficiency** normalization + convention mapping | Live THETIS / APCIS scraping of identifiable vessel inspections |
| Action-code severity (`15`/`16`/`17`/`30`) and compound Defect Score | Flag White/Grey/Black WGB statistics (existing Field 2) |
| Repeat-deficiency flags for critical systems | Full SOLAS/MARPOL treaty text ingestion |
| Modular CIC / regional weight injection | Rewriting Japan Art. 815 / UK MIA 1906 warranty doctrine in the core |
| Unit tests on anonymized Paris/Tokyo-style fixtures | Committing raw MOU PDFs or identifiable PSC dossiers |

**Architecture boundary.** Taxonomy constants and Defect Score live in Universal Open Core (`ontology/psc.py`, `ingest/psc_deficiencies.py`). Jurisdiction warranty thresholds (Art. 815 vs MIA s.39 privity) stay in Modular Jurisdiction Adapters (`evaluate_seaworthiness_warranty`).

---

## 2. Controlling primary sources (fetched 2026-09-27)

| Instrument | Public URL | Local cache | Role for #31 |
| :--- | :--- | :--- | :--- |
| IMO A.1155(32) Procedures for PSC, 2021 | [A.1155(32).pdf](https://wwwcdn.imo.org/localresources/en/KnowledgeCentre/IndexofIMOResolutions/AssemblyDocuments/A.1155(32).pdf) | `IMO_A.1155_32_Procedures_for_PSC_2021.pdf` | Detention definition; detainable examples by convention; report forms |
| Tokyo MOU Deficiency Codes (July 2026) | [Tokyo-MOU-deficiency-codes-July-2026.pdf](https://www.tokyo-mou.org/wp/wp-content/uploads/Tokyo-MOU-deficiency-codes-July-2026.pdf) | `Tokyo_MOU_deficiency_codes_July_2026.pdf` | **Controlling 5-digit taxonomy (Tokyo)** |
| Paris MoU Deficiency Codes (01-07-2026) | [parismou.org/download/2556/](https://parismou.org/download/2556/) | `Paris_MOU_List_of_Deficiency_Codes_01-07-2026.pdf` | **Controlling 5-digit taxonomy (Paris)** + statutory certificate matrix |
| Paris PSCC59 Guidelines on detention and action taken | [pscc59-2026-03-…](https://parismou.org/download/pscc59-2026-03-guidelines-on-detention-and-action-taken/) | `Paris_MOU_PSCC59_Guidelines_detention_and_action_taken.pdf` | Action codes `15`/`16`/`17` (and ISM `19`/`21`) |
| Tokyo Flag performance list 2025 | [Flag-performance-list-2025.pdf](https://www.tokyo-mou.org/wp/wp-content/uploads/Flag-performance-list-2025.pdf) | `Tokyo_MOU_Flag_performance_list_2025.pdf` | Flag-tier context only |
| Tokyo detention review case 43 | [Summary-of-detention-review-case-43-02-2023.pdf](https://www.tokyo-mou.org/wp/wp-content/uploads/Summary-of-detention-review-case-43-02-2023.pdf) | `Tokyo_MOU_detention_review_case_43_02_2023.pdf` | Public narrative pattern for fixtures |

**Citation note on A.1155 vs 5-digit codes.** Issue #31 and earlier project docs describe “IMO Resolution A.1155(32) 5-digit category taxonomy (`011xx`…)”. **A.1155(32) does not publish the 5-digit table**; it publishes procedures, detention guidance, and convention-grouped detainable examples. The **Paris and Tokyo MOU Deficiency Codes PDFs** are the controlling sources for `011`/`041`/`071`/`101`/`131`/`151`.

**Citation note on `071xx`.** Issue #31 maps `071xx` → Safety of Navigation. **Both MOU code lists label category `07` / prefix `071` as Fire safety** (SOLAS II-2). Safety of Navigation is category `10` / prefix **`101`**. The engine encodes the MOU labels.

**Citation note on Code 30.** Historical MOU databases and Issue #31 use action code **`30`** for detention. PSCC59/2026/03 documents rectification codes `15`/`16`/`17` and records detention as a form tick-box (“Grounds for detention”). The open core keeps `ACTION_DETENTION = "30"` for machine-readable inspection records.

---

## 3. Verified taxonomy → convention map

| Prefix | MOU category (verified) | Convention encoding |
| :--- | :--- | :--- |
| `011` / `012` | Certificate & Documentation (ship / crew) | SOLAS certificates / STCW |
| `041` | Emergency Systems | SOLAS Ch. II-1 / II-2 |
| `071` | Fire safety | SOLAS Ch. II-2 |
| `101` | Safety of Navigation | SOLAS Ch. V |
| `131` | Propulsion and auxiliary machinery | SOLAS Ch. II-1 |
| `141`–`148` | Pollution prevention | MARPOL (Annex / AFS / BWM) |
| `151` | ISM | ISM Code / SOLAS Ch. IX |

Critical-system hints used for repeat flags (not exhaustive of all detainable items):

| Critical system | Representative codes / keywords |
| :--- | :--- |
| Steering gear | `02105`, `04106`, `08104`, description contains “steering” |
| Emergency fire pump | `04102`, “emergency fire pump” |
| ISM major non-conformity | `151xx` |

---

## 4. Action-code severity & Defect Score

### 4.1 `ACTION_CODE_SEVERITY` (Universal Core)

| Code | Meaning (PSCC59 / MOU practice) | Weight |
| :--- | :--- | ---: |
| `30` | Detention (machine-record convention) | **1.0** |
| `17` | Rectify before departure | **0.5** |
| `15` | Rectify at next port | **0.4** |
| `16` | Rectify within 14 days | **0.25** |
| other / missing | Residual | **0.1** |

`15` is weighted above `16` because departure-port deferral still constrains the voyage more tightly than a 14-day master-responsibility window.

### 4.2 Category base weights

Safety-critical prefixes (`041`, `071`, `101`, `131`, `151`) use base **1.0**; documentation / other mapped prefixes use **0.6**; unknown prefixes use **0.4**.

### 4.3 Compound Seaworthiness Defect Score

For each normalized deficiency \(d\):

```text
contrib(d) = category_base(prefix) × ACTION_CODE_SEVERITY(action)
             × repeat_mult(d) × cic_mult(prefix, mou_id)
score = Σ contrib(d)
```

- `repeat_mult = 1.5` when the same critical system appears in a prior inspection window; else `1.0`.
- `cic_mult` defaults to `1.0`; regional Concentrated Inspection Campaign weights inject via `cic_weights: dict[str, float]` (prefix → multiplier) without hardcoding Tokyo vs Paris priorities in the core.

The report also exposes: `detention_present`, `repeat_critical_flags`, convention citations, and a list of `NormalizedDeficiency` rows convertible to adapter `PSCDeficiency` for `evaluate_seaworthiness_warranty`.

---

## 5. Implementation map

| Component | Path |
| :--- | :--- |
| Taxonomy / severity constants | `src/marine_claims_ai/ontology/psc.py` |
| Parser + Defect Score | `src/marine_claims_ai/ingest/psc_deficiencies.py` |
| Anonymized fixtures | `config/psc_inspection_fixtures.json` |
| Unit tests | `tests/test_psc_deficiencies.py` |
| Warranty adapter (unchanged doctrine) | `adapters/japan_reference.py` ← consumes `PSCDeficiency` |

### 5.1 Public API

```text
parse_inspection_record(raw) → list[NormalizedDeficiency]
score_seaworthiness(deficiencies, *, prior=None, mou_id=None, cic_weights=None)
  → SeaworthinessRiskReport
to_adapter_deficiencies(deficiencies) → list[PSCDeficiency]
```

---

## 6. Fixture policy

`config/psc_inspection_fixtures.json` holds **anonymized** Paris/Tokyo-style inspection logs (no real vessel names / IMO). JSON lives under `config/` for the Zero-Dataset allowlist. Raw taxonomy PDFs remain under gitignored `_inputs/psc/`.

---

## 7. Verification checklist (primary text)

- [x] Tokyo / Paris: `07` / `071` = **Fire safety** — not navigation.
- [x] Tokyo / Paris: `10` / `101` = **Safety of Navigation**.
- [x] Tokyo / Paris: `04102` = Emergency fire pump; `151` = ISM; `131` = Propulsion & auxiliary.
- [x] PSCC59: action codes `15` / `16` / `17` defined as next-port / 14-days / before-departure.
- [x] A.1155(32): procedures & detainable examples; **not** the 5-digit code table.
- [x] Code `30` retained as universal detention marker for machine records (Issue #31 DoD).
