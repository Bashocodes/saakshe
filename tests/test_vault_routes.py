"""The vault endpoints — list metadata + manual add. Empty-state safe."""
from __future__ import annotations

import base64
from fastapi.testclient import TestClient

from service.app import app
from common import project

client = TestClient(app)


def test_vault_list_empty_by_default(monkeypatch, tmp_path):
    monkeypatch.setenv("SAAKSHE_PROJECT_DIR", str(tmp_path))
    project.STORE.reset(persist=False)
    r = client.get("/api/vault/list")
    assert r.status_code == 200
    assert r.json()["assets"] == []


def test_vault_add_then_list(monkeypatch, tmp_path):
    monkeypatch.setenv("SAAKSHE_PROJECT_DIR", str(tmp_path))
    project.STORE.reset(persist=False)
    payload = {"kind": "logo", "filename": "l.png", "content_type": "image/png",
               "data_b64": base64.b64encode(b"PNG").decode()}
    r = client.post("/api/vault/add", json=payload)
    assert r.status_code == 200 and r.json()["asset"]["kind"] == "logo"
    assert len(client.get("/api/vault/list").json()["assets"]) == 1
