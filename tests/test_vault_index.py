# tests/test_vault_index.py
"""The vault metadata INDEX in ProjectStore — versioned, dedup'd, queryable."""
from __future__ import annotations

from common import project


def _store(tmp_path, monkeypatch):
    monkeypatch.setenv("SAAKSHE_PROJECT_DIR", str(tmp_path))
    monkeypatch.delenv("SAAKSHE_STORE", raising=False)
    s = project.ProjectStore(user="t")
    s.reset(persist=False)
    return s


def test_add_asset_records_and_bumps_version(tmp_path, monkeypatch):
    s = _store(tmp_path, monkeypatch)
    v0 = s.version
    rec = s.add_asset(kind="logo", filename="logo.png", content_type="image/png",
                      uri="vault://abc", sha256="abc", tags=["primary"], provenance="repo")
    assert rec["kind"] == "logo" and rec["uri"] == "vault://abc"
    assert s.version != v0                      # versioned like a pack commit
    assert s.asset_count() == 1


def test_add_asset_dedups_by_sha(tmp_path, monkeypatch):
    s = _store(tmp_path, monkeypatch)
    s.add_asset(kind="logo", filename="a.png", content_type="image/png", uri="vault://x", sha256="x")
    s.add_asset(kind="logo", filename="a-copy.png", content_type="image/png", uri="vault://x", sha256="x")
    assert s.asset_count() == 1                  # same bytes -> one record


def test_assets_for_filters_by_kind_and_tag(tmp_path, monkeypatch):
    s = _store(tmp_path, monkeypatch)
    s.add_asset(kind="logo", filename="l.png", content_type="image/png", uri="vault://l", sha256="l", tags=["primary"])
    s.add_asset(kind="reference", filename="r.jpg", content_type="image/jpeg", uri="vault://r", sha256="r")
    assert [a["kind"] for a in s.assets_for(kinds=["logo"])] == ["logo"]
    assert len(s.assets_for(kinds=["logo", "reference"])) == 2
    assert s.assets_for(tags=["primary"])[0]["filename"] == "l.png"


def test_assets_persist_and_reload(tmp_path, monkeypatch):
    s = _store(tmp_path, monkeypatch)
    s.add_asset(kind="font", filename="f.ttf", content_type="font/ttf", uri="vault://f", sha256="f")
    s._save()
    s2 = project.ProjectStore(user="t")          # fresh instance reads from disk
    assert s2.asset_count() == 1 and s2.assets_for(kinds=["font"])[0]["uri"] == "vault://f"
