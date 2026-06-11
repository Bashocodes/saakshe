"""Repo visibility probe — the bridge tells the founder BEFORE granting whether
manas can read a repo anonymously (any public/open-source repo), needs a
fine-grained token (private), or needs a local SSH run (git@ refs).

Two invariants the probe must keep:
  * a raw ref is NEVER handed to git — the probe builds its own https URL from a
    strictly parsed ref (no ext:: transports, no whitespace smuggling), and
  * no credential helper is consulted — the verdict is what a stranger sees,
    which is exactly the question the founder is asking.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

from fastapi.testclient import TestClient

from common import project
from manas import sources
from service.app import app

client = TestClient(app)


# ─── parsing guard: garbage never reaches git ────────────────────────────────
def test_probe_never_runs_git_on_unparseable_refs(monkeypatch):
    calls: list = []
    monkeypatch.setattr(sources.subprocess, "run",
                        lambda *a, **k: calls.append(a) or (_ for _ in ()).throw(AssertionError))
    for bad in ("", "   ", "owneronly", "owner/repo/extra", "ext::sh -c id",
                "http://github.com/x/y", "https://github.com/x/y z"):
        assert sources.probe_repo_visibility(bad)["visibility"] == "unknown"
    assert calls == []


def test_probe_ssh_ref_short_circuits_without_git(monkeypatch):
    monkeypatch.setattr(sources.subprocess, "run",
                        lambda *a, **k: (_ for _ in ()).throw(AssertionError("git ran")))
    assert sources.probe_repo_visibility("git@github.com:octo/repo.git")["visibility"] == "ssh"
    assert sources.probe_repo_visibility("ssh://git@github.com/octo/repo")["visibility"] == "ssh"


# ─── verdicts ────────────────────────────────────────────────────────────────
def _fake_run(rc: int):
    def run(cmd, **kw):
        if rc:
            raise subprocess.CalledProcessError(rc, cmd, stderr="fatal: auth")
        return subprocess.CompletedProcess(cmd, 0, stdout="abc\tHEAD\n", stderr="")
    return run


def test_probe_public_when_anonymous_ls_remote_succeeds(monkeypatch):
    monkeypatch.setattr(sources.subprocess, "run", _fake_run(0))
    assert sources.probe_repo_visibility("octo/repo")["visibility"] == "public"


def test_probe_private_when_anonymous_access_refused(monkeypatch):
    monkeypatch.setattr(sources.subprocess, "run", _fake_run(128))
    assert sources.probe_repo_visibility("octo/repo")["visibility"] == "private"


def test_probe_is_anonymous_and_https_only(monkeypatch):
    seen: dict = {}

    def run(cmd, **kw):
        seen["cmd"], seen["env"] = cmd, kw.get("env") or {}
        return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

    monkeypatch.setattr(sources.subprocess, "run", run)
    sources.probe_repo_visibility("github.com/octo/repo")
    cmd = seen["cmd"]
    assert "credential.helper=" in cmd            # no stored token colors the verdict
    assert "https://github.com/octo/repo.git" in cmd
    assert seen["env"].get("GIT_TERMINAL_PROMPT") == "0"   # never hangs on a prompt


def test_probe_takes_full_https_urls_as_pasted(monkeypatch):
    """Any open-source host works — a full https URL is probed exactly as the
    reader would clone it (gitlab, bitbucket, self-hosted)."""
    seen: dict = {}

    def run(cmd, **kw):
        seen["cmd"] = cmd
        return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

    monkeypatch.setattr(sources.subprocess, "run", run)
    v = sources.probe_repo_visibility("https://gitlab.com/octo/repo")
    assert v["visibility"] == "public"
    assert "https://gitlab.com/octo/repo" in seen["cmd"]


# ─── the PAT must survive a pasted https URL (the founder's natural input) ───
def test_pat_token_is_injected_into_full_https_refs():
    url = sources.normalize_repo_ref("https://github.com/octo/repo.git",
                                     mechanism="pat", token="ghp_x")
    assert url == "https://x-access-token:ghp_x@github.com/octo/repo.git"
    # and ssh refs stay untouched — the key, not the token, is the credential
    assert sources.normalize_repo_ref("git@github.com:octo/repo.git",
                                      mechanism="pat", token="ghp_x").startswith("git@")


# ─── the route ───────────────────────────────────────────────────────────────
def test_probe_route_returns_verdict_and_hint(monkeypatch, tmp_path):
    monkeypatch.setenv("SAAKSHE_PROJECT_DIR", str(tmp_path))
    project.STORE.reset(persist=False)
    monkeypatch.setattr(sources.subprocess, "run", _fake_run(0))
    r = client.post("/api/connect/probe", json={"ref": "octo/repo"})
    assert r.status_code == 200
    body = r.json()
    assert body["visibility"] == "public"
    assert body["hint"]            # the gate shows this line verbatim


def test_probe_route_is_sealed_on_the_public_demo(monkeypatch, tmp_path):
    monkeypatch.setenv("SAAKSHE_PROJECT_DIR", str(tmp_path))
    monkeypatch.setenv("SAAKSHE_PUBLIC_DEMO", "1")
    project.STORE.reset(persist=False)
    try:
        r = client.post("/api/connect/probe", json={"ref": "octo/repo"})
        assert r.status_code == 403
    finally:
        monkeypatch.delenv("SAAKSHE_PUBLIC_DEMO")


# ─── the gate speaks the truth about access ──────────────────────────────────
def test_connect_gate_offers_the_proper_paths():
    html = (Path(__file__).parents[1] / "web" / "cockpit.html").read_text()
    assert "uses your git SSH" not in html        # the stale local-only claim
    assert "/api/connect/probe" in html           # the gate probes before granting
    assert 'id="cgToken"' in html                 # private repos take a token
