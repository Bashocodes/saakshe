"""The sealed public demo — one shared store, so visitors must not mutate it,
and the model-burning routes carry a per-IP budget."""
from __future__ import annotations

import base64

from fastapi.testclient import TestClient

from service.app import app, _BUCKETS
from common import project

client = TestClient(app)


def _sealed(monkeypatch, tmp_path):
    monkeypatch.setenv("SAAKSHE_PROJECT_DIR", str(tmp_path))
    monkeypatch.setenv("SAAKSHE_PUBLIC_DEMO", "1")
    project.STORE.reset(persist=False)


def test_sealed_demo_403s_every_mutating_connect_route(monkeypatch, tmp_path):
    _sealed(monkeypatch, tmp_path)
    assert client.post("/api/connect/source",
                       json={"kind": "github", "ref": "octo/repo"}).status_code == 403
    assert client.post("/api/connect/ingest").status_code == 403
    assert client.post("/api/connect/reset").status_code == 403
    payload = {"kind": "logo", "filename": "l.png", "content_type": "image/png",
               "data_b64": base64.b64encode(b"PNG").decode()}
    assert client.post("/api/vault/add", json=payload).status_code == 403


def test_owner_bypasses_the_seal_into_a_sandbox(monkeypatch, tmp_path):
    """A signed-in OWNER gets the seal lifted AND an isolated per-user store —
    the founder runs the real connect flow while the shared seeded demo stays
    untouched. A signed-in non-owner (a judge) stays sealed."""
    from common import auth

    _sealed(monkeypatch, tmp_path)
    monkeypatch.setenv("SAAKSHE_SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setenv("SAAKSHE_REQUIRE_SIGNIN", "1")
    monkeypatch.setenv("OWNER_EMAILS", "founder@example.com")
    monkeypatch.setattr(auth, "verify_token",
                        lambda tok: {"sub": "owner-sandbox-1", "email": "founder@example.com"})
    r = client.post("/api/connect/source",
                    json={"kind": "github", "ref": "octo/repo"},
                    headers={"Authorization": "Bearer owner-token"})
    assert r.status_code == 200
    assert not project.STORE.is_connected(), "the founder's connect must land in a sandbox, not the shared demo"
    monkeypatch.setattr(auth, "verify_token",
                        lambda tok: {"sub": "judge-1", "email": "judge@saakshe.com"})
    assert client.post("/api/connect/source",
                       json={"kind": "github", "ref": "octo/repo"},
                       headers={"Authorization": "Bearer judge-token"}).status_code == 403


def test_sealed_demo_still_answers_the_witness(monkeypatch, tmp_path):
    _sealed(monkeypatch, tmp_path)
    _BUCKETS.clear()
    r = client.post("/api/saakshe/ask", json={"text": "anyone waiting on me?"})
    assert r.status_code == 200
    assert "text" in r.json()


def test_unsealed_routes_stay_open(monkeypatch, tmp_path):
    monkeypatch.setenv("SAAKSHE_PROJECT_DIR", str(tmp_path))
    monkeypatch.delenv("SAAKSHE_PUBLIC_DEMO", raising=False)
    project.STORE.reset(persist=False)
    r = client.post("/api/connect/source", json={"kind": "github", "ref": "octo/repo"})
    assert r.status_code == 200


def test_ask_rate_limit_429s_after_burst(monkeypatch, tmp_path):
    monkeypatch.setenv("SAAKSHE_PROJECT_DIR", str(tmp_path))
    project.STORE.reset(persist=False)
    _BUCKETS.clear()
    codes = [client.post("/api/saakshe/ask", json={"text": "what did today cost?"}).status_code
             for _ in range(14)]
    assert codes[0] == 200
    assert 429 in codes, "the 12/min bucket must trip inside a 14-call burst"
    _BUCKETS.clear()


def test_public_config_carries_the_lock_flag(monkeypatch, tmp_path):
    _sealed(monkeypatch, tmp_path)
    assert client.get("/api/public-config").json()["public_demo"] is True


def test_any_signed_in_founder_bypasses_the_seal_into_a_sandbox(monkeypatch, tmp_path):
    """Everyone-access (2026-06-11): a signed-in NON-owner, non-judge account gets
    the seal lifted AND its own sandbox — the shared seeded demo stays pristine.
    Only anonymous visitors and JUDGE_EMAILS stay sealed."""
    from common import auth

    _sealed(monkeypatch, tmp_path)
    monkeypatch.setenv("SAAKSHE_SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setenv("SAAKSHE_REQUIRE_SIGNIN", "1")
    monkeypatch.setenv("OWNER_EMAILS", "founder@example.com")
    monkeypatch.setattr(auth, "verify_token",
                        lambda tok: {"sub": "visitor-7", "email": "maker@example.com"})
    r = client.post("/api/connect/source",
                    json={"kind": "github", "ref": "octo/repo"},
                    headers={"Authorization": "Bearer visitor-token"})
    assert r.status_code == 200
    assert not project.STORE.is_connected(), \
        "a visitor's connect must land in their sandbox, never the shared demo"
