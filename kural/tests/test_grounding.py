"""Pin real Context Pack at frame time (Task 4.1).

In demo, ``fetch_grounding`` returns the Sundara seed fixture, byte-identical (the
pack's version overrides the fixture's so the message is bound to the live memory
the founder approved — but nothing else changes). In live, the bundle is built
FRESH from the REAL passed manas Context Pack + live funnel/market reads via a
mockable seam; if no live source resolves it falls back to the seed fixture, so a
claim is never ungrounded even if a model forgets to call a tool.

The live branch is exercised with a mocked funnel/market seam (the standard way to
test a live integration without creds / network — never a real call in CI). One
creds-gated smoke confirms the live path runs end-to-end when credentials are
present. kural authors NOTHING here — this only seeds the grounding the readers
cite; the post the founder publishes is kalai's own `formats`, untouched.
"""

from __future__ import annotations

import pytest

from common import config
from kural import grounding
from kural.demo_fixtures import DEMO_GROUNDING


# ─── demo: the seed fixture, byte-identical (with the version swap) ───────────
def test_demo_no_pack_is_the_seed_fixture(monkeypatch):
    """Demo mode with no Context Pack grounds from the seed fixture, byte-identical
    (this is the demo-published-output-byte-identical contract)."""
    monkeypatch.setenv("SAAKSHE_MODE", "demo")
    assert grounding.fetch_grounding() == DEMO_GROUNDING
    assert grounding.fetch_grounding(None) == DEMO_GROUNDING


def test_demo_swaps_only_the_pack_version(monkeypatch):
    """Demo mode with a real pack swaps ONLY the manas_context_pack version — the
    message binds to the live memory the founder approved; funnel/market stay the
    fixture's. Nothing else moves (the refactor preserved today's demo behavior)."""
    monkeypatch.setenv("SAAKSHE_MODE", "demo")
    out = grounding.fetch_grounding({"version": "v99", "topic": "pricing"})
    assert out["manas_context_pack"]["version"] == "v99"            # bound to live memory
    assert out["funnel"] == DEMO_GROUNDING["funnel"]               # fixture, unchanged
    assert out["market"] == DEMO_GROUNDING["market"]               # fixture, unchanged
    # Only the version moved; every other memory field is the fixture's, byte-for-byte.
    expected = dict(DEMO_GROUNDING)
    expected["manas_context_pack"] = dict(DEMO_GROUNDING["manas_context_pack"])
    expected["manas_context_pack"]["version"] = "v99"
    assert out == expected


# ─── live: build FRESH from the REAL passed pack + live funnel/market ─────────
def test_live_builds_from_real_pack_and_live_funnel_market(monkeypatch):
    """In live, a resolved live source overrides the fixture — the readers cite the
    org's ACTUAL funnel/market numbers, and the memory section is the REAL passed
    Context Pack (not the canned 1,840 list / Sundara fixture)."""
    monkeypatch.setenv("SAAKSHE_MODE", "live")
    live_fm = {
        "funnel": {"list_size": 4096, "consented_30d_opens": 2500, "topic_match_pct": 71},
        "market": {"competitor_posts_7d": 5, "our_last_post_days": 3},
    }
    monkeypatch.setattr(grounding, "_live_funnel_market", lambda: live_fm)
    real_pack = {"version": "v99", "voice": "LIVE FOUNDER VOICE", "grandfather_promise": "LIVE PROMISE"}
    out = grounding.fetch_grounding(real_pack)
    # funnel/market come from the LIVE source, not the fixture.
    assert out["funnel"]["list_size"] == 4096                      # live, not 1840
    assert out["funnel"] == live_fm["funnel"]
    assert out["market"] == live_fm["market"]
    assert out["funnel"] != DEMO_GROUNDING["funnel"]
    # the memory section is the REAL passed Context Pack, not the fixture's.
    assert out["manas_context_pack"]["voice"] == "LIVE FOUNDER VOICE"
    assert out["manas_context_pack"] == real_pack
    assert out != DEMO_GROUNDING


def test_live_falls_back_to_seed_when_no_source(monkeypatch):
    """In live but with no live funnel/market source resolved, fall back to the seed
    bundle so the readers are never ungrounded."""
    monkeypatch.setenv("SAAKSHE_MODE", "live")
    monkeypatch.setattr(grounding, "_live_funnel_market", lambda: None)
    # No pack → the pure seed fixture.
    assert grounding.fetch_grounding() == DEMO_GROUNDING
    # A pack → the seed fixture with only the version swapped (same as demo).
    out = grounding.fetch_grounding({"version": "v99"})
    assert out["manas_context_pack"]["version"] == "v99"
    assert out["funnel"] == DEMO_GROUNDING["funnel"]


def test_live_funnel_market_is_gated_off_by_default(monkeypatch):
    """Without EXAMPLE_MCP_ENABLE the live funnel/market read is a no-op (None) — the
    opt-in transport pattern, identical to arivu's _live_admin_bundle."""
    monkeypatch.delenv("EXAMPLE_MCP_ENABLE", raising=False)
    assert grounding._live_funnel_market() is None


@pytest.mark.skipif(
    not config.creds_available(), reason="live grounding smoke needs live creds"
)
def test_live_grounding_path_runs_without_error(monkeypatch):
    """Creds-gated smoke: the live path executes end-to-end and returns a non-empty
    bundle (falls back to the seed when the MCP transport isn't enabled)."""
    monkeypatch.setenv("SAAKSHE_MODE", "live")
    out = grounding.fetch_grounding({"version": "v-smoke"})
    assert isinstance(out, dict) and out
    assert out.get("manas_context_pack")
