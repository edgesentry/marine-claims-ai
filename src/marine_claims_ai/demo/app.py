"""FastAPI application for the interactive 3-use-case executive demo.

All business logic lives in ``marine_claims_ai.demo.ops`` / ``services`` so the
CLI (``demo.cli``) exposes the same capabilities without a browser.
"""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

from fastapi import Cookie, FastAPI, Query, Request, Response
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from marine_claims_ai.demo.i18n import Lang, t
from marine_claims_ai.demo.ops import Uc2Params, export_uc1, export_uc2, export_uc3, run_uc1, run_uc2, run_uc3

DEMO_DIR = Path(__file__).resolve().parent
TEMPLATES_DIR = DEMO_DIR / "templates"
STATIC_DIR = DEMO_DIR / "static"

templates = Jinja2Templates(directory=str(TEMPLATES_DIR))
templates.env.globals["t"] = t


def create_app() -> FastAPI:
    app = FastAPI(title="MarineClaims AI Demo", docs_url=None, redoc_url=None)
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

    @app.get("/", response_class=HTMLResponse)
    def home(request: Request, demo_lang: Annotated[str | None, Cookie()] = None):
        lang = _lang(demo_lang)
        return _page(request, "uc1.html", "uc1", lang, uc1=run_uc1(lang))

    @app.get("/uc1", response_class=HTMLResponse)
    def uc1_page(request: Request, demo_lang: Annotated[str | None, Cookie()] = None):
        lang = _lang(demo_lang)
        return _page(request, "uc1.html", "uc1", lang, uc1=run_uc1(lang))

    @app.get("/uc2", response_class=HTMLResponse)
    def uc2_page(request: Request, demo_lang: Annotated[str | None, Cookie()] = None):
        lang = _lang(demo_lang)
        return _page(request, "uc2.html", "uc2", lang, uc2=run_uc2(lang))

    @app.get("/uc3", response_class=HTMLResponse)
    def uc3_page(
        request: Request,
        case_id: str | None = None,
        demo_lang: Annotated[str | None, Cookie()] = None,
    ):
        lang = _lang(demo_lang)
        return _page(request, "uc3.html", "uc3", lang, uc3=run_uc3(lang, case_id=case_id))

    @app.get("/set-lang")
    def set_lang(lang: str = Query("en"), next: str = Query("/")):
        loc = "ja" if lang == "ja" else "en"
        target = next if next.startswith("/") else "/"
        resp = RedirectResponse(url=target, status_code=303)
        resp.set_cookie("demo_lang", loc, max_age=60 * 60 * 24 * 365, httponly=False, samesite="lax")
        return resp

    @app.get("/partials/uc2", response_class=HTMLResponse)
    def uc2_partial(
        request: Request,
        daily_dock_rate: int = 860_000,
        dock_days: int = 5,
        hire_rate: int = 4_000_000,
        legacy_lead_days: int = 21,
        ai_lead_minutes: int = 15,
        demo_lang: Annotated[str | None, Cookie()] = None,
    ):
        lang = _lang(demo_lang)
        params = Uc2Params(
            daily_dock_rate=daily_dock_rate,
            dock_days=dock_days,
            hire_rate=hire_rate,
            legacy_lead_days=legacy_lead_days,
            ai_lead_minutes=ai_lead_minutes,
        )
        return templates.TemplateResponse(
            request,
            "partials/uc2_results.html",
            {"lang": lang, "uc2": run_uc2(lang, params)},
        )

    @app.get("/partials/uc3", response_class=HTMLResponse)
    def uc3_partial(
        request: Request,
        case_id: str | None = None,
        demo_lang: Annotated[str | None, Cookie()] = None,
    ):
        lang = _lang(demo_lang)
        return templates.TemplateResponse(
            request,
            "partials/uc3_results.html",
            {"lang": lang, "uc3": run_uc3(lang, case_id=case_id)},
        )

    @app.get("/export/survey.md")
    def export_survey_md(demo_lang: Annotated[str | None, Cookie()] = None):
        return _export_uc1(_lang(demo_lang), "md", "preliminary_survey.md", "text/markdown; charset=utf-8")

    @app.get("/export/survey.html")
    def export_survey_html_route(demo_lang: Annotated[str | None, Cookie()] = None):
        return _export_uc1(_lang(demo_lang), "html", "preliminary_survey.html", "text/html; charset=utf-8")

    @app.get("/export/apportionment.md")
    def export_apportion_md(
        daily_dock_rate: int = 860_000,
        dock_days: int = 5,
        hire_rate: int = 4_000_000,
        legacy_lead_days: int = 21,
        ai_lead_minutes: int = 15,
        demo_lang: Annotated[str | None, Cookie()] = None,
    ):
        return _export_uc2(
            _lang(demo_lang),
            Uc2Params(daily_dock_rate, dock_days, hire_rate, legacy_lead_days, ai_lead_minutes),
            "md",
            "rule_d5_apportionment.md",
            "text/markdown; charset=utf-8",
        )

    @app.get("/export/apportionment.html")
    def export_apportion_html(
        daily_dock_rate: int = 860_000,
        dock_days: int = 5,
        hire_rate: int = 4_000_000,
        legacy_lead_days: int = 21,
        ai_lead_minutes: int = 15,
        demo_lang: Annotated[str | None, Cookie()] = None,
    ):
        return _export_uc2(
            _lang(demo_lang),
            Uc2Params(daily_dock_rate, dock_days, hire_rate, legacy_lead_days, ai_lead_minutes),
            "html",
            "rule_d5_apportionment.html",
            "text/html; charset=utf-8",
        )

    @app.get("/export/colregs.md")
    def export_colregs_md(
        case_id: str | None = None,
        demo_lang: Annotated[str | None, Cookie()] = None,
    ):
        return _export_uc3(_lang(demo_lang), case_id, "md", "colregs_fault_memo.md", "text/markdown; charset=utf-8")

    @app.get("/export/colregs.html")
    def export_colregs_html(
        case_id: str | None = None,
        demo_lang: Annotated[str | None, Cookie()] = None,
    ):
        return _export_uc3(_lang(demo_lang), case_id, "html", "colregs_fault_memo.html", "text/html; charset=utf-8")

    return app


def _export_uc1(lang: Lang, fmt: str, filename: str, media_type: str) -> Response:
    try:
        _, body = export_uc1(lang, fmt=fmt)  # type: ignore[arg-type]
    except FileNotFoundError as exc:
        return Response(str(exc), status_code=404, media_type="text/plain")
    return _download(body, filename, media_type)


def _export_uc2(lang: Lang, params: Uc2Params, fmt: str, filename: str, media_type: str) -> Response:
    _, body = export_uc2(lang, params=params, fmt=fmt)  # type: ignore[arg-type]
    return _download(body, filename, media_type)


def _export_uc3(lang: Lang, case_id: str | None, fmt: str, filename: str, media_type: str) -> Response:
    try:
        _, body = export_uc3(lang, case_id=case_id, fmt=fmt)  # type: ignore[arg-type]
    except ValueError:
        return Response("Requested resource was not found.", status_code=404, media_type="text/plain")
    return _download(body, filename, media_type)


def _lang(cookie: str | None) -> Lang:
    return "ja" if cookie == "ja" else "en"


def _page(request: Request, template: str, active: str, lang: Lang, **ctx):
    return templates.TemplateResponse(
        request,
        template,
        {
            "lang": lang,
            "active": active,
            "path": request.url.path,
            **ctx,
        },
    )


def _download(body: str, filename: str, media_type: str) -> Response:
    return Response(
        content=body.encode("utf-8"),
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


app = create_app()
