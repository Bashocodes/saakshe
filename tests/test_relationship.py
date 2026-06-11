"""The self-vs-public marker — connecting someone else's public repo must not
make saakshe speak as if the founder owns it.

org.relationship: "own" (default — today's exact behavior) | "public" (a product
the founder is exploring). Set from the connect step, carried on the org dict
through status/grasped, respected by the fallback copy and the interview
phrasing (manas/tests cover the phrasing side).
"""
from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from common import project
from service.app import app

client = TestClient(app)
ROOT = Path(__file__).resolve().parents[1]


def _fresh(monkeypatch, tmp_path):
    monkeypatch.setenv("SAAKSHE_PROJECT_DIR", str(tmp_path))
    project.STORE.reset(persist=False)


def test_connect_carries_relationship(monkeypatch, tmp_path):
    _fresh(monkeypatch, tmp_path)
    r = client.post("/api/connect/source",
                    json={"kind": "github", "ref": "excalidraw/excalidraw",
                          "relationship": "public"})
    assert r.status_code == 200
    st = client.get("/api/connect/status").json()
    assert st["org"]["relationship"] == "public"


def test_relationship_defaults_to_own(monkeypatch, tmp_path):
    _fresh(monkeypatch, tmp_path)
    r = client.post("/api/connect/source", json={"kind": "github", "ref": "octo/repo"})
    assert r.status_code == 200
    st = client.get("/api/connect/status").json()
    assert st["org"].get("relationship", "own") == "own"


def test_bad_relationship_is_rejected(monkeypatch, tmp_path):
    _fresh(monkeypatch, tmp_path)
    r = client.post("/api/connect/source",
                    json={"kind": "github", "ref": "octo/repo", "relationship": "stolen"})
    assert r.status_code == 400


def test_ingest_org_hint_does_not_clobber_relationship(monkeypatch, tmp_path):
    """runner.py's set_org(**org_hint) carries name/kind/one_liner only — the
    marker set at connect time must survive a grounding pass."""
    _fresh(monkeypatch, tmp_path)
    store = project.STORE
    store.set_org(relationship="public")
    store.set_org(name="Excalidraw", kind="virtual whiteboard", one_liner="draws")
    assert store.org["relationship"] == "public"
    assert store.org["name"] == "Excalidraw"


def test_public_fallback_copy_is_not_possessive(monkeypatch, tmp_path):
    _fresh(monkeypatch, tmp_path)
    store = project.STORE
    store.set_org(relationship="public")
    org = store.org_for_flywheel()
    assert org["name"] == "the project"        # never "your company"
    assert org["kind"] == "a public product"   # never "the connected company"


def test_own_fallback_copy_is_unchanged(monkeypatch, tmp_path):
    _fresh(monkeypatch, tmp_path)
    org = project.STORE.org_for_flywheel()
    assert org["name"] == "your company"
    assert org["kind"] == "the connected company"


def test_cockpit_ships_the_relationship_toggle():
    html = (ROOT / "web" / "cockpit.html").read_text()
    assert 'id="cgRelMine"' in html and 'id="cgRelPublic"' in html
    assert "sources[0].relationship" in html  # doConnect sends the marker with the grant
