# Gate A Priority 2 (Issue #59) — COLREGS A5/A6 + civil A7

**Canonical (WASM / Vitest):**

```bash
cd web && npm run gate-a
# A5/A6 geometries + A7 offline snippets: web/src/benchmarks/gateAPriority2.ts
```

The former Python Gate A Priority 2 harness was removed.
## Metrics

| ID | What | Threshold |
|----|------|-----------|
| **A5** | COLREGS situation (Rules 13–15) vs JMAT gold | Situation accuracy ≥ 90% |
| **A6** | Give-way / stand-on role attribution | Critical role inversions = **0** (always) |
| **A7** | Civil fault-ratio / yen extraction | Accuracy ≥ 90%; within ±10pt ≥ 80% |

## Scale targets (Issue #59)

- JMAT gold cases: **100** (overtaking ≥25 / head-on ≥25 / crossing ≥50)
- Civil catalog with fault_ratio: **60–80**

When below target the report sets `scale.scale_incomplete=true`. Zero-tolerance **A6** and accuracy gates on the present corpus still apply for `--fail-on-gate`. Use `--fail-on-scale` to exit non-zero until corpus targets are met.

## Config & data

- Thresholds: `config/gate_a_priority2.json`
- JMAT E2E gold: `config/jmat_collision_eval.json` (embedded narratives; Zero-Dataset)
- Civil gold: `config/civil_precedent_catalog.json`
- Raw HTML/PDF (gitignored): `_inputs/casualties/jmat/`, `_inputs/legal/civil_court/`
- Logs: `_logs/colregs_civil_eval.log`

Related: [COLREGS encounter engine](colregs_encounter_engine.md) · [Directory governance](directory_structure_and_data_governance.md) · [Gate A Priority 1](gate_a_priority1_eval.md)
