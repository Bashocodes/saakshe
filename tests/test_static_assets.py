"""web static assets — the page server must serve the cockpit's css/js (and og
image) with real media types, not append .html and 404 them (prod rev 00015 bug:
chat-panel.css/js came back as branded-404 HTML, so the chat panel shipped dead)."""
from fastapi.testclient import TestClient

from service.app import app

client = TestClient(app)


def test_chat_panel_css_served_as_css():
    r = client.get("/chat-panel.css")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/css")


def test_chat_panel_js_served_as_javascript():
    r = client.get("/chat-panel.js")
    assert r.status_code == 200
    assert "javascript" in r.headers["content-type"]


def test_missing_asset_is_404_not_branded_html():
    r = client.get("/nope.css")
    assert r.status_code == 404
    assert not r.headers["content-type"].startswith("text/css")


def test_traversal_still_blocked():
    r = client.get("/..%2fservice%2fapp.py")
    assert r.status_code == 404


def test_unknown_extension_still_falls_through_to_pages():
    # /pricing keeps working exactly as before (the .html append path).
    r = client.get("/pricing")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/html")
