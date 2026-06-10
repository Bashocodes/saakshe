"""Pin live grounding at frame time (2b.3).

In demo, the frame-time grounding bundle is the seed fixture, byte-identical — so
the four original tests are untouched. In live, ``fetch_grounding`` pulls the org's
REAL numbers from the example MCP admin surface; if no live source resolves, the
bundle carries ONLY what is real (the manas corpus section) — fixture numbers
NEVER reach a live chamber ("grounded or silent" means silent, not canned).

The live branch is exercised with a mocked admin fetch (the standard way to test a
live integration without creds / network). One creds-gated smoke confirms the live
path runs end-to-end when credentials are present.
"""

from __future__ import annotations

import pytest

from arivu import config
from arivu.demo_fixtures import DEMO_GROUNDING
from arivu.tools import grounding


def test_demo_grounding_is_the_seed_fixture(monkeypatch):
    """Demo mode grounds from the seed fixture, byte-identical (the 4 originals
    depend on this)."""
    monkeypatch.setenv("ARIVU_MODE", "demo")
    assert grounding.fetch_grounding() == DEMO_GROUNDING


def test_live_grounding_uses_real_numbers_when_available(monkeypatch):
    """In live, a resolved live source overrides the fixture — the chamber argues
    from the org's actual numbers, not the canned 412."""
    monkeypatch.setenv("ARIVU_MODE", "live")
    live_bundle = {"admin_stats": {"paying_users": 999, "current_pro_price": 41}}
    monkeypatch.setattr(grounding, "_live_admin_bundle", lambda: live_bundle)
    out = grounding.fetch_grounding()
    assert out is live_bundle
    assert out["admin_stats"]["paying_users"] == 999          # live, not 412
    assert out != DEMO_GROUNDING


def test_live_no_source_never_serves_fixture_numbers(monkeypatch):
    """In live with no live source AND no reachable corpus, the bundle is EMPTY —
    fixture numbers never reach a live chamber. An advisor with nothing real to
    cite must qualify or stay silent, not argue from a canned 412-user company."""
    from common import a2a

    monkeypatch.setenv("ARIVU_MODE", "live")
    monkeypatch.setattr(grounding, "_live_admin_bundle", lambda: None)
    monkeypatch.delitem(a2a._HANDLERS, "manas.get_founder_context", raising=False)
    out = grounding.fetch_grounding()
    assert out == {}
    assert out != DEMO_GROUNDING


def test_live_fallback_grounds_memory_from_real_corpus(monkeypatch):
    """Live + no admin source: the manas_a2a section is built from the REAL corpus
    (brand/voice + top cited facts) via manas's A2A skill, and NO fixture numbers
    ride along — the chamber argues only from what the founder actually imbibed."""
    from common import a2a

    monkeypatch.setenv("ARIVU_MODE", "live")
    monkeypatch.setattr(grounding, "_live_admin_bundle", lambda: None)
    monkeypatch.setitem(
        a2a._HANDLERS, "manas.get_founder_context",
        lambda topic="company": {
            "version": "v9", "grounded": True,
            "voice_rules": ["plain and warm"], "brand_rules": ["honor grandfathering"],
            "facts": [{"claim": "the product is free to start", "source": "site"}],
        },
    )
    out = grounding.fetch_grounding()
    assert out["manas_a2a"] == {
        "brand_canon": "honor grandfathering",
        "voice": "plain and warm",
        "facts": "the product is free to start",
    }
    assert "admin_stats" not in out                    # fixture numbers never leak live
    assert "admin_analytics_user_growth" not in out


def test_live_fallback_empty_when_corpus_ungrounded(monkeypatch):
    """An UNGROUNDED corpus (nothing imbibed) yields an EMPTY live bundle — never
    the seed fixture. Honest silence beats canned confidence."""
    from common import a2a

    monkeypatch.setenv("ARIVU_MODE", "live")
    monkeypatch.setattr(grounding, "_live_admin_bundle", lambda: None)
    monkeypatch.setitem(
        a2a._HANDLERS, "manas.get_founder_context",
        lambda topic="company": {"version": "v0", "grounded": False,
                                 "voice_rules": [], "brand_rules": []},
    )
    assert grounding.fetch_grounding() == {}


def test_live_admin_bundle_is_gated_off_by_default(monkeypatch):
    """Without EXAMPLE_MCP_ENABLE the live fetch is a no-op (None) — the opt-in
    transport pattern, identical to example_mcp_toolset."""
    monkeypatch.delenv("EXAMPLE_MCP_ENABLE", raising=False)
    assert grounding._live_admin_bundle() is None


@pytest.mark.skipif(
    not config.creds_available(), reason="live grounding smoke needs live creds"
)
def test_live_grounding_path_runs_without_error(monkeypatch):
    """Creds-gated smoke: the live path executes end-to-end. The bundle may be
    empty (nothing real resolved) but it must never be the demo fixture."""
    monkeypatch.setenv("ARIVU_MODE", "live")
    out = grounding.fetch_grounding()
    assert isinstance(out, dict)
    assert out != DEMO_GROUNDING
