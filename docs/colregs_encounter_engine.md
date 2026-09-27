# COLREGS Encounter Geometry Engine: Rule Summary & Implementation Map

This document records the **steering and sailing rules** that bound GitHub Issue [#30](https://github.com/edgesentry/marine-claims-AI/issues/30) (First-Order Predicate Logic Engine for COLREGS Rules 13–15), and maps each clause to the open-core implementation after verification against public primary texts.

Related docs: [Symbolic AI Implementation Framework](symbolic_ai_implementation_framework.md) · [R&D Roadmap](research_and_development_roadmap.md) Stage 1 · [Public Benchmarks & Accuracy Evaluation](public_benchmarks_and_accuracy_evaluation.md) §5 · [Technical Stack](technical_stack.md).

Local primary-text cache (gitignored): `_inputs/colregs/` — see [`_inputs/colregs/SOURCES.md`](../_inputs/colregs/SOURCES.md).

---

## 1. Scope of Issue #30

Issue #30 asks for a deterministic, hallucination-free classifier that maps encounter telemetry (headings, true bearing) to COLREGS Part B Section II situation labels and vessel roles. The open-core side encodes only **convention-invariant geometry**. Jurisdiction-local fault-split catalogs (JMAT ratios, Admiralty precedents) stay in Modular Jurisdiction Adapters.

| In scope | Out of scope (this issue) |
| :--- | :--- |
| COLREGS Rules **13–15** situation geometry + role assignment | Numerical civil fault percentages (70:30, 80:20, …) |
| Relative bearing / course difference / optional CPA·TCPA | Rule 19 restricted visibility, Rule 9/10 TSS fairway adapters |
| Rules **16–17** role labels (`GIVE_WAY` / `STAND_ON`) as obligations attached to 13–15 | Full Rule 17 close-quarters branch tree as a separate state machine |
| Unit tests on synthetic + anonymized historical-pattern fixtures | Committing raw JMAT/JTSB PDFs or identifiable vessel tracks |

**Architecture boundary.** `legal/colregs_engine.py` is Universal Open Core. `adapters.base.EncounterSituation` (precedent-lookup DTO) is a different type from `legal.colregs_engine.EncounterSituation` (geometry enum).

---

## 2. Controlling primary sources (fetched 2026-09-27)

| Instrument | Public URL | Local cache | Role for #30 |
| :--- | :--- | :--- | :--- |
| USCG Navigation Rules Handbook (International Rules) | [NavRules_Handbook_Corrected_08_08_2024.pdf](https://www.navcen.uscg.gov/sites/default/files/pdf/navRules/Handbook/NavRules_Handbook_Corrected_08_08_2024.pdf) | `USCG_NavRules_Handbook_2024-08-08.pdf` | **Controlling English** Rules 13–17 wording |
| eCFR 33 CFR §§ 83.13–83.17 | [eCFR Subpart B](https://www.ecfr.gov/current/title-33/chapter-I/subchapter-E/part-83/subpart-B/subject-group-ECFR201c8b6bfd729a0) | `ecfr_*` | Machine-readable restatement of International Rules |
| 海上衝突予防法（昭和52年法律第62号） | [e-Gov law 352AC0000000062](https://laws.e-gov.go.jp/law/352AC0000000062) | `egov_kaisho_yoboho_webfetch.md`, `egov_arts13-17_excerpt.md` | **Controlling Japanese** Arts. 13–17 |
| IMO COLREGS portal | [imo.org COLREG](https://www.imo.org/en/About/Conventions/Pages/COLREG.aspx) | `imo_colreg_portal.html` | Convention identity only; full annex not free on portal |
| JMAT Art. 13 commentary / overtaking primer | [yobouho13](https://www.mlit.go.jp/jmat/monoshiri/houki/yobouhou/yobouho13.htm), [oikoshi](https://www.mlit.go.jp/jmat/monoshiri/houki/houkinyumon/oikoshi.htm) | `jmat_*.html` | Sector explanation aligned with statute |
| JMAT saiketsu (紀伊水道 横切) | [6tk002.pdf](https://www.mlit.go.jp/jmat/saiketsu/saiketsu_kako/tokyou/tkR07/6tk002.pdf) | `jmat_6tk002_kii_crossing.pdf` | Public **Art. 15** situation label for fixture pattern |
| JTSB marine accident PDFs | [jtsb.mlit.go.jp](https://jtsb.mlit.go.jp/jtsb/ship/) via `fetch_public_datasets.py` | `_inputs/poc_datasets/jtsb_*` | AIS/narrative patterns (not committed) |

**Citation note on ±5°.** Issue #30 and earlier project docs describe head-on courses as “180° ± 5°”. **Neither COLREGS Rule 14 nor 海上衝突予防法 第14条 states a numeric degree band.** Both use “nearly reciprocal” / 「ほとんど真向かい」 and “nearly ahead” / 「ほとんど船首方向」. The engine’s `HEAD_ON_*_TOLERANCE_DEG = 5.0` is an **explicit engineering encoding** of that qualitative language, chosen to match the issue’s DoD and prior internal docs—not a value copied from the statute.

---

## 3. Rule summary — verified wording → predicates

### 3.1 Rule 13 / 第13条 — Overtaking（追越し船）

**Statutory fact pattern (verified).** A vessel coming up from a direction **more than 22.5° abaft the beam** of the other (夜間: sternlight only, neither sidelight) is an overtaking vessel and must keep out of the way until past and clear.

Japanese Art. 13(2): 「船舶の正横後**二十二度三十分**を超える後方の位置」— identical numeric threshold.

Art. 21 sidelight arcs (**112°30′** from ahead to 22.5° abaft either beam) independently confirm the same geometric cut.

**Encoding.**

- `aspect_angle` = relative bearing of the approaching vessel **as seen from the vessel being approached**.
- `is_overtaking(aspect) ⇔ 112.5° < aspect < 247.5°`.
- Priority: Rule 13 is evaluated before Rules 14–15 (doubt → assume overtaking: Art. 13(3) / Rule 13(c)).
- Roles: overtaking vessel `GIVE_WAY`, overtaken `STAND_ON` (Rules 16–17).

### 3.2 Rule 14 / 第14条 — Head-on（行会い船）

**Statutory fact pattern (verified).** Two power-driven vessels meeting on reciprocal or nearly reciprocal courses with risk of collision: **each alters course to starboard** (port-to-port). Deemed when the other is ahead or nearly ahead (masthead lights in line / both sidelights).

**Encoding.**

- `is_head_on(course_diff, relative_bearing)` when `|course_diff − 180°| ≤ 5°` **and** angular distance of relative bearing from ahead ≤ 5°.
- Both vessels: `GIVE_WAY` with `mutual_starboard_alteration=True` (neither is a Rule 17 stand-on vessel in the classical crossing sense).

### 3.3 Rule 15 / 第15条 — Crossing（横切り船）

**Statutory fact pattern (verified).** When two power-driven vessels are crossing with risk of collision, the vessel that has the other on her **starboard** side shall keep out of the way and shall, so far as practicable, avoid crossing ahead.

Japanese Art. 15: 「他の動力船を**右げん側**に見る動力船」— identical duty.

**Public ground-truth label.** JMAT 6tk002 (紀伊水道): 「海上衝突予防法**第１５条**の横切り船の航法によって律するのが相当」— situation class `CROSSING`, not a numeric fault % in the open core.

**Encoding.**

- After excluding Rules 13 and 14: `is_crossing` when courses are neither nearly parallel nor head-on-reciprocal and the contact lies forward of 22.5° abaft either beam.
- Starboard contact → own ship `GIVE_WAY`; port contact → own ship `STAND_ON`.

### 3.4 Rules 16–17 / 第16–17条 — Give-way / Stand-on labels

Attached as `VesselRole` on Rule 13/15 verdicts. Rule 14 uses mutual starboard alteration rather than asymmetric stand-on.

---

## 4. Implementation map

| Component | Path |
| :--- | :--- |
| Engine | `src/marine_claims_ai/legal/colregs_engine.py` |
| Package exports | `src/marine_claims_ai/legal/__init__.py` |
| Geometry fixtures | `config/collision_geometries.json` (Zero-Dataset JSON allowlist) |
| Unit tests | `tests/test_colregs_engine.py` |

### 4.1 Telemetry helpers

| Symbol | Definition |
| :--- | :--- |
| Relative bearing | `θ_rel = (TrueBearing − Heading) mod 360` |
| Course difference | `Δψ = \|Heading_A − Heading_B\| mod 360` |
| CPA / TCPA | Optional relative-velocity kinematics when range + SOG provided |

### 4.2 Classification priority

```text
is_overtaking(rel from B of A) → OVERTAKING, A=GIVE_WAY
else is_overtaking(rel from A of B) → OVERTAKING, B=GIVE_WAY
else (power-driven ∧ is_head_on) → HEAD_ON, mutual starboard
else (power-driven ∧ is_crossing) → CROSSING, starboard give-way
else → SAFE_PASSING
```

Determinism: identical inputs always yield identical `EncounterVerdict` (no LLM path).

---

## 5. Fixture policy

`config/collision_geometries.json` holds **synthetic** compass-quadrant cases plus **anonymized historical-pattern** rows (no real vessel names / IMO). JSON lives under `config/` to satisfy the Zero-Dataset allowlist (Issue #30’s `tests/fixtures/` path would fail CI leak check). Pattern citations point at public ruling *situation* labels (e.g. Art. 15) and COLREGS thresholds, not proprietary claim files. Raw PDFs remain under gitignored `_inputs/`.

---

## 6. Verification checklist (primary text)

- [x] Rule 13 / Art. 13: **22.5° / 二十二度三十分** abaft beam — matched in code constants.
- [x] Art. 21 sidelight **112°30′** arc — consistent with overtaking/crossing boundary at 112.5° relative.
- [x] Rule 14 / Art. 14: mutual starboard alteration; “nearly” left qualitative in statute — ±5° documented as engineering tolerance.
- [x] Rule 15 / Art. 15: starboard-side give-way — matched.
- [x] JMAT 6tk002: public **Art. 15** crossing label used as historical-pattern situation class.
- [x] IMO portal: convention identity only; English operative text taken from USCG/eCFR public republication.
