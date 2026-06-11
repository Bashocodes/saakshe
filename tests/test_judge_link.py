"""The judge magic link — /judge/<token> signs the judge in without Supabase.

Pins the capability-link contract: a matching token sets the HttpOnly cookie and
every session resolves to the JUDGE identity (shared seeded store, mutations
sealed, free); a wrong token — or the feature left unconfigured — is a branded
404 and the cookie is inert. The cockpit boots gate-free because public-config
reports require_signin=false to a judge-link request.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from service.app import app

TOKEN = "k9f2m7d4q1z8w3x6v5b0"  # ≥16 chars — a real-shaped secret


def _client() -> TestClient:
    # https base URL so the Secure cookie rides in the test jar
    return TestClient(app, base_url="https://testserver")


def _gate_on(monkeypatch, token: str = TOKEN):
    monkeypatch.setenv("SAAKSHE_SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setenv("SAAKSHE_REQUIRE_SIGNIN", "1")
    monkeypatch.setenv("SAAKSHE_PUBLIC_DEMO", "1")
    monkeypatch.setenv("SAAKSHE_JUDGE_TOKEN", token)


def test_unconfigured_feature_is_a_branded_404(monkeypatch):
    monkeypatch.delenv("SAAKSHE_JUDGE_TOKEN", raising=False)
    assert _client().get(f"/judge/{TOKEN}", follow_redirects=False).status_code == 404


def test_short_token_env_fails_closed(monkeypatch):
    _gate_on(monkeypatch, token="short")  # <16 chars: feature stays OFF
    c = _client()
    assert c.get("/judge/short", follow_redirects=False).status_code == 404


def test_wrong_token_404_and_no_cookie(monkeypatch):
    _gate_on(monkeypatch)
    r = _client().get("/judge/not-the-token", follow_redirects=False)
    assert r.status_code == 404
    assert "sk_judge" not in r.cookies


def test_link_sets_cookie_and_lands_on_cockpit(monkeypatch):
    _gate_on(monkeypatch)
    r = _client().get(f"/judge/{TOKEN}", follow_redirects=False)
    assert r.status_code == 303
    assert r.headers["location"] == "/cockpit"
    set_cookie = r.headers["set-cookie"]
    assert "sk_judge" in set_cookie and "HttpOnly" in set_cookie and "Secure" in set_cookie


def test_cookie_unlocks_the_gated_api_as_the_judge(monkeypatch):
    _gate_on(monkeypatch)
    c = _client()
    assert c.get("/api/gates").status_code == 401          # anonymous stays gated
    c.get(f"/judge/{TOKEN}", follow_redirects=False)       # jar keeps the cookie
    assert c.get("/api/gates").status_code == 200
    s = c.get("/api/connect/status")
    assert s.status_code == 200                            # the shared seeded demo
    # ...and the judge stays sealed: mutations on the shared company are blocked
    r = c.post("/api/connect/reset")
    assert r.status_code == 403


def test_public_config_reports_open_demo_to_a_judge_link(monkeypatch):
    _gate_on(monkeypatch)
    c = _client()
    assert c.get("/api/public-config").json()["require_signin"] is True
    c.get(f"/judge/{TOKEN}", follow_redirects=False)
    cfg = c.get("/api/public-config").json()
    assert cfg["require_signin"] is False                  # the cockpit boots gate-free
    assert cfg["auth_enabled"] is False
    assert cfg["judge_link"] is True


def test_garbage_cookie_is_inert(monkeypatch):
    _gate_on(monkeypatch)
    c = _client()
    c.cookies.set("sk_judge", "forged-value")
    assert c.get("/api/gates").status_code == 401
