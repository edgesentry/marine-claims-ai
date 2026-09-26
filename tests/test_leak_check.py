from __future__ import annotations

from marine_claims_ai.ci.leak_check import (
    check_banned_tracked_files,
    is_json_allowed,
    is_scannable_text,
    resolve_diff_range,
    scan_line,
)


def test_json_allowlist_only_config():
    assert is_json_allowed("config/benchmark_rules.json") is True
    assert is_json_allowed("config/nested/rules.json") is True
    assert is_json_allowed("datasets/benchmark.json") is False
    assert is_json_allowed("src/marine_claims_ai/foo.py") is False


def test_banned_tracked_files():
    tracked = [
        "README.md",
        "config/benchmark_rules.json",
        "secret.pdf",
        "data/leak.json",
        "notes.csv",
    ]
    violations = check_banned_tracked_files(tracked)
    assert any("secret.pdf" in v for v in violations)
    assert any("leak.json" in v for v in violations)
    assert any("notes.csv" in v for v in violations)
    assert not any("benchmark_rules.json" in v for v in violations)


def test_scan_line_detects_private_paths_and_secrets():
    # Assemble probes so this test file itself is not flagged by the leak scanner.
    macos_path = "/" + "/".join(["Users", "alice", "secret", "file"])
    hits = scan_line("x.py", 1, f'path = "{macos_path}"')
    assert hits and "macOS home" in hits[0]

    hits = scan_line("x.py", 2, 'api_' + 'key = "sk-test-123456"')
    assert hits and "API key" in hits[0]

    enterprise = "marine-claims-knowledge-" + "enterprise"
    hits = scan_line("x.py", 3, f"from {enterprise} import x")
    assert hits and "enterprise" in hits[0]

    # Actions runner home should not trip Linux home detector
    runner_cwd = "/" + "/".join(["home", "runner", "work", "repo"])
    assert scan_line("x.py", 4, f"cwd={runner_cwd}") == []


def test_scannable_text_skips_leak_checker_itself():
    assert is_scannable_text("src/marine_claims_ai/ci/leak_check.py") is False
    assert is_scannable_text("src/marine_claims_ai/index/search.py") is True


def test_resolve_diff_range_explicit_and_pr(monkeypatch):
    assert resolve_diff_range("origin/main") == "origin/main...HEAD"
    monkeypatch.setenv("GITHUB_EVENT_NAME", "pull_request")
    monkeypatch.setenv("GITHUB_BASE_REF", "main")
    assert resolve_diff_range(None) == "origin/main...HEAD"
    monkeypatch.setenv("GITHUB_EVENT_NAME", "push")
    assert resolve_diff_range(None) is None
