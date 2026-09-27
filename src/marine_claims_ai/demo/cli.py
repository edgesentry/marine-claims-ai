"""CLI for the same demo capabilities as the Web UI (no FastAPI required)."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from marine_claims_ai.demo.i18n import Lang
from marine_claims_ai.demo.ops import (
    Uc2Params,
    export_uc1,
    export_uc2,
    export_uc3,
    format_uc1_summary,
    format_uc2_summary,
    format_uc3_summary,
    list_cases,
    run_uc1,
    run_uc2,
    run_uc3,
    write_export,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="marine-claims-demo",
        description=(
            "MarineClaims AI executive demo — same UC1/UC2/UC3 + exports as the Web UI. "
            "Use `serve` for the HTMX app (requires: uv sync --group demo)."
        ),
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_serve = sub.add_parser("serve", help="Launch FastAPI + HTMX Web UI")
    p_serve.add_argument("--host", default="127.0.0.1")
    p_serve.add_argument("--port", type=int, default=8765)
    p_serve.add_argument("--reload", action="store_true")

    p1 = sub.add_parser("uc1", help="Topology / owner's work exclusion (Kaiyo Maru)", parents=[_lang_parent()])
    p1.add_argument("--export-md", type=Path, help="Write survey Markdown")
    p1.add_argument("--export-html", type=Path, help="Write printable HTML survey")
    p1.add_argument("--json", action="store_true", help="Print machine-readable JSON summary")
    p1.add_argument("--sample-excluded", type=int, default=40)

    p2 = sub.add_parser("uc2", help="AAA Rule D5 apportionment + off-hire simulator", parents=[_lang_parent()])
    _add_uc2_params(p2)
    p2.add_argument("--export-md", type=Path)
    p2.add_argument("--export-html", type=Path)
    p2.add_argument("--json", action="store_true")

    p3 = sub.add_parser("uc3", help="COLREGS radar / fault-ratio evidence", parents=[_lang_parent()])
    p3.add_argument("--case", dest="case_id", default=None, help="Case id (see list-cases)")
    p3.add_argument("--export-md", type=Path)
    p3.add_argument("--export-html", type=Path)
    p3.add_argument("--json", action="store_true")

    sub.add_parser("list-cases", help="List UC3 fixture case ids", parents=[_lang_parent()])

    args = parser.parse_args(argv)
    lang: Lang = "ja" if getattr(args, "lang", "en") == "ja" else "en"

    if args.cmd == "serve":
        return _serve(args)
    if args.cmd == "list-cases":
        return _list_cases(lang)
    if args.cmd == "uc1":
        return _cmd_uc1(args, lang)
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


def _uc2_params(args: argparse.Namespace) -> Uc2Params:
    return Uc2Params(
        daily_dock_rate=args.daily_dock_rate,
        dock_days=args.dock_days,
        hire_rate=args.hire_rate,
        legacy_lead_days=args.legacy_lead_days,
        ai_lead_minutes=args.ai_lead_minutes,
    )


def _serve(args: argparse.Namespace) -> int:
    try:
        import uvicorn
    except ImportError:
        print("Web UI deps missing. Install with: uv sync --group demo", file=sys.stderr)
        return 1
    print(f"MarineClaims AI demo → http://{args.host}:{args.port}/")
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


def _cmd_uc1(args: argparse.Namespace, lang: Lang) -> int:
    try:
        uc1 = run_uc1(lang, sample_excluded=args.sample_excluded)
        if not uc1.get("ok"):
            print(uc1.get("error"), file=sys.stderr)
            return 1
        if args.json:
            print(json.dumps(_uc1_json(uc1), ensure_ascii=False, indent=2))
        else:
            print(format_uc1_summary(uc1, lang))
        if args.export_md:
            _, body = export_uc1(lang, fmt="md", sample_excluded=args.sample_excluded)
            print(f"wrote {write_export(args.export_md, body)}")
        if args.export_html:
            _, body = export_uc1(lang, fmt="html", sample_excluded=args.sample_excluded)
            print(f"wrote {write_export(args.export_html, body)}")
        return 0
    except FileNotFoundError as exc:
        print(str(exc), file=sys.stderr)
        return 1


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
        uc3 = run_uc3(lang, case_id=args.case_id)
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


def _uc1_json(uc1: dict) -> dict:
    return {
        "ok": True,
        "n_items": uc1["n_items"],
        "claimed": uc1["claimed"],
        "excluded_jpy": uc1["excluded_jpy"],
        "approved_jpy": uc1["approved_jpy"],
        "rate": uc1["rate"],
        "counts": uc1["counts"],
    }


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
    }


if __name__ == "__main__":
    raise SystemExit(main())
