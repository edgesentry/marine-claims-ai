# Demo Use Cases: Inputs, Processing, Outputs

Explains the executive-demo tabs (Issue #54 / #83): **what** each use case is, **which laws / rules it encodes**, **inputs**, **internal processing**, and **what outputs mean**. The Web UI analyzes **real business PDFs** where relevant (list or open file); interactive controls still change results live.

Related: [Executive demo (WASM PWA)](executive_demo_cli_and_web.md) · [AAA Rule D5](aaa_rule_d5_drydock_apportionment.md) · [COLREGS engine](colregs_encounter_engine.md) · [PSC deficiency vector](psc_deficiency_vector.md) · [Exact Span grounding](exact_span_grounding.md) · [Confidence / HUMAN_REVIEW](confidence_abstention.md) · [Getting started](getting_started.md).

**UI language:** Business terms only on screen (no library/function names). Developer notes below may mention modules.

**Scope:** The demo covers three public-data insurance use cases: **Rule D5 apportionment**, **COLREGS fault evidence**, and **PSC seaworthiness screening**. Hull-topology / owner's-work exclusion is **not** implemented in the demo (see the high-ROI architecture note on rejecting detailed GA topology).

## Legal / rule basis (summary)

| Demo tab | Controlling instruments (what the engine encodes) | Not claimed by the demo |
| :--- | :--- | :--- |
| **1. Rule D5** | London **Association of Average Adjusters (AAA) Rules of Practice — Section D, Rule D5** (“DRY DOCK EXPENSES”). Parallel market wording: US/CA AAA **Rule C2**. | Japan AAA Rules **1** / **20** (different predicates); dock tariffs; final indemnity |
| **2. COLREGS** | **COLREGS 1972** Part B Section II **Rules 13–15** (situation) and **16–17** (give-way / stand-on roles); Japanese transposition **海上衝突予防法**（昭和52年法律第62号）**第13–17条** | Binding civil fault %; full Rule 19 / TSS adapters as separate engines |
| **3. PSC** | **Tokyo / Paris MOU Deficiency Codes** (5-digit taxonomy); action codes per **Paris PSCC59** / MOU practice (`15`/`16`/`17`; machine-record **`30`** = detention); procedures context **IMO A.1155(32)**; convention families **SOLAS / MARPOL / ISM / STCW** | Live MOU scrape; Japan Commercial Code Art. 815 / UK **MIA 1906 s.39** warranty conclusion (adapter-only) |

Detailed clause maps: [aaa_rule_d5_drydock_apportionment.md](aaa_rule_d5_drydock_apportionment.md) · [colregs_encounter_engine.md](colregs_encounter_engine.md) · [psc_deficiency_vector.md](psc_deficiency_vector.md).

## Stage A extraction contract

**Document-type router (Issue #86)** runs first on uploaded PDF / pasted text (`web/src/pipeline/documentRouter.ts`):

| Detected type | Demo tab that may Analyze |
| :--- | :--- |
| `repair_spec` | Rule D5 |
| `civil_judgment` / `jmat_ruling` / `jtsb_report` | COLREGS |
| `psc_inspection` | PSC |
| `unknown` | none — override required or abstain |

The PWA shows the detected type and confidence, lets you override before **Analyze**, and never silently runs Stage B on `unknown` or a tab mismatch. Heuristic Tier 1 only in this release (optional SLM Tier 2 is Issue #77).

Before Stage B scoring, extractors wrap output in a shared **`ExtractionResult`** (`web/src/schemas/`, Issue #87):

- `rule_d5.v1` — repair lines + docking context  
- `colregs.v1` — headings / bearing / situation candidates + facts/ruling excerpts  
- `psc.v1` — deficiency rows (+ optional prior window)

Invalid envelopes never reach the Rule D5 / COLREGS / PSC scorers. JSON Schema copies for interoperability: [docs/schemas/](schemas/). Document-derived fields also need **Exact Span** grounding (or an explicit paste bypass): [exact_span_grounding.md](exact_span_grounding.md) (Issue #88). When Stage A document confidence is below engineering defaults, the PWA shows **`HUMAN_REVIEW_REQUIRED`** and blocks Stage B until Confirm & score ([confidence_abstention.md](confidence_abstention.md#try-it-in-the-pwa), Issue #89) — e.g. Rule D5 repair PDF upload, not the synthetic demo lines.

**UI language ≠ extraction language (Issue #90):** The PWA locale switch (`web/src/i18n.ts`) only changes **display** strings. Schema enums consumed by Stage B (`crossing`, `04102`, `casualty_immediate`, `ENG-02`, …) stay language-agnostic. JA/EN shipyard jargon is mapped via the lexicon (`config/lexicons/shipyard_jargon.v1.json`, `web/src/pipeline/normalizeLabels.ts`) — not full-document MT. Vector candidate recall is a separate track (#104).

---

## UC1 (demo tab) — AAA Rule D5 & off-hire simulator

| | |
| :--- | :--- |
| **Use case** | Split drydock common dues under London AAA Rule D5 and estimate off-hire avoided by faster pre-approval. |
| **Tab** | `1. Rule D5` / `/uc2` (WASM PWA) |

### Legal / rule basis (Rule D5)

| Layer | Instrument | Role in this UC |
| :--- | :--- | :--- |
| **Controlling** | London AAA **Rules of Practice, Rule D5** (DRY DOCK EXPENSES) | Who pays **common dock dues** (entering / leaving / lay): **100% underwriter** when the vessel docks for the casualty, or **50/50** with the owner when deferred to a routine docking with concurrent owner’s work |
| Parallel | US/Canada AAA Rules of Practice **C2** | Same substance; not a second algorithm |
| Adjacent (not encoded) | Japan AAA Rules of Practice (e.g. Rule 1, Rule 20) | Different market predicates — see dedicated Rule D5 doc |
| Heuristic only | Off-hire days × hire rate | **Not** a statute; screening-time estimate for pitch / pre-approval |

Primary-text map and implementation notes: [AAA Rule D5](aaa_rule_d5_drydock_apportionment.md).

### Inputs (Rule D5)

| Input | Source | Interactive? |
| :--- | :--- | :--- |
| Drydock / repair PDF | Public repair specs under `_data/` or open file → `_data/demo_uploads/` | List + file picker + Analyze |
| Dock rate/days, hire, lead times, docking context, statutory toggle | UI / CLI | Yes — flips Rule D5 outcome |

### Processing (Rule D5)

Extract works from the PDF → classify casualty / owner / common dues → Rule D5 apportionment → off-hire heuristic.

### Outputs (Rule D5)

How dues are split, insurer/owner shares, timeline, off-hire estimate, statement export.

---

## UC2 (demo tab) — COLREGS radar & fault evidence

| | |
| :--- | :--- |
| **Use case** | Classify encounter geometry (Rules 13–15), assign give-way / stand-on, and show fault-ratio evidence. |
| **Tab** | `2. COLREGS` / `/uc3` (WASM PWA) |

### Legal / rule basis (COLREGS)

| Layer | Instrument | Role in this UC |
| :--- | :--- | :--- |
| **Controlling (EN)** | **COLREGS 1972** — Convention on the International Regulations for Preventing Collisions at Sea, Part B Section II **Rules 13–15** (overtaking / head-on / crossing) and **Rules 16–17** (give-way / stand-on obligations) | Encounter **situation** and **vessel roles** from headings and relative bearing |
| **Controlling (JA)** | **海上衝突予防法**（昭和52年法律第62号）**第13–17条** | Domestic transposition of the same geometry; demo labels cite both |
| Evidence patterns | Public JMAT / civil / JTSB records (fixtures) | Fault-ratio **evidence** from open patterns — not a court award |
| Engineering note | Head-on ±5° tolerance | Qualitative “nearly reciprocal” in Rule 14 / 第14条 encoded as an explicit engineering constant — see COLREGS doc |

Primary-text map: [COLREGS encounter engine](colregs_encounter_engine.md).

### Inputs (COLREGS)

| Input | Source | Interactive? |
| :--- | :--- | :--- |
| Ruling / judgment / casualty PDF | JTSB reports or opened PDFs | List + file picker + Analyze |
| Optional sample fixture | `civil_7` / JMAT ids | Dropdown |
| Heading / bearing | Sliders | Live reclassify |

### Processing (COLREGS)

Extract text → judgment / telemetry helpers → encounter classification + fault-ratio estimate.

### Outputs (COLREGS)

Situation, roles, fault ratio, radar sketch, COLREGS memo export.

---

## UC3 (demo tab) — PSC seaworthiness risk

| | |
| :--- | :--- |
| **Use case** | Score public Tokyo / Paris MOU-style deficiency records into a Seaworthiness Defect Score for underwriting refresh and post-casualty screening. |
| **Tab** | `3. PSC` (WASM PWA) |

### Legal / rule basis (PSC)

| Layer | Instrument | Role in this UC |
| :--- | :--- | :--- |
| **Controlling taxonomy** | **Tokyo MOU** and **Paris MoU Deficiency Codes** (5-digit / category prefixes, e.g. `041` emergency, `071` fire safety, `101` navigation, `151` ISM) | Map deficiency codes → convention family and category weights |
| **Action codes** | Paris **PSCC59** guidelines on detention and action taken (`15` / `16` / `17`); machine-record **Code `30`** = detention (MOU database practice) | Severity weights and detention flag |
| **Procedures** | **IMO Resolution A.1155(32)** Procedures for Port State Control | Detention / detainable-examples context — **not** the 5-digit code table |
| **Convention families** | **SOLAS**, **MARPOL**, **ISM Code**, **STCW** (via MOU category → chapter encoding) | Citations on the report and memo |
| **Not in core scoring** | Japan Commercial Code **Art. 815** / UK **Marine Insurance Act 1906 s.39** (warranty of seaworthiness) | Jurisdiction adapters only; demo memo is **screening**, not a warranty opinion |
| Demo only | Risk bands `low` / `elevated` / `critical` | Engineering thresholds for pitch clarity — not statutory cut-offs |

Primary-text map: [PSC deficiency vector](psc_deficiency_vector.md).

### Inputs (PSC)

| Input | Source | Interactive? |
| :--- | :--- | :--- |
| Bundled anonymized inspection fixtures | `config/psc_inspection_fixtures.json` (copied into PWA `data/`) | Dropdown |
| Lookback window (months) | UI (default **24**, Issue #42) | Yes — repeat flags move in/out of window |
| Pasted deficiency list | JSON fixture/inspection or simple CSV (`deficiency_code,action_taken,nature[,inspection_date]`) | Optional paste + Score |

**Public-only.** No live MOU scrape, no private claims history, no identifiable vessel names / IMO numbers.

### Processing (PSC)

Normalize deficiency + action codes → category / severity weights → repeat multiplier for critical systems inside lookback → Defect Score + demo risk band (`low` / `elevated` / `critical`).

Bands are engineering demo thresholds (Code 30 or score ≥ 1.0 → critical; critical system or score ≥ 0.4 → elevated), not statutory warranty cut-offs.

### Outputs (PSC)

Defect Score and band, deficiency table (code, action e.g. 17 / 30, repeat flag), underwriter memo export (Markdown / HTML print-to-PDF). Memo cites public taxonomy; it is **not** a legal warranty-of-seaworthiness opinion.

### 30-second pitch script

1. Open tab **3. PSC** (default fixture `repeat_ism_major`).
2. Confirm Defect Score ≥ 1.5, band **critical**, Code **30**, repeat flag **ism**.
3. Shrink lookback to **6** months → repeat flag clears; Code 30 / critical band remain.
4. Export memo (MD or HTML).

---

## Changing conditions

| Control | Expected change |
| :--- | :--- |
| Rule D5 PDF + Analyze | Lines and dues from that document |
| Rule D5 docking context / statutory | 50/50 ↔ 100% underwriter |
| COLREGS PDF + Analyze | Facts/ruling/fault from that document |
| COLREGS heading / bearing | Situation / roles / radar |
| PSC fixture / paste | Defect rows and score |
| PSC lookback | Repeat flag on/off for dated priors |

Final indemnity remains with the appointed surveyor / adjuster.

PDFs are never committed (Zero-Dataset). Place under `_data/poc_datasets/` or open into `_data/demo_uploads/`.
