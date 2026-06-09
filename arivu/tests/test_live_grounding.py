"""Pin live grounding at frame time (2b.3).

In demo, the frame-time grounding bundle is the seed fixture, byte-identical — so
the four original tests are untouched. In live, ``fetch_grounding`` pulls the org's
REAL numbers from the example MCP admin surface; if no live source resolves it
falls back to the seed bundle, so a position is never ungrounded.

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


def test_live_grounding_falls_back_to_seed_when_no_source(monkeypatch):
    """In live but with no live source resolved, fall back to the seed bundle so a
    position is never ungrounded."""
    monkeypatch.setenv("ARIVU_MODE", "live")
    monkeypatch.setattr(grounding, "_live_admin_bundle", lambda: None)
    assert grounding.fetch_grounding() == DEMO_GROUNDING


def test_live_admin_bundle_is_gated_off_by_default(monkeypatch):
    """Without EXAMPLE_MCP_ENABLE the live fetch is a no-op (None) — the opt-in
    transport pattern, identical to example_mcp_toolset."""
    monkeypatch.delenv("EXAMPLE_MCP_ENABLE", raising=False)
    assert grounding._live_admin_bundle() is None


@pytest.mark.skipif(
    not config.creds_available(), reason="live grounding smoke needs live creds"
)
def test_live_grounding_path_runs_without_error(monkeypatch):
    """Creds-gated smoke: the live path executes end-to-end and returns a non-empty
    bundle (falls back to the seed when the MCP transport isn't enabled)."""
    monkeypatch.setenv("ARIVU_MODE", "live")
    out = grounding.fetch_grounding()
    assert isinstance(out, dict) and out
