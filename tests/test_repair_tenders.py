"""Tests for public repair-tender crawler (no network required)."""

from __future__ import annotations

import json
from pathlib import Path

from marine_claims_ai.ingest.repair_tenders import fetch_repair_tenders, load_manifest


def test_load_manifest_has_entries():
    m = load_manifest()
    assert len(m["entries"]) >= 5
    kinds = {e["kind"] for e in m["entries"]}
    assert "spec" in kinds


def test_dry_run_does_not_write(tmp_path: Path):
    summary = fetch_repair_tenders(
        repairs_dir=tmp_path / "repairs",
        dry_run=True,
        limit=3,
    )
    assert summary["dry_run"] is True
    assert not (tmp_path / "repairs").exists() or not any((tmp_path / "repairs").rglob("*.pdf"))
    assert len(summary["results"]) == 3
    assert all(r["action"] == "dry_run" for r in summary["results"])


def test_seed_copy_from_local_file(tmp_path: Path):
    seed_root = tmp_path / "seed"
    seed_root.mkdir()
    seed_pdf = seed_root / "demo_spec.pdf"
    seed_pdf.write_bytes(b"%PDF-1.4 demo")

    manifest = {
        "polite_sleep_seconds": 0,
        "entries": [
            {
                "id": "demo",
                "kind": "spec",
                "filename": "demo_out.pdf",
                "url": None,
                "local_seed": "demo_spec.pdf",
            }
        ],
    }
    man_path = tmp_path / "manifest.json"
    man_path.write_text(json.dumps(manifest), encoding="utf-8")

    # Point seed lookup via monkeypatching DEFAULT paths is heavy; place seed where
    # _resolve_seed looks — use repairs_dir specs as already-present skip path by
    # pre-copying through a tiny wrapper: call with url download mocked via seed
    # by putting file into LEGACY-like layout under tmp and patching.
    from marine_claims_ai.ingest import repair_tenders as rt

    original = rt._resolve_seed

    def _fake_resolve(name: str):
        if Path(name).name == "demo_spec.pdf":
            return seed_pdf
        return original(name)

    rt._resolve_seed = _fake_resolve  # type: ignore[assignment]
    try:
        summary = fetch_repair_tenders(
            manifest_path=man_path,
            repairs_dir=tmp_path / "repairs",
            dry_run=False,
        )
    finally:
        rt._resolve_seed = original  # type: ignore[assignment]

    dest = tmp_path / "repairs" / "specs" / "demo_out.pdf"
    assert dest.is_file()
    assert dest.read_bytes().startswith(b"%PDF")
    assert summary["seeded"] == 1
