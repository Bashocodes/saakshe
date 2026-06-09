"""GitHub connect mechanism routing — the in-container default must be cloneable.

The container ships no ssh deploy key, so 'ssh' can never clone there. A bare
``owner/repo`` (the form the connect gate's own placeholder suggests) and any
https URL must route to the public https mechanism; ssh only when explicitly
asked for; PAT when a token rides along.
"""
from __future__ import annotations

from fastapi.testclient import TestClient

from service.app import app
from common import project
from manas.sources import normalize_repo_ref

client = TestClient(app)


def _connect(monkeypatch, tmp_path, body):
    monkeypatch.setenv("SAAKSHE_PROJECT_DIR", str(tmp_path))
    project.STORE.reset(persist=False)
    r = client.post("/api/connect/source", json=body)
    assert r.status_code == 200
    return r.json()["connection"]


def test_bare_owner_repo_defaults_to_public(monkeypatch, tmp_path):
    conn = _connect(monkeypatch, tmp_path, {"kind": "github", "ref": "octo/repo"})
    assert conn["meta"]["mechanism"] == "public"
    # And the public mechanism yields an in-container-cloneable https URL.
    assert normalize_repo_ref("octo/repo", mechanism="public") == "https://github.com/octo/repo.git"


def test_token_defaults_to_pat(monkeypatch, tmp_path):
    conn = _connect(monkeypatch, tmp_path,
                    {"kind": "github", "ref": "octo/repo", "token": "ghp_x"})
    assert conn["meta"]["mechanism"] == "pat"
    url = normalize_repo_ref("octo/repo", mechanism="pat", token="ghp_x")
    assert url.startswith("https://x-access-token:ghp_x@github.com/")


def test_explicit_ssh_is_honored(monkeypatch, tmp_path):
    conn = _connect(monkeypatch, tmp_path,
                    {"kind": "github", "ref": "git@github.com:octo/repo.git", "mechanism": "ssh"})
    assert conn["meta"]["mechanism"] == "ssh"
