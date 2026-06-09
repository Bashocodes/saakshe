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
