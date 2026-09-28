"""Tests for Progressive Web App (PWA) manifest and Service Worker endpoints."""

from __future__ import annotations

import json
from starlette.testclient import TestClient

from marine_claims_ai.demo.app import create_app


def test_manifest_webmanifest_endpoint():
    app = create_app()
    client = TestClient(app)
    response = client.get("/manifest.webmanifest")
    assert response.status_code == 200
    assert "application/manifest+json" in response.headers.get("content-type", "")

    manifest = response.json()
    assert manifest["id"] == "/"
    assert manifest["display"] == "standalone"
    assert manifest["start_url"] == "/"
    assert len(manifest["icons"]) >= 1
    assert any(icon["purpose"] == "maskable" for icon in manifest["icons"])


def test_service_worker_endpoint():
    app = create_app()
    client = TestClient(app)
    response = client.get("/sw.js")
    assert response.status_code == 200
    assert "application/javascript" in response.headers.get("content-type", "")
    assert response.headers.get("service-worker-allowed") == "/"

    js_text = response.text
    assert "marine-claims-v1" in js_text
    assert "install" in js_text
    assert "activate" in js_text
    assert "fetch" in js_text


def test_favicon_and_icon_endpoints():
    app = create_app()
    client = TestClient(app)
    
    # Favicon
    resp_fav = client.get("/favicon.ico")
    assert resp_fav.status_code == 200
    assert "image/svg+xml" in resp_fav.headers.get("content-type", "")
    assert b"<svg" in resp_fav.content

    # SVG Icon
    resp_icon = client.get("/static/icons/icon.svg")
    assert resp_icon.status_code == 200
    assert "image/svg+xml" in resp_icon.headers.get("content-type", "")


def test_pwa_tags_in_html_shell():
    app = create_app()
    client = TestClient(app)
    response = client.get("/")
    assert response.status_code == 200

    html = response.text
    assert '<link rel="manifest" href="/manifest.webmanifest">' in html
    assert '<meta name="theme-color" content="#0f172a">' in html
    assert "navigator.serviceWorker.register('/sw.js'" in html
    assert 'id="pwa-install-btn"' in html
    assert 'id="pwa-offline-indicator"' in html
