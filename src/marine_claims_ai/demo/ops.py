"""Shared demo operations used by both CLI and Web UI."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from marine_claims_ai.demo import export as export_mod
from marine_claims_ai.demo.i18n import Lang, t
from marine_claims_ai.demo.services import build_uc1, build_uc2, build_uc3, list_uc3_cases

ExportFormat = Literal["md", "html"]


@dataclass(frozen=True)
class Uc2Params:
    """Rule D5 / off-hire knobs shared by CLI flags and Web sliders."""

    daily_dock_rate: int = 860_000
    dock_days: int = 5
    hire_rate: int = 4_000_000
    legacy_lead_days: int = 21
    ai_lead_minutes: int = 15

    def as_kwargs(self) -> dict[str, int]:
        return {
            "daily_dock_rate": self.daily_dock_rate,
            "dock_days": self.dock_days,
            "hire_rate": self.hire_rate,
            "legacy_lead_days": self.legacy_lead_days,
            "ai_lead_minutes": self.ai_lead_minutes,
        }


def run_uc1(lang: Lang = "en", *, sample_excluded: int = 40) -> dict[str, Any]:
    return build_uc1(lang, sample_excluded=sample_excluded)


def run_uc2(lang: Lang = "en", params: Uc2Params | None = None) -> dict[str, Any]:
    p = params or Uc2Params()
    return build_uc2(lang, **p.as_kwargs())


def run_uc3(lang: Lang = "en", *, case_id: str | None = None) -> dict[str, Any]:
    return build_uc3(lang, case_id=case_id)


def list_cases(lang: Lang = "en") -> list[dict[str, str]]:
    return list_uc3_cases(lang)


def export_uc1(
    lang: Lang = "en",
    *,
    fmt: ExportFormat = "md",
    sample_excluded: int = 40,
) -> tuple[dict[str, Any], str]:
    uc1 = run_uc1(lang, sample_excluded=sample_excluded)
    if not uc1.get("ok"):
        raise FileNotFoundError(uc1.get("error") or t("data_missing", lang))
    if fmt == "html":
        body = export_mod.survey_html(uc1["summary_for_export"], uc1["items_for_export"], lang)
    else:
        body = export_mod.survey_markdown(uc1["summary_for_export"], uc1["items_for_export"], lang)
    return uc1, body


def export_uc2(
    lang: Lang = "en",
    *,
    params: Uc2Params | None = None,
    fmt: ExportFormat = "md",
) -> tuple[dict[str, Any], str]:
    uc2 = run_uc2(lang, params)
    if fmt == "html":
        body = export_mod.apportionment_html(uc2, lang)
    else:
        body = export_mod.apportionment_markdown(uc2, lang)
    return uc2, body


def export_uc3(
    lang: Lang = "en",
    *,
    case_id: str | None = None,
    fmt: ExportFormat = "md",
) -> tuple[dict[str, Any], str]:
    uc3 = run_uc3(lang, case_id=case_id)
    if not uc3.get("ok"):
        raise ValueError(uc3.get("error") or "COLREGS case unavailable")
    if fmt == "html":
        body = export_mod.colregs_survey_html(uc3, lang)
    else:
        body = export_mod.colregs_survey_markdown(uc3, lang)
    return uc3, body


def write_export(path: Path | str, body: str) -> Path:
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(body, encoding="utf-8")
    return out


def format_uc1_summary(uc1: dict[str, Any], lang: Lang = "en") -> str:
    if not uc1.get("ok"):
        return str(uc1.get("error") or t("data_missing", lang))
    lines = [
        t("uc1_title", lang),
        f"  {t('metric_items', lang)}: {uc1['n_items']}",
        f"  {t('metric_claimed', lang)}: ¥{uc1['claimed']:,}",
        f"  {t('metric_excluded', lang)}: ¥{uc1['excluded_jpy']:,}",
        f"  {t('metric_rate', lang)}: {uc1['rate']}%",
        f"  counts: covered={uc1['counts']['covered']} "
        f"apportioned={uc1['counts']['apportioned']} "
        f"excluded={uc1['counts']['excluded']}",
    ]
    sample = uc1.get("rows") or []
    if sample:
        lines.append("")
        lines.append(t("line_items", lang) + ":")
        for row in sample[:12]:
            lines.append(
                f"  [{row['status_label']}] {row['description'][:70]}  ¥{row['amount']:,}"
            )
        if len(sample) > 12:
            lines.append(f"  … ({len(sample) - 12} more in export)")
    return "\n".join(lines)


def format_uc2_summary(uc2: dict[str, Any], lang: Lang = "en") -> str:
    lines = [
        t("uc2_title", lang),
        f"  {t('rule_label', lang)}: {uc2['rule']}",
        f"  {t('common_dues', lang)}: ¥{uc2['dock_total']:,}",
        f"  {t('insurer_share', lang)}: ¥{uc2['insurer_common']:,}",
        f"  {t('owner_share', lang)}: ¥{uc2['owner_common']:,}",
        f"  {t('days_saved', lang)}: {uc2['days_saved']}",
        f"  {t('offhire_saved', lang)}: ¥{uc2['offhire_jpy']:,}",
        "",
        f"  params: dock_rate={uc2['daily_dock_rate']:,}/day × {uc2['dock_days']}d, "
        f"hire={uc2['hire_rate']:,}/day, legacy={uc2['legacy_lead_days']}d, "
        f"ai={uc2['ai_lead_minutes']}min",
    ]
    return "\n".join(lines)


def format_uc3_summary(uc3: dict[str, Any], lang: Lang = "en") -> str:
    if not uc3.get("ok"):
        return str(uc3.get("error") or "error")
    lines = [
        t("uc3_title", lang),
        f"  case: {uc3['case_id']} — {uc3['title']}",
        f"  {t('situation', lang)}: {uc3['situation_label']} ({uc3['situation']})",
        f"  {t('role_a', lang)}: {uc3['role_a_label']}",
        f"  {t('role_b', lang)}: {uc3['role_b_label']}",
        f"  {t('fault_ratio', lang)}: {uc3['fault_ratio']}",
        f"  bearing: {uc3['relative_bearing']}°",
    ]
    if uc3.get("rule_citations"):
        lines.append(f"  {t('article', lang)}: {'; '.join(uc3['rule_citations'])}")
    return "\n".join(lines)
