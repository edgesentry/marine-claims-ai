"""CLI for the same demo capabilities as the Web UI (no FastAPI required)."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from marine_claims_ai.demo.i18n import Lang
from marine_claims_ai.demo.ops import (
    Uc2Params,
    Uc3Params,
    clear_cache,
    export_uc2,
    export_uc3,
    format_uc2_summary,
    format_uc3_summary,
    list_cases,
    run_uc2,
    run_uc3,
    write_export,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="marine-claims-demo",
        description=(
            "MarineClaims AI executive demo — Rule D5 + COLREGS (same as the Web UI). "
            "Use `serve` for the HTMX app (requires: uv sync --group demo)."
        ),
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_serve = sub.add_parser("serve", help="Launch FastAPI + HTMX Web UI")
    p_serve.add_argument("--host", default="127.0.0.1")
    p_serve.add_argument("--port", type=int, default=8765)
    p_serve.add_argument("--reload", action="store_true")

    p2 = sub.add_parser("uc2", help="AAA Rule D5 apportionment + off-hire simulator", parents=[_lang_parent()])
    _add_uc2_params(p2)
    p2.add_argument("--export-md", type=Path)
    p2.add_argument("--export-html", type=Path)
    p2.add_argument("--json", action="store_true")

    p3 = sub.add_parser("uc3", help="COLREGS radar / fault-ratio evidence", parents=[_lang_parent()])
    p3.add_argument("--case", dest="case_id", default=None, help="Case id (see list-cases)")
    p3.add_argument("--doc", dest="doc_pdf", default=None, help="Ruling / judgment / casualty PDF")
    p3.add_argument("--analyze", action="store_true", help="Parse PDF live")
    p3.add_argument("--heading-a", type=float, default=None, dest="heading_a_deg")
    p3.add_argument("--heading-b", type=float, default=None, dest="heading_b_deg")
    p3.add_argument("--bearing-ab", type=float, default=None, dest="true_bearing_a_to_b_deg")
    p3.add_argument("--export-md", type=Path)
    p3.add_argument("--export-html", type=Path)
    p3.add_argument("--json", action="store_true")

    sub.add_parser("list-cases", help="List UC3 fixture case ids", parents=[_lang_parent()])
    sub.add_parser(
        "clear-cache",
        help="Clear demo analysis JSON, PDF page previews, uploads, and in-memory loaders",
    )

    args = parser.parse_args(argv)
    lang: Lang = "ja" if getattr(args, "lang", "en") == "ja" else "en"

    if args.cmd == "serve":
        return _serve(args)
    if args.cmd == "clear-cache":
        stats = clear_cache()
        print(
            "Cleared demo cache: "
            f"analysis_json={stats['analysis_json']} "
            f"pdf_pages={stats['pdf_pages']} "
            f"uploads={stats['uploads']}"
        )
        return 0
    if args.cmd == "list-cases":
        return _list_cases(lang)
    if args.cmd == "uc2":
        return _cmd_uc2(args, lang)
    if args.cmd == "uc3":
        return _cmd_uc3(args, lang)
    parser.error(f"unknown command: {args.cmd}")
    return 2


def _lang_parent() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(add_help=False)
    p.add_argument("--lang", choices=("en", "ja"), default="en")
    return p


def _add_uc2_params(p: argparse.ArgumentParser) -> None:
    p.add_argument("--daily-dock-rate", type=int, default=860_000)
    p.add_argument("--dock-days", type=int, default=5)
    p.add_argument("--hire-rate", type=int, default=4_000_000)
    p.add_argument("--legacy-lead-days", type=int, default=21)
    p.add_argument("--ai-lead-minutes", type=int, default=15)
    p.add_argument(
        "--docking-context",
        choices=("casualty_immediate", "deferred_to_routine"),
        default="casualty_immediate",
    )
    p.add_argument(
        "--no-statutory",
        action="store_true",
        help="Omit statutory SAFE line (can flip ¶2(a) → ¶1 under immediate docking)",
    )
    p.add_argument("--spec", dest="spec_pdf", default=None, help="Drydock / repair specification PDF")
    p.add_argument("--analyze", action="store_true", help="Parse PDF live")


def _uc2_params(args: argparse.Namespace) -> Uc2Params:
    return Uc2Params(
        daily_dock_rate=args.daily_dock_rate,
        dock_days=args.dock_days,
        hire_rate=args.hire_rate,
        legacy_lead_days=args.legacy_lead_days,
        ai_lead_minutes=args.ai_lead_minutes,
        docking_context=args.docking_context,
        include_statutory=not args.no_statutory,
        spec_pdf=getattr(args, "spec_pdf", None),
        analyze=bool(getattr(args, "analyze", False)),
    )


def _uc3_params(args: argparse.Namespace) -> Uc3Params:
    return Uc3Params(
        case_id=args.case_id,
        heading_a_deg=args.heading_a_deg,
        heading_b_deg=args.heading_b_deg,
        true_bearing_a_to_b_deg=args.true_bearing_a_to_b_deg,
        doc_pdf=getattr(args, "doc_pdf", None),
        analyze=bool(getattr(args, "analyze", False)),
    )


def _serve(args: argparse.Namespace) -> int:
    try:
        import uvicorn
    except ImportError:
        print("Web UI deps missing. Install with: uv sync --group demo", file=sys.stderr)
        return 1
    from marine_claims_ai.demo.logging_setup import DEMO_LOG_PATH, setup_demo_logging

    setup_demo_logging()
    print(f"MarineClaims AI demo → http://{args.host}:{args.port}/")
    print(f"Demo log file → {DEMO_LOG_PATH}")
    uvicorn.run(
        "marine_claims_ai.demo.app:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
    )
    return 0


def _list_cases(lang: Lang) -> int:
    for c in list_cases(lang):
        print(f"{c['id']}\t{c['source']}\t{c['title']}")
    return 0


def _cmd_uc2(args: argparse.Namespace, lang: Lang) -> int:
    params = _uc2_params(args)
    uc2 = run_uc2(lang, params)
    if args.json:
        print(json.dumps(_uc2_json(uc2), ensure_ascii=False, indent=2))
    else:
        print(format_uc2_summary(uc2, lang))
    if args.export_md:
        _, body = export_uc2(lang, params=params, fmt="md")
        print(f"wrote {write_export(args.export_md, body)}")
    if args.export_html:
        _, body = export_uc2(lang, params=params, fmt="html")
        print(f"wrote {write_export(args.export_html, body)}")
    return 0


def _cmd_uc3(args: argparse.Namespace, lang: Lang) -> int:
    try:
        params = _uc3_params(args)
        uc3 = run_uc3(lang, params)
        if not uc3.get("ok"):
            print(uc3.get("error"), file=sys.stderr)
            return 1
        if args.json:
            print(json.dumps(_uc3_json(uc3), ensure_ascii=False, indent=2))
        else:
            print(format_uc3_summary(uc3, lang))
        if args.export_md:
            _, body = export_uc3(lang, case_id=args.case_id, fmt="md")
            print(f"wrote {write_export(args.export_md, body)}")
        if args.export_html:
            _, body = export_uc3(lang, case_id=args.case_id, fmt="html")
            print(f"wrote {write_export(args.export_html, body)}")
        return 0
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 1


def _uc2_json(uc2: dict) -> dict:
    return {
        "ok": True,
        "rule": uc2["rule"],
        "dock_total": uc2["dock_total"],
        "insurer_common": uc2["insurer_common"],
        "owner_common": uc2["owner_common"],
        "days_saved": uc2["days_saved"],
        "offhire_jpy": uc2["offhire_jpy"],
        "params": {
            "daily_dock_rate": uc2["daily_dock_rate"],
            "dock_days": uc2["dock_days"],
            "hire_rate": uc2["hire_rate"],
            "legacy_lead_days": uc2["legacy_lead_days"],
            "ai_lead_minutes": uc2["ai_lead_minutes"],
            "docking_context": uc2["docking_context"],
            "include_statutory": uc2["include_statutory"],
        },
        "line_rows": uc2["line_rows"],
    }


def _uc3_json(uc3: dict) -> dict:
    return {
        "ok": True,
        "case_id": uc3["case_id"],
        "title": uc3["title"],
        "situation": uc3["situation"],
        "role_a": uc3["role_a"],
        "role_b": uc3["role_b"],
        "fault_ratio": uc3["fault_ratio"],
        "relative_bearing": uc3["relative_bearing"],
        "rule_citations": uc3["rule_citations"],
        "overrides_applied": uc3.get("overrides_applied"),
        "geometry": uc3.get("geometry"),
    }


if __name__ == "__main__":
    raise SystemExit(main())
