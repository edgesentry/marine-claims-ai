"""End-to-end tests for demo CLI and Web UI (local only; not required in CI).

Run after ``uv sync --group demo``::

    uv run pytest -m demo -q
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from marine_claims_ai.demo import loaders
from marine_claims_ai.demo.cli import main as cli_main
from marine_claims_ai.paths import REPO_ROOT

pytestmark = pytest.mark.demo

FIXTURE = REPO_ROOT / "config" / "demo_e2e_claims_analysis_min.json"
CLI_SCRIPT = REPO_ROOT / "scripts" / "run_demo_cli.py"


@pytest.fixture
def demo_kaiyomaru(monkeypatch: pytest.MonkeyPatch):
    """Point UC1 loaders at the tracked synthetic fixture."""
    assert FIXTURE.is_file()
    loaders.clear_loader_caches()
    monkeypatch.setattr(loaders, "resolve_kaiyomaru_path", lambda: FIXTURE)
    yield FIXTURE
    loaders.clear_loader_caches()


def _run_cli(*args: str) -> subprocess.CompletedProcess[str]:
    cmd = [sys.executable, str(CLI_SCRIPT), *args]
    env = os.environ.copy()
    src = str(REPO_ROOT / "src")
    env["PYTHONPATH"] = src + (os.pathsep + env["PYTHONPATH"] if env.get("PYTHONPATH") else "")
    return subprocess.run(
        cmd,
        cwd=str(REPO_ROOT),
        env=env,
        capture_output=True,
        text=True,
        check=False,
        timeout=120,
    )


def _json_payload(stdout: str) -> dict:
    text = stdout.strip()
    if "wrote" in text:
        text = text[: text.index("wrote")].strip()
    return json.loads(text)


def test_e2e_cli_list_cases_and_uc3(tmp_path: Path):
    listed = _run_cli("list-cases")
    assert listed.returncode == 0, listed.stderr
    assert "civil_7" in listed.stdout

    md = tmp_path / "colregs.md"
    html = tmp_path / "colregs.html"
    run = _run_cli(
        "uc3",
        "--case",
        "civil_7",
        "--lang",
        "en",
        "--json",
        "--export-md",
        str(md),
        "--export-html",
        str(html),
    )
    assert run.returncode == 0, run.stderr
    payload = _json_payload(run.stdout)
    assert payload["case_id"] == "civil_7"
    assert payload["fault_ratio"]
    assert md.is_file() and md.stat().st_size > 50
    assert "<html" in html.read_text(encoding="utf-8").lower()


def test_e2e_cli_uc2_export(tmp_path: Path):
    md = tmp_path / "d5.md"
    run = _run_cli(
        "uc2",
        "--dock-days",
        "4",
        "--daily-dock-rate",
        "900000",
        "--json",
        "--export-md",
        str(md),
    )
    assert run.returncode == 0, run.stderr
    payload = _json_payload(run.stdout)
    assert payload["params"]["dock_days"] == 4
    assert payload["insurer_common"] + payload["owner_common"] == payload["dock_total"]
    assert "D5" in md.read_text(encoding="utf-8")


def test_e2e_cli_uc1_with_fixture(demo_kaiyomaru: Path, tmp_path: Path):
    out_md = tmp_path / "survey.md"
    out_html = tmp_path / "survey.html"
    rc = cli_main(
        [
            "uc1",
            "--lang",
            "ja",
            "--json",
            "--export-md",
            str(out_md),
            "--export-html",
            str(out_html),
        ]
    )
    assert rc == 0
    assert out_md.is_file() and "予備" in out_md.read_text(encoding="utf-8")
    assert out_html.is_file()


@pytest.fixture
def web_client(demo_kaiyomaru: Path):
    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient

    from marine_claims_ai.demo.app import create_app

    return TestClient(create_app())


def test_e2e_web_uc1_page_and_exports(web_client):
    r = web_client.get("/uc1")
    assert r.status_code == 200
    assert "pill" in r.text or "EXCLUDED" in r.text or "除外" in r.text

    md = web_client.get("/export/survey.md")
    assert md.status_code == 200
    assert "attachment" in md.headers.get("content-disposition", "")
    assert b"Preliminary" in md.content or "予備".encode() in md.content

    html = web_client.get("/export/survey.html")
    assert html.status_code == 200
    assert b"<html" in html.content.lower()


def test_e2e_web_uc2_partial_and_exports(web_client):
    page = web_client.get("/uc2")
    assert page.status_code == 200
    assert "/analyze/uc2" in page.text
    assert "spec_pdf" in page.text or "doc_uc2" in page.text.lower() or "入渠" in page.text

    partial = web_client.get(
        "/partials/uc2",
        params={
            "daily_dock_rate": 900_000,
            "dock_days": 4,
            "hire_rate": 4_000_000,
            "legacy_lead_days": 21,
            "ai_lead_minutes": 15,
            "include_statutory": "1",
        },
    )
    assert partial.status_code == 200
    assert "D5" in partial.text
    assert "3,600,000" in partial.text or "3600000" in partial.text.replace(",", "")

    md = web_client.get("/export/apportionment.md", params={"dock_days": 4, "daily_dock_rate": 900_000})
    assert md.status_code == 200
    assert b"D5" in md.content


def test_e2e_web_uc3_case_switch_and_exports(web_client):
    page = web_client.get("/uc3", params={"case_id": "civil_7"})
    assert page.status_code == 200
    assert "70:30" in page.text or "あたご" in page.text

    partial = web_client.get("/partials/uc3", params={"case_id": "civil_7"})
    assert partial.status_code == 200
    assert "70:30" in partial.text
    assert "svg" in partial.text.lower()

    md = web_client.get("/export/colregs.md", params={"case_id": "civil_7"})
    assert md.status_code == 200
    assert b"70:30" in md.content or b"COLREGS" in md.content


def test_e2e_web_i18n_cookie_and_static(web_client):
    set_lang = web_client.get("/set-lang", params={"lang": "ja", "next": "/uc2"}, follow_redirects=False)
    assert set_lang.status_code in (303, 307)
    assert "demo_lang" in set_lang.headers.get("set-cookie", "")

    ja = web_client.get("/uc2", cookies={"demo_lang": "ja"})
    assert ja.status_code == 200
    assert "按分" in ja.text or "休航" in ja.text

    en = web_client.get("/uc1", cookies={"demo_lang": "en"})
    assert en.status_code == 200
    assert "Watertight" in en.text or "topology" in en.text.lower()

    assert web_client.get("/static/demo.css").status_code == 200
    assert len(web_client.get("/static/vendor/htmx.min.js").content) > 1000
    assert len(web_client.get("/static/vendor/chart.umd.min.js").content) > 1000


def test_e2e_cli_web_export_parity(web_client):
    from marine_claims_ai.demo.ops import Uc2Params, export_uc2

    params = Uc2Params(daily_dock_rate=900_000, dock_days=4)
    _, cli_body = export_uc2("en", params=params, fmt="md")
    web = web_client.get(
        "/export/apportionment.md",
        params={"daily_dock_rate": 900_000, "dock_days": 4},
    )
    assert web.status_code == 200
    assert web.content.decode("utf-8") == cli_body
