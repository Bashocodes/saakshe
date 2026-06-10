"""saakshe.tests.test_signin_hardening — the 2026-06-10 audit fixes, pinned.

Four behaviors that must never regress:
1. The gated-demo switch fails CLOSED: SAAKSHE_REQUIRE_SIGNIN=1 with Supabase auth
   misconfigured 401s every session-bound route instead of serving wide open.
2. A GitHub PAT rides IN over setu but never rides back OUT of any response.
3. A balance lookup outage reads as None ("unknown"), never as 0 ("broke").
4. /api/connect/answer is sealed on the public demo like its mutating siblings.
"""

from __future__ import annotations

import httpx
import pytest
from fastapi.testclient import TestClient

from common import credits, project


@pytest.fixture
def demo_client(monkeypatch, tmp_path):
    """The app in plain file-store demo mode (no Supabase, no auth)."""
    import service.app as appmod

    monkeypatch.delenv("SAAKSHE_STORE", raising=False)
    monkeypatch.delenv("SAAKSHE_SUPABASE_URL", raising=False)
    monkeypatch.delenv("SAAKSHE_REQUIRE_SIGNIN", raising=False)
    monkeypatch.delenv("SAAKSHE_PUBLIC_DEMO", raising=False)
    store = project.ProjectStore(user="t_signin_hardening")
    store.reset()
    monkeypatch.setattr(project, "STORE", store)
    return TestClient(appmod.app)


def test_require_signin_fails_closed_without_supabase(monkeypatch):
    """Flag set + auth misconfigured (no SAAKSHE_SUPABASE_URL) → 401, not open."""
    import service.app as appmod

    monkeypatch.delenv("SAAKSHE_STORE", raising=False)
    monkeypatch.delenv("SAAKSHE_SUPABASE_URL", raising=False)
    monkeypatch.setenv("SAAKSHE_REQUIRE_SIGNIN", "1")
    c = TestClient(appmod.app)

    r = c.get("/api/connect/status")
    assert r.status_code == 401
    assert r.json()["detail"] == "auth_required"

    # the frontend's misconfig gate keys off this exact combination
    cfg = c.get("/api/public-config").json()
    assert cfg["require_signin"] is True
    assert cfg["auth_enabled"] is False


def test_github_pat_never_echoed(demo_client):
    """The PAT is stored for the clone but redacted from every response body."""
    pat = "ghp_SECRET_e2e_token_123"
    r = demo_client.post("/api/connect/source",
                         json={"kind": "github", "ref": "https://github.com/x/app",
                               "token": pat})
    assert r.status_code == 200
    assert pat not in r.text
    assert "•••" in r.text

    r2 = demo_client.get("/api/connect/status")
    assert r2.status_code == 200
    assert pat not in r2.text


def test_balance_outage_reads_unknown_not_broke(monkeypatch):
    """A transport failure must surface as None, never as balance 0."""
    monkeypatch.setenv("SAAKSHE_SUPABASE_URL", "https://ref.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "k")

    def boom(*a, **k):
        raise httpx.ConnectError("supabase is down")
    monkeypatch.setattr(httpx, "get", boom)
    assert credits.balance("u_anyone") is None


def test_connect_answer_sealed_on_public_demo(demo_client, monkeypatch):
    monkeypatch.setenv("SAAKSHE_PUBLIC_DEMO", "1")
    r = demo_client.post("/api/connect/answer", json={"qid": "q1", "answer": "x"})
    assert r.status_code == 403
    assert "sealed" in r.json()["detail"]


def test_grasped_readout_serves_the_extraction(demo_client):
    """The CONNECT pill's landing: org + facts + rules + questions, PAT-redacted."""
    demo_client.post("/api/connect/source",
                     json={"kind": "github", "ref": "https://github.com/x/app",
                           "token": "ghp_SECRET_grasped"})
    r = demo_client.get("/api/connect/grasped")
    assert r.status_code == 200
    d = r.json()
    assert d["connected"] is True
    assert set(d) >= {"grounded", "version", "org", "facts",
                      "voice_rules", "brand_rules", "questions"}
    assert "ghp_SECRET_grasped" not in r.text
