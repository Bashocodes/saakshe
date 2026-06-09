"""The vault blob backend — demo disk (deterministic, creds-free) + a mockable live seam."""
from __future__ import annotations

import hashlib

from common import vault


def _iso(tmp_path, monkeypatch):
    monkeypatch.setenv("SAAKSHE_PROJECT_DIR", str(tmp_path))   # isolate the vault dir
    monkeypatch.delenv("SAAKSHE_STORE", raising=False)         # demo backend


def test_demo_put_returns_deterministic_content_hash_uri(tmp_path, monkeypatch):
    _iso(tmp_path, monkeypatch)
    data = b"a-logo-png"
    uri = vault.put("asset-1", data, "image/png")
    assert uri == f"vault://{hashlib.sha256(data).hexdigest()[:16]}"
    # same bytes -> same uri (idempotent, content-addressed)
    assert vault.put("asset-1", data, "image/png") == uri


def test_put_get_round_trips_bytes(tmp_path, monkeypatch):
    _iso(tmp_path, monkeypatch)
    data = b"font-file-bytes"
    uri = vault.put("a2", data, "font/ttf")
    assert vault.get(uri) == data


def test_get_missing_returns_none(tmp_path, monkeypatch):
    _iso(tmp_path, monkeypatch)
    assert vault.get("vault://0000000000000000") is None


def test_demo_is_creds_free(tmp_path, monkeypatch):
    _iso(tmp_path, monkeypatch)
    assert vault.available() is False            # no Supabase env -> demo only
    # put/get never construct a client in demo (no exception, pure disk)
    vault.put("a3", b"x", "image/png")
