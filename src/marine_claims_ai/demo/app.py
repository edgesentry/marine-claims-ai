"""FastAPI application for the interactive executive demo (Rule D5 + COLREGS).

All business logic lives in ``marine_claims_ai.demo.ops`` / ``services`` so the
CLI (``demo.cli``) exposes the same capabilities without a browser.
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Annotated
from urllib.parse import urlparse

from fastapi import Cookie, FastAPI, File, Form, Query, Request, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from marine_claims_ai.demo.documents import label_for_pdf, resolve_pdf, save_upload
from marine_claims_ai.demo.i18n import Lang, t
from marine_claims_ai.demo.logging_setup import get_demo_logger, setup_demo_logging
from marine_claims_ai.demo.ops import (
    Uc2Params,
    Uc3Params,
    clear_cache,
    export_uc2,
    export_uc3,
    run_uc2,
    run_uc3,
)
from marine_claims_ai.demo.pdf_preview import ensure_pdf_page_previews
from marine_claims_ai.ingest.pdf_text import pdf_to_text

log = get_demo_logger("app")


DEMO_DIR = Path(__file__).resolve().parent
TEMPLATES_DIR = DEMO_DIR / "templates"
STATIC_DIR = DEMO_DIR / "static"

templates = Jinja2Templates(directory=str(TEMPLATES_DIR))
templates.env.globals["t"] = t


def create_app() -> FastAPI:
    setup_demo_logging()
    app = FastAPI(title="MarineClaims AI Demo", docs_url=None, redoc_url=None)
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

    @app.middleware("http")
    async def _log_requests(request: Request, call_next):
        t0 = time.perf_counter()
        response = await call_next(request)
        ms = (time.perf_counter() - t0) * 1000
        # Skip noisy static assets
        path = request.url.path
        if not path.startswith("/static/"):
            log.info("%s %s → %s (%.0fms)", request.method, path, response.status_code, ms)
        return response

    @app.get("/", response_class=HTMLResponse)
    def home(request: Request, demo_lang: Annotated[str | None, Cookie()] = None):
        lang = _lang(demo_lang)
        return _page(request, "uc2.html", "uc2", lang, uc2=run_uc2(lang))

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
        candidate = next.replace("\\", "")
        parsed = urlparse(candidate)
        target = candidate if candidate.startswith("/") and not parsed.scheme and not parsed.netloc else "/"
        resp = RedirectResponse(url=target, status_code=303)
        resp.set_cookie("demo_lang", loc, max_age=60 * 60 * 24 * 365, httponly=False, samesite="lax")
        return resp

    @app.post("/demo/clear-cache")
    def clear_demo_cache(
        next: str = Form("/uc2"),
        demo_lang: Annotated[str | None, Cookie()] = None,
    ):
        _ = demo_lang
        stats = clear_cache()
        log.info("clear-cache %s", stats)
        target = _safe_next(next)
        sep = "&" if "?" in target else "?"
        return RedirectResponse(url=f"{target}{sep}cache_cleared=1", status_code=303)

    @app.post("/upload")
    async def upload_pdf(
        file: UploadFile = File(...),
        next: str = Form("/uc2"),
        demo_lang: Annotated[str | None, Cookie()] = None,
    ):
        lang = _lang(demo_lang)
        raw = await file.read()
        try:
            dest = save_upload(file.filename or "upload.pdf", raw)
        except ValueError:
            return RedirectResponse(url=f"{_safe_next(next)}?upload_error=1", status_code=303)
        # Return to next with the new filename as query hint
        sep = "&" if "?" in next else "?"
        target = f"{_safe_next(next)}{sep}uploaded={dest.name}"
        _ = lang
        return RedirectResponse(url=target, status_code=303)

    @app.api_route("/docs/{name}/view", methods=["GET", "HEAD"])
    def open_pdf(
        request: Request,
        name: str,
        demo_lang: Annotated[str | None, Cookie()] = None,
    ):
        """HTML viewer for a local demo PDF (text preview + optional native PDF pane).

        The path must end with ``/view`` (not ``.pdf``). Chrome treats any URL whose
        path ends in ``.pdf`` as a native PDF document even when the body is HTML,
        which produces a blank pane.
        """
        safe = Path(name).name
        if safe != name or ".." in name or not safe.lower().endswith(".pdf"):
            return Response("Not found.", status_code=404, media_type="text/plain")
        path = resolve_pdf(safe)
        if path is None or not path.is_file():
            return Response("Not found.", status_code=404, media_type="text/plain")

        if request.method == "HEAD":
            return Response(status_code=200, media_type="text/html; charset=utf-8")

        lang = _lang(demo_lang)
        title = label_for_pdf(safe, lang)
        text = pdf_to_text(str(path))
        preview = (text or "").strip()
        if len(preview) > 12000:
            preview = preview[:12000] + "\n…"
        if not preview:
            preview = t("pdf_no_text", lang)

        page_paths = ensure_pdf_page_previews(path)
        page_urls = [
            f"/docs/{safe}/page/{i}"
            for i, _ in enumerate(page_paths, start=1)
        ]

        return templates.TemplateResponse(
            request,
            "pdf_viewer.html",
            {
                "lang": lang,
                "pdf_name": safe,
                "pdf_title": title,
                "pdf_preview": preview,
                "pdf_file_url": f"/docs/{safe}/file",
                "pdf_page_urls": page_urls,
                "path": request.url.path,
                "active": "",
            },
        )

    # Old ``/docs/pdf/<name>`` links end in ``.pdf`` → blank Chrome PDF pane. Redirect.
    @app.api_route("/docs/pdf/{name}", methods=["GET", "HEAD"])
    def open_pdf_legacy(name: str):
        safe = Path(name).name
        return RedirectResponse(url=f"/docs/{safe}/view", status_code=302)

    @app.api_route("/docs/view/{name}", methods=["GET", "HEAD"])
    def open_pdf_view_legacy(name: str):
        safe = Path(name).name
        return RedirectResponse(url=f"/docs/{safe}/view", status_code=302)

    @app.api_route("/docs/{name}/file", methods=["GET", "HEAD"])
    def download_pdf_file(
        request: Request,
        name: str,
        download: Annotated[int, Query()] = 0,
    ):
        """Raw PDF bytes for in-browser viewing / download."""
        safe = Path(name).name
        if safe != name or ".." in name or not safe.lower().endswith(".pdf"):
            return Response("Not found.", status_code=404, media_type="text/plain")
        path = resolve_pdf(safe)
        if path is None or not path.is_file():
            return Response("Not found.", status_code=404, media_type="text/plain")
        disposition = "attachment" if download else "inline"
        # Do not pass filename= to FileResponse (that forces attachment).
        headers = {
            "Content-Disposition": f'{disposition}; filename="{safe}"',
            "Content-Length": str(path.stat().st_size),
        }
        if request.method == "HEAD":
            return Response(
                status_code=200,
                media_type="application/pdf",
                headers=headers,
            )
        return FileResponse(
            path,
            media_type="application/pdf",
            headers=headers,
        )

    @app.api_route("/docs/{name}/page/{page}", methods=["GET", "HEAD"])
    def pdf_page_image(request: Request, name: str, page: int):
        """PNG raster of one PDF page (1-based) for the HTML viewer."""
        safe = Path(name).name
        if safe != name or ".." in name or not safe.lower().endswith(".pdf"):
            return Response("Not found.", status_code=404, media_type="text/plain")
        if page < 1 or page > 50:
            return Response("Not found.", status_code=404, media_type="text/plain")
        pdf_path = resolve_pdf(safe)
        if pdf_path is None or not pdf_path.is_file():
            return Response("Not found.", status_code=404, media_type="text/plain")
        pages = ensure_pdf_page_previews(pdf_path)
        if page > len(pages):
            return Response("Not found.", status_code=404, media_type="text/plain")
        img = pages[page - 1]
        headers = {"Content-Length": str(img.stat().st_size), "Cache-Control": "private, max-age=3600"}
        if request.method == "HEAD":
            return Response(status_code=200, media_type="image/png", headers=headers)
        return FileResponse(img, media_type="image/png", headers=headers)

    # Alias kept for any bookmarked ``…/docs/pdf/<name>/file`` URLs.
    @app.api_route("/docs/pdf/{name}/file", methods=["GET", "HEAD"])
    def download_pdf_file_legacy(
        request: Request,
        name: str,
        download: Annotated[int, Query()] = 0,
    ):
        return download_pdf_file(request, name, download)

    @app.get("/analyze/uc2")
    @app.get("/analyze/uc3")
    def analyze_get_redirect(request: Request):
        """Browsers may land on /analyze/* after POST; send them to the tab page."""
        path = request.url.path
        dest = "/uc3" if path.endswith("/uc3") else "/uc2"
        q = request.url.query
        url = f"{dest}?{q}" if q else dest
        return RedirectResponse(url=url, status_code=303)

    @app.post("/analyze/uc2", response_class=HTMLResponse)
    async def analyze_uc2(
        request: Request,
        spec_pdf: str = Form(...),
        daily_dock_rate: int = Form(860_000),
        dock_days: int = Form(5),
        hire_rate: int = Form(4_000_000),
        legacy_lead_days: int = Form(21),
        ai_lead_minutes: int = Form(15),
        docking_context: str = Form("casualty_immediate"),
        include_statutory: str | None = Form(None),
        spec_file: UploadFile | None = File(None),
        demo_lang: Annotated[str | None, Cookie()] = None,
    ):
        lang = _lang(demo_lang)
        if spec_file and spec_file.filename:
            try:
                spec_pdf = save_upload(spec_file.filename, await spec_file.read()).name
            except ValueError:
                pass
        params = Uc2Params(
            daily_dock_rate=daily_dock_rate,
            dock_days=dock_days,
            hire_rate=hire_rate,
            legacy_lead_days=legacy_lead_days,
            ai_lead_minutes=ai_lead_minutes,
            docking_context=docking_context,
            include_statutory=_truthy(include_statutory),
            spec_pdf=spec_pdf,
            analyze=True,
        )
        return _page(request, "uc2.html", "uc2", lang, uc2=run_uc2(lang, params))

    @app.post("/analyze/uc3", response_class=HTMLResponse)
    async def analyze_uc3(
        request: Request,
        doc_pdf: str = Form(...),
        case_id: str | None = Form(None),
        heading_a_deg: float | None = Form(None),
        heading_b_deg: float | None = Form(None),
        true_bearing_a_to_b_deg: float | None = Form(None),
        doc_file: UploadFile | None = File(None),
        demo_lang: Annotated[str | None, Cookie()] = None,
    ):
        lang = _lang(demo_lang)
        if doc_file and doc_file.filename:
            try:
                doc_pdf = save_upload(doc_file.filename, await doc_file.read()).name
            except ValueError:
                pass
        params = Uc3Params(
            case_id=case_id,
            heading_a_deg=heading_a_deg,
            heading_b_deg=heading_b_deg,
            true_bearing_a_to_b_deg=true_bearing_a_to_b_deg,
            doc_pdf=doc_pdf,
            analyze=True,
        )
        return _page(request, "uc3.html", "uc3", lang, uc3=run_uc3(lang, params))

    @app.get("/partials/uc2", response_class=HTMLResponse)
    def uc2_partial(
        request: Request,
        daily_dock_rate: int = 860_000,
        dock_days: int = 5,
        hire_rate: int = 4_000_000,
        legacy_lead_days: int = 21,
        ai_lead_minutes: int = 15,
        docking_context: str = "casualty_immediate",
        include_statutory: str | None = None,
        spec_pdf: str | None = None,
        analyze: str | None = None,
        demo_lang: Annotated[str | None, Cookie()] = None,
    ):
        lang = _lang(demo_lang)
        params = Uc2Params(
            daily_dock_rate=daily_dock_rate,
            dock_days=dock_days,
            hire_rate=hire_rate,
            legacy_lead_days=legacy_lead_days,
            ai_lead_minutes=ai_lead_minutes,
            docking_context=docking_context,
            include_statutory=_truthy(include_statutory),
            spec_pdf=spec_pdf,
            analyze=_truthy(analyze),
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
        heading_a_deg: float | None = None,
        heading_b_deg: float | None = None,
        true_bearing_a_to_b_deg: float | None = None,
        doc_pdf: str | None = None,
        analyze: str | None = None,
        demo_lang: Annotated[str | None, Cookie()] = None,
    ):
        lang = _lang(demo_lang)
        params = Uc3Params(
            case_id=case_id,
            heading_a_deg=heading_a_deg,
            heading_b_deg=heading_b_deg,
            true_bearing_a_to_b_deg=true_bearing_a_to_b_deg,
            doc_pdf=doc_pdf,
            analyze=_truthy(analyze),
        )
        return templates.TemplateResponse(
            request,
            "partials/uc3_results.html",
            {"lang": lang, "uc3": run_uc3(lang, params)},
        )

    @app.get("/export/apportionment.md")
    def export_apportion_md(
        daily_dock_rate: int = 860_000,
        dock_days: int = 5,
        hire_rate: int = 4_000_000,
        legacy_lead_days: int = 21,
        ai_lead_minutes: int = 15,
        docking_context: str = "casualty_immediate",
        include_statutory: str | None = "1",
        demo_lang: Annotated[str | None, Cookie()] = None,
    ):
        return _export_uc2(
            _lang(demo_lang),
            Uc2Params(
                daily_dock_rate,
                dock_days,
                hire_rate,
                legacy_lead_days,
                ai_lead_minutes,
                docking_context,
                _truthy(include_statutory),
            ),
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
        docking_context: str = "casualty_immediate",
        include_statutory: str | None = "1",
        demo_lang: Annotated[str | None, Cookie()] = None,
    ):
        return _export_uc2(
            _lang(demo_lang),
            Uc2Params(
                daily_dock_rate,
                dock_days,
                hire_rate,
                legacy_lead_days,
                ai_lead_minutes,
                docking_context,
                _truthy(include_statutory),
            ),
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


def _truthy(value: str | None) -> bool:
    if value is None:
        return False
    return value.strip().lower() in {"1", "true", "on", "yes"}


def _safe_next(next_url: str) -> str:
    """Allow only same-origin relative paths; never return POST-only /analyze/* URLs."""
    candidate = (next_url or "/").replace("\\", "").split("?", 1)[0]
    parsed = urlparse(candidate)
    if not candidate.startswith("/") or parsed.scheme or parsed.netloc:
        return "/uc2"
    # Form POST responses may leave the browser on /analyze/*; clear-cache
    # must not redirect back there (GET → 405 Method Not Allowed).
    if candidate.startswith("/analyze"):
        if candidate.startswith("/analyze/uc2"):
            return "/uc2"
        if candidate.startswith("/analyze/uc3"):
            return "/uc3"
        return "/uc2"
    if candidate in {"/", ""}:
        return "/uc2"
    return candidate


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
            "cache_cleared": request.query_params.get("cache_cleared") in {"1", "true", "yes"},
            "analyzed": request.query_params.get("analyzed") in {"1", "true", "yes"},
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
