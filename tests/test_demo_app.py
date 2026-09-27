"""Smoke tests for demo i18n, ops, CLI, and Web export helpers."""

from __future__ import annotations

from pathlib import Path

from marine_claims_ai.demo.cli import main as cli_main
from marine_claims_ai.demo.i18n import MESSAGES, t
from marine_claims_ai.demo.ops import (
    Uc2Params,
    export_uc1,
    export_uc2,
    export_uc3,
    format_uc1_summary,
    run_uc1,
    run_uc2,
    run_uc3,
)


def test_i18n_keys_symmetric():
    for key, entry in MESSAGES.items():
        assert "en" in entry and "ja" in entry, key
        assert entry["en"].strip() and entry["ja"].strip(), key


def test_t_fallback():
    assert t("app_title", "en")
    assert t("missing_key_xyz", "en") == "missing_key_xyz"


def test_ops_parity_cli_and_exports(tmp_path: Path):
    for lang in ("en", "ja"):
        uc1 = run_uc1(lang)
        assert uc1["ok"] is True
        summary = format_uc1_summary(uc1, lang)
        assert "topology" in summary.lower() or "トポロジー" in summary
        _, md = export_uc1(lang, fmt="md")
        assert "Preliminary" in md or "予備" in md

        params = Uc2Params(dock_days=4, daily_dock_rate=900_000)
        uc2 = run_uc2(lang, params)
        assert uc2["dock_days"] == 4
        assert uc2["insurer_common"] + uc2["owner_common"] == uc2["dock_total"]
        _, amd = export_uc2(lang, params=params, fmt="md")
        assert "D5" in amd

        uc3 = run_uc3(lang, case_id="civil_7")
        assert uc3["case_id"] == "civil_7"
        assert uc3["fault_ratio"]
        _, cmd = export_uc3(lang, case_id="civil_7", fmt="md")
        assert "COLREGS" in cmd or "航法" in cmd

    out = tmp_path / "survey.md"
    _, body = export_uc1("en", fmt="md")
    out.write_text(body, encoding="utf-8")
    assert out.stat().st_size > 100


def test_cli_uc_commands(tmp_path: Path, capsys):
    assert cli_main(["list-cases", "--lang", "en"]) == 0
    listed = capsys.readouterr().out
    assert "civil_7" in listed

    md = tmp_path / "uc1.md"
    assert cli_main(["uc1", "--json", "--export-md", str(md)]) == 0
    assert md.is_file()
    assert '"n_items"' in capsys.readouterr().out

    assert cli_main(["uc2", "--dock-days", "3", "--json"]) == 0
    out = capsys.readouterr().out.replace(" ", "")
    assert '"dock_days":3' in out

    assert cli_main(["uc3", "--case", "civil_7", "--lang", "ja", "--json"]) == 0
    assert "civil_7" in capsys.readouterr().out


def test_demo_http_routes():
    from fastapi.testclient import TestClient

    from marine_claims_ai.demo.app import create_app

    client = TestClient(create_app())
    assert client.get("/").status_code == 200
    assert client.get("/uc2").status_code == 200
    assert client.get("/uc3").status_code == 200
    assert client.get("/partials/uc2").status_code == 200
    r = client.get("/set-lang?lang=ja&next=/uc1")
    assert r.status_code in (303, 307, 200)
    md = client.get("/export/survey.md")
    assert md.status_code == 200
    assert "attachment" in md.headers.get("content-disposition", "")
