# Demo Use Cases: Inputs, Processing, Outputs

Explains the three executive-demo tabs (Issue #54): **what** each use case is, **inputs**, **internal processing**, and **what outputs mean**. The Web UI analyzes **real business PDFs** (list or open file); interactive controls still change results live.

Related: [Executive demo CLI & Web](executive_demo_cli_and_web.md) · [AAA Rule D5](aaa_rule_d5_drydock_apportionment.md) · [COLREGS engine](colregs_encounter_engine.md) · [Getting started](getting_started.md).

**UI language:** Business terms only on screen (no library/function names). Developer notes below may mention modules.

---

## UC1 — Topology / owner's work exclusion

| | |
| :--- | :--- |
| **Use case** | Screen a drydock repair specification against casualty damage zones so concurrent / periodic owner's work is excluded. |
| **Tab** | `1. Topology` / `/uc1` · CLI `marine-claims-demo uc1 --analyze --spec … --casualty …` |

### Inputs

| Input | Source | Interactive? |
| :--- | :--- | :--- |
| Repair specification PDF | Public Kaiyo Maru / sample specs under `_data/` or `_inputs/`; or Open file → `_data/demo_uploads/` | List + file picker + Analyze |
| Casualty / investigation PDF | JTSB collision reports (same dirs / open file) | List + file picker |
| Damage / probe zones, status filter | Compartment nodes | Dropdowns after analysis |

### Processing

1. `pdftotext` + `appraisal.pipeline` extract damage profile and line items, then screen concurrent repairs.
2. Compartment causality check for the selected damage→repair zones.
3. Results may persist under `_data/poc_datasets/claims_analysis_*.json` for export.

### Outputs

Metrics, compartment view, causality check (business wording), line table, Preliminary Survey draft.

---

## UC2 — AAA Rule D5 & off-hire simulator

| | |
| :--- | :--- |
| **Use case** | Split drydock common dues under London AAA Rule D5 and estimate off-hire avoided by faster pre-approval. |
| **Tab** | `2. Rule D5` / `/uc2` · CLI `marine-claims-demo uc2 --analyze --spec …` |

### Inputs

| Input | Source | Interactive? |
| :--- | :--- | :--- |
| Drydock / repair PDF | Same public repair specs (or open file) | List + file picker + Analyze |
| Dock rate/days, hire, lead times, docking context, statutory toggle | UI / CLI | Yes — flips Rule D5 outcome |

### Processing

Extract works from the PDF → classify casualty / owner / common dues → Rule D5 apportionment → off-hire heuristic.

### Outputs

How dues are split, insurer/owner shares, timeline, off-hire estimate, statement export.

---

## UC3 — COLREGS radar & fault evidence

| | |
| :--- | :--- |
| **Use case** | Classify encounter geometry (Rules 13–15), assign give-way / stand-on, and show fault-ratio evidence. |
| **Tab** | `3. COLREGS` / `/uc3` · CLI `marine-claims-demo uc3 --analyze --doc …` |

### Inputs

| Input | Source | Interactive? |
| :--- | :--- | :--- |
| Ruling / judgment / casualty PDF | JTSB reports or opened PDFs | List + file picker + Analyze |
| Optional sample fixture | `civil_7` / JMAT ids | Dropdown |
| Heading / bearing | Sliders | Live reclassify |

### Processing

Extract text → judgment / telemetry helpers → encounter classification + fault-ratio estimate.

### Outputs

Situation, roles, fault ratio, radar sketch, COLREGS memo export.

---

## Changing conditions

| Control | Expected change |
| :--- | :--- |
| UC1 PDF pair + Analyze | Full re-screen from documents |
| UC1 damage / probe zone | Causality check pass/fail |
| UC2 PDF + Analyze | Lines and dues from that document |
| UC2 docking context / statutory | 50/50 ↔ 100% underwriter |
| UC3 PDF + Analyze | Facts/ruling/fault from that document |
| UC3 heading / bearing | Situation / roles / radar |

Final indemnity remains with the appointed surveyor / adjuster.

PDFs are never committed (Zero-Dataset). Place under `_data/poc_datasets/` or open into `_data/demo_uploads/`.
