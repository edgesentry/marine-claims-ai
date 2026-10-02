# Demo Use Cases: Inputs, Processing, Outputs

Explains the executive-demo tabs (Issue #54): **what** each use case is, **inputs**, **internal processing**, and **what outputs mean**. The Web UI analyzes **real business PDFs** (list or open file); interactive controls still change results live.

Related: [Executive demo (WASM PWA)](executive_demo_cli_and_web.md) · [AAA Rule D5](aaa_rule_d5_drydock_apportionment.md) · [COLREGS engine](colregs_encounter_engine.md) · [Getting started](getting_started.md).

**UI language:** Business terms only on screen (no library/function names). Developer notes below may mention modules.

**Scope:** The demo covers **Rule D5 apportionment** and **COLREGS fault evidence** only. Hull-topology / owner's-work exclusion is **not** implemented in the demo (see the high-ROI architecture note on rejecting detailed GA topology).

---

## UC1 (demo tab) — AAA Rule D5 & off-hire simulator

| | |
| :--- | :--- |
| **Use case** | Split drydock common dues under London AAA Rule D5 and estimate off-hire avoided by faster pre-approval. |
| **Tab** | `1. Rule D5` / `/uc2` (WASM PWA) |

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

## Changing conditions

| Control | Expected change |
| :--- | :--- |
| Rule D5 PDF + Analyze | Lines and dues from that document |
| Rule D5 docking context / statutory | 50/50 ↔ 100% underwriter |
| COLREGS PDF + Analyze | Facts/ruling/fault from that document |
| COLREGS heading / bearing | Situation / roles / radar |

Final indemnity remains with the appointed surveyor / adjuster.

PDFs are never committed (Zero-Dataset). Place under `_data/poc_datasets/` or open into `_data/demo_uploads/`.
