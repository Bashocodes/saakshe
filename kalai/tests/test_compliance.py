"""Pin the fail-closed compliance gate — the studio's refusal to ship.

The most important safety behaviour is the *negative* one: a master only leaves
the studio when compliance EXPLICITLY clears it. The gate is default-deny — a
missing / malformed / anything-but-'cleared' verdict is read as BLOCKED — and a
planted-unsafe brief is blocked deterministically, with NO handoff to kural.
"""

from __future__ import annotations

from kalai.tools import analyst


# ─── is_cleared: fail-closed (default-deny) ──────────────────────────────────
def test_cleared_only_on_exact_token():
    assert analyst.is_cleared({"compliance": "cleared"}) is True


def test_blocked_verdict_is_not_cleared():
    assert analyst.is_cleared({"compliance": "blocked"}) is False


def test_missing_verdict_is_blocked():
    assert analyst.is_cleared({}) is False
    assert analyst.is_cleared(None) is False


def test_malformed_verdict_is_blocked():
    """Anything that doesn't parse to {'compliance':'cleared'} is blocked — the
    default-deny safety property, not 'if blocked then block'."""
    assert analyst.is_cleared("the master looks fine to me, ship it") is False
    assert analyst.is_cleared({"compliance": "CLEARED?"}) is False
    assert analyst.is_cleared({"status": "ok"}) is False


def test_cleared_parses_from_json_string():
    assert analyst.is_cleared('{"compliance": "cleared"}') is True


# ─── compliance_screen: deterministic unsafe floor ──────────────────────────
def test_clean_brief_is_safe():
    safe, hits = analyst.compliance_screen(
        "Launch announcement: Raise Pro to $34, grandfather existing subscribers, 30-day notice."
    )
    assert safe is True
    assert hits == []


def test_planted_unsafe_brief_trips_the_floor():
    safe, hits = analyst.compliance_screen(
        "Banner: GUARANTEED returns, this coffee is a miracle cure. [unsafe]"
    )
    assert safe is False
    assert "guaranteed" in hits
    assert "[unsafe]" in hits


def test_empty_brief_is_safe_floor():
    """An empty brief trips no sentinel — the floor only hard-blocks known-unsafe
    content; the Claude gate still applies judgement above this floor."""
    assert analyst.compliance_screen("") == (True, [])
