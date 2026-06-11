"""Pin the store factory's durability seam — SAAKSHE_OWNER_STORE=supabase.

The gated profile pins SAAKSHE_STORE=file for the seeded judge demo, which also
forced OWNERS onto the container filesystem: every redeploy wiped the founder's
connections ("not connected yet" after each deploy). The owner-store opt-in
sends PER-USER stores to Supabase while the global/default ("founder") store —
the judge demo — stays file."""

from __future__ import annotations

from common import project


class _FakeSupaStore:
    def __init__(self, user_id):
        self.user_id = user_id


def _patch_supastore(monkeypatch, available=True):
    import common.supastore as supastore

    monkeypatch.setattr(supastore, "available", lambda: available)
    monkeypatch.setattr(supastore, "SupabaseStore", _FakeSupaStore)


def test_owner_store_optin_sends_users_to_supabase(monkeypatch):
    monkeypatch.delenv("SAAKSHE_STORE", raising=False)
    monkeypatch.setenv("SAAKSHE_OWNER_STORE", "supabase")
    _patch_supastore(monkeypatch)
    s = project._make_store("user-abc123")
    assert isinstance(s, _FakeSupaStore) and s.user_id == "user-abc123"


def test_owner_store_optin_keeps_judge_demo_on_file(monkeypatch):
    """The global default store ('founder' — the seeded demo every judge sees)
    must stay file-backed even with the owner opt-in set."""
    monkeypatch.delenv("SAAKSHE_STORE", raising=False)
    monkeypatch.setenv("SAAKSHE_OWNER_STORE", "supabase")
    _patch_supastore(monkeypatch)
    s = project._make_store("founder")
    assert isinstance(s, project.ProjectStore)


def test_owner_store_falls_back_when_unavailable(monkeypatch):
    monkeypatch.delenv("SAAKSHE_STORE", raising=False)
    monkeypatch.setenv("SAAKSHE_OWNER_STORE", "supabase")
    _patch_supastore(monkeypatch, available=False)
    s = project._make_store("user-abc123")
    assert isinstance(s, project.ProjectStore)


def test_no_env_no_change(monkeypatch):
    monkeypatch.delenv("SAAKSHE_STORE", raising=False)
    monkeypatch.delenv("SAAKSHE_OWNER_STORE", raising=False)
    s = project._make_store("user-abc123")
    assert isinstance(s, project.ProjectStore)
