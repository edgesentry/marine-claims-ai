# MarineClaims AI

AI-powered marine insurance claims appraisal, fault attribution, and concurrent repair screening.

Deterministic domain engines (COLREGS, naval-architecture compartment graphs, AAA Rule D5) combine with light LLM normalization so adjusters can screen concurrent repairs and attribute collision fault without hallucinated legal conclusions.

## Capabilities

- **Concurrent repair screening** — drydock specs vs damage zones; Negative Pattern Library + watertight-barrier gates; 50/50 common dues
- **Collision fault attribution** — COLREGS Rules 13–15 geometry + JMAT / civil precedent heuristics
- **PSC risk signals** — Paris / Tokyo MOU-style flag deficiency patterns

## Open-core scope

Public ingestion scripts, ontologies, verification engines, and scientific methodology docs. **No raw claim PDFs or extracted JSON in git** (Zero-Dataset). Local caches: `_data/` (preferred), legacy `_inputs/`.

## Quick start

```bash
uv sync
uv run pytest -q
```

Full install, ingest, index, eval, pipeline, and demo instructions:
**[docs/getting_started.md](docs/getting_started.md)**

Executive demo (WASM PWA): **[docs/executive_demo_cli_and_web.md](docs/executive_demo_cli_and_web.md)**

Agent constraints: **[AGENTS.md](AGENTS.md)**

## Documentation

| Doc | Topic |
| :--- | :--- |
| [Getting Started](docs/getting_started.md) | Install, ingest, indexes, benchmarks, pipeline |
| [Executive Demo (Issues #54 / #76)](docs/executive_demo_cli_and_web.md) | Client-side WASM PWA |
| [Demo Use Cases](docs/demo_use_cases.md) | Per-tab use case / input / process / output |
| [Technical Stack](docs/technical_stack.md) | Architecture |
| [Public Benchmarks & Accuracy](docs/public_benchmarks_and_accuracy_evaluation.md) | Evaluation methodology |
| [AAA Rule D5](docs/aaa_rule_d5_drydock_apportionment.md) | Drydock apportionment |
| [COLREGS Encounter Engine](docs/colregs_encounter_engine.md) | Rules 13–15 |
| [Gate A Priority 1](docs/gate_a_priority1_eval.md) | H&M drydock A1–A4, A8 — **Vitest:** `cd web && npm run gate-a` |
| [Gate A Priority 2](docs/gate_a_priority2_eval.md) | COLREGS A5/A6 + Civil A7 — **Vitest** in `web/src/benchmarks/gateAPriority2.ts` |
| [Symbolic AI Framework](docs/symbolic_ai_implementation_framework.md) | Deterministic core |
| [Database Lifecycle](docs/database_architecture_and_lifecycle.md) | DuckDB (analytics + vector search) |
| [R&D Roadmap](docs/research_and_development_roadmap.md) | Stages |
| [Iterative Knowledge Loop](docs/iterative_knowledge_loop_specification.md) | Learning loop |
| [Prior Research Synthesis](docs/prior_research_synthesis.md) | Background |

## License

[Apache License, Version 2.0](LICENSE).

Dependency license policy is enforced in CI via `pip-licenses` and GitHub Dependency Review. Strong copyleft / common source-available traps (GPL/AGPL/LGPL/SSPL/BUSL, etc.) fail the build.
