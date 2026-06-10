"""The gated demo — SAAKSHE_REQUIRE_SIGNIN=1 puts the whole API surface behind
Supabase sign-in (email credentials shipped in the Devpost testing instructions)
while the seeded file-store demo + public-demo sealing stay byte-identical for a
signed-in judge. The sign-in surfaces themselves stay open: the HTML pages,
/api/public-config (the cockpit boots supabase-js from it) and the health probe.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from common import auth
from service.app import app

client = TestClient(app)


def _gate_on(monkeypatch):
    monkeypatch.setenv("SAAKSHE_SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setenv("SAAKSHE_REQUIRE_SIGNIN", "1")


def test_api_routes_401_without_signin(monkeypatch):
    _gate_on(monkeypatch)
    assert client.get("/api/gates").status_code == 401
    assert client.post("/api/saakshe/ask", json={"text": "hi"}).status_code == 401
    assert client.get("/api/vault/list").status_code == 401
    assert client.get("/api/stream").status_code == 401


def test_signin_surfaces_stay_open(monkeypatch):
    _gate_on(monkeypatch)
    assert client.get("/").status_code == 200                      # the landing
    assert client.get("/api/saakshe/health").status_code == 200    # Cloud Run probe
    cfg = client.get("/api/public-config")
    assert cfg.status_code == 200
    assert cfg.json()["require_signin"] is True
    assert cfg.json()["auth_enabled"] is True                      # boots supabase-js


def test_valid_token_unlocks_the_seeded_demo(monkeypatch):
    _gate_on(monkeypatch)
    monkeypatch.setattr(auth, "verify_token",
                        lambda tok: {"sub": "judge-1", "email": "judge@saakshe.com"})
    hdr = {"Authorization": "Bearer judge-token"}
    assert client.get("/api/gates", headers=hdr).status_code == 200
    # the judge lands on the SHARED seeded demo store — never an empty tenant
    s = client.get("/api/connect/status", headers=hdr)
    assert s.status_code == 200


def test_voice_ws_rejected_without_token(monkeypatch):
    _gate_on(monkeypatch)
    with pytest.raises(WebSocketDisconnect):
        with client.websocket_connect("/ws/voice"):
            pass


def test_flag_off_is_todays_open_demo(monkeypatch):
    monkeypatch.delenv("SAAKSHE_REQUIRE_SIGNIN", raising=False)
    monkeypatch.delenv("SAAKSHE_SUPABASE_URL", raising=False)
    assert client.get("/api/gates").status_code == 200
    assert client.get("/api/public-config").json()["require_signin"] is False
