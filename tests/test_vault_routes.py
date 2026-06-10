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


# ─── the byte-serving route (the gate-2 card's <img> source) ──────────────────
def test_vault_asset_serves_bytes_with_sniffed_type():
    from common import vault as blob
    png = b"\x89PNG\r\n\x1a\n" + b"fake-render"
    uri = blob.put("render-test.png", png, "image/png")
    r = client.get("/api/vault/asset", params={"uri": uri})
    assert r.status_code == 200
    assert r.content == png
    assert r.headers["content-type"].startswith("image/png")


def test_vault_asset_rejects_non_vault_uri():
    """Only vault://<hex> URIs are servable — never a path, never a live storage key."""
    for bad in ("../../etc/passwd", "founder/secret.png", "vault://../x", "vault://UPPER"):
        assert client.get("/api/vault/asset", params={"uri": bad}).status_code == 400


def test_vault_asset_404_when_missing():
    assert client.get("/api/vault/asset",
                      params={"uri": "vault://deadbeefdeadbeef"}).status_code == 404
