"""The marketing/legal pages + the branded 404. Served by the single-segment
catch-all; an unknown page returns the real 404.html (status 404), so a typo'd
URL lands on a saakshe page instead of bare JSON."""
from __future__ import annotations

from fastapi.testclient import TestClient

from service.app import app

client = TestClient(app)


def test_site_pages_are_served():
    for page in ("pricing", "faq", "terms", "privacy"):
        r = client.get(f"/{page}")
        assert r.status_code == 200, page
        assert "text/html" in r.headers["content-type"]
        assert page in r.text.lower()


def test_unknown_page_serves_branded_404():
    r = client.get("/this-page-does-not-exist")
    assert r.status_code == 404
    assert "text/html" in r.headers["content-type"]
    assert "page not found" in r.text.lower()


def test_unknown_api_route_stays_json():
    r = client.get("/api/this/does/not/exist")
    assert r.status_code == 404
    assert "text/html" not in r.headers.get("content-type", "")
