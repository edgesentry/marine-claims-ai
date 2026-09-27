"""Unit/smoke helpers for the executive demo (local ``pytest -m demo`` only)."""

from __future__ import annotations

from pathlib import Path

import pytest

from marine_claims_ai.demo.cli import main as cli_main
from marine_claims_ai.demo.i18n import MESSAGES, t
from marine_claims_ai.demo.ops import (
    Uc2Params,
    export_uc2,
    export_uc3,
    format_uc2_summary,
    run_uc2,
    run_uc3,
)

pytestmark = pytest.mark.demo


def test_i18n_keys_symmetric():
    for key, entry in MESSAGES.items():
        assert "en" in entry and "ja" in entry, key
        assert entry["en"].strip() and entry["ja"].strip(), key


def test_t_fallback():
    assert t("app_title", "en")
    assert t("missing_key_xyz", "en") == "missing_key_xyz"


def test_ops_parity_cli_and_exports(tmp_path: Path):
    for lang in ("en", "ja"):
        params = Uc2Params(dock_days=4, daily_dock_rate=900_000)
        uc2 = run_uc2(lang, params)
        assert uc2["dock_days"] == 4
        assert uc2["insurer_common"] + uc2["owner_common"] == uc2["dock_total"]
        summary = format_uc2_summary(uc2, lang)
        assert "D5" in summary or "按分" in summary
        _, amd = export_uc2(lang, params=params, fmt="md")
        assert "D5" in amd

        uc3 = run_uc3(lang, case_id="civil_7")
        assert uc3["case_id"] == "civil_7"
        assert uc3["fault_ratio"]
        _, cmd = export_uc3(lang, case_id="civil_7", fmt="md")
        assert "COLREGS" in cmd or "航法" in cmd

    out = tmp_path / "rule_d5.md"
    _, body = export_uc2("en", params=Uc2Params(), fmt="md")
    out.write_text(body, encoding="utf-8")
    assert out.stat().st_size > 100


def test_cli_uc_commands(tmp_path: Path, capsys):
    assert cli_main(["list-cases", "--lang", "en"]) == 0
    listed = capsys.readouterr().out
    assert "civil_7" in listed

    md = tmp_path / "uc2.md"
    assert cli_main(["uc2", "--dock-days", "3", "--json", "--export-md", str(md)]) == 0
    out = capsys.readouterr().out.replace(" ", "")
    assert '"dock_days":3' in out
    assert md.is_file()

    assert cli_main(["uc3", "--case", "civil_7", "--lang", "ja", "--json"]) == 0
    assert "civil_7" in capsys.readouterr().out


def test_demo_http_routes():
    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient

    from marine_claims_ai.demo.app import create_app

    client = TestClient(create_app())
    home = client.get("/")
    assert home.status_code == 200
    assert "Rule D5" in home.text or "按分" in home.text
    assert client.get("/uc2").status_code == 200
    assert client.get("/uc3").status_code == 200
    assert client.get("/uc1").status_code == 404
    assert client.get("/partials/uc2?include_statutory=1").status_code == 200
    assert client.get(
        "/partials/uc3?case_id=civil_7&heading_a_deg=0&heading_b_deg=180&true_bearing_a_to_b_deg=0"
    ).status_code == 200
    r = client.get("/set-lang?lang=ja&next=/uc2")
    assert r.status_code in (303, 307, 200)
    cleared = client.post("/demo/clear-cache", data={"next": "/uc2"}, follow_redirects=False)
    assert cleared.status_code in (303, 307)
    assert "cache_cleared=1" in (cleared.headers.get("location") or "")


def test_interactive_conditions_change_outputs():
    """Condition knobs must change engine outputs (demo pitch requirement)."""
    uc2_50 = run_uc2("en", Uc2Params(include_statutory=True, docking_context="casualty_immediate"))
    uc2_100 = run_uc2("en", Uc2Params(include_statutory=False, docking_context="casualty_immediate"))
    assert uc2_50["rule"] != uc2_100["rule"] or uc2_50["insurer_common"] != uc2_100["insurer_common"]
    assert uc2_50["insurer_common"] + uc2_50["owner_common"] == uc2_50["dock_total"]
    assert uc2_100["owner_common"] == 0 or "100" in str(uc2_100["rule"]).upper()

    uc3_base = run_uc3("en", case_id="civil_7")
    uc3_head = run_uc3(
        "en",
        case_id="civil_7",
        heading_a_deg=0,
        heading_b_deg=180,
        true_bearing_a_to_b_deg=0,
    )
    assert uc3_base["situation"] != uc3_head["situation"] or uc3_head["overrides_applied"] is True
    assert uc3_head["situation"] == "head_on"
