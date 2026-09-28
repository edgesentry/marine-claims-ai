# Gate A Priority 1 (Issue #58) — local scale eval notes

Run after fetching repair tenders:

```bash
uv run python -m marine_claims_ai.ingest.repair_tenders
uv run python scripts/eval_gate_a_priority1.py \
  --json-out _data/benchmarks/gate_a_priority1_report.json \
  --fail-on-gate
```

- **Zero-tolerance** (must pass on whatever corpus is present): Critical FA = 0, Rule D5 recon error = 0 JPY, Exact Span fabricated accepted = 0.
- **Scale**: issue targets are ≥10 vessels / ≥2,500 line items / ≥20 bid notices. When below target the report sets `scale.scale_incomplete=true` but still requires zero-tolerance.
- Provisional gold dumps: `uv run python scripts/eval_public_appraisal.py --write-gold-dir _data/benchmarks/gold`
- PDF bodies stay gitignored under `_inputs/repairs/` and `_data/`.
