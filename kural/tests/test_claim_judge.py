"""Pin the deterministic Claim-Judge math — the mouth's fact-check safety property.

The Claim-Judge is an LLM-as-judge, but the GATE is a pure numeric threshold:
claim_support >= CLAIM_THRESHOLD (0.80; canon 0.86) verifies; below it loops back
to the writer; the bounded loop hitting MAX_CLAIM_ROUNDS without crossing stops
UNVERIFIED (no safe message). If any of these drift the contract is broken, so
the formulas are pinned to exact literals.
"""

from __future__ import annotations

from common import config
from kural.tools import analyst


# ─── claim_support_of: defensive read, fail-closed ────────────────────────────
def test_claim_support_reads_float_and_clamps():
    assert analyst.claim_support_of({"claim_support": 0.86}) == 0.86
    assert analyst.claim_support_of({"claim_support": 1.5}) == 1.0
    assert analyst.claim_support_of({"claim_support": -0.2}) == 0.0


def test_claim_support_unparseable_fails_closed_to_zero():
    """A judge reply with no usable score reads 0.0 → the claim FAILS, never passes."""
    assert analyst.claim_support_of({}) == 0.0
    assert analyst.claim_support_of({"claim_support": "not-a-number"}) == 0.0


# ─── claim_should_stop: verify / re-ground / rollback ─────────────────────────
def test_claim_verifies_at_threshold():
    stop, verified, reason = analyst.claim_should_stop(config.CLAIM_THRESHOLD, 1)
    assert stop is True
    assert verified is True
    assert "verified" in reason


def test_claim_verifies_at_canon_support():
    """The sealed canon (0.86) clears the 0.80 bar."""
    stop, verified, _ = analyst.claim_should_stop(config.CANON["claim_support"], 1)
    assert (stop, verified) == (True, True)


def test_claim_blocks_unverified_below_threshold_under_max_rounds():
    """Below the bar with rounds left: do not stop, loop back to the writer."""
    stop, verified, reason = analyst.claim_should_stop(config.CLAIM_THRESHOLD - 0.10, 1)
    assert stop is False
    assert verified is False
    assert "back to the writer" in reason


def test_claim_rolls_back_at_max_rounds_below_threshold():
    """Max rewrite rounds without crossing the bar => UNVERIFIED, not a forced pass."""
    stop, verified, reason = analyst.claim_should_stop(
        config.CLAIM_THRESHOLD - 0.10, config.MAX_CLAIM_ROUNDS
    )
    assert stop is True
    assert verified is False
    assert "no safe message" in reason


def test_forbidden_midpoint_does_not_verify():
    """A forbidden animation midpoint (0.81 would round-trip, 0.62 clearly fails)
    must never be presented as the verified canon. The deterministic gate treats
    anything below 0.80 as unverified — 0.62 cannot pass."""
    for bad in config.FORBIDDEN["numbers"]:
        if bad < config.CLAIM_THRESHOLD:
            _, verified, _ = analyst.claim_should_stop(bad, 1)
            assert verified is False, f"{bad} must not verify"
