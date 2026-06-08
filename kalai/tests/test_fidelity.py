"""Pin the Brand-Fidelity loop math — the studio's brand safety property.

The loop ends on the numeric threshold (FIDELITY_THRESHOLD) or a max-iteration
rollback, never on "looks good to me." The sealed canon climb is 6.8 → 8.4 → 9.1:
8.4 FAILS (under the 8.5 bar), 9.1 PASSES. These are pinned to exact literals so a
model can never talk the studio past the bar.
"""

from __future__ import annotations

from common import config
from kalai.tools import analyst


# ─── fidelity_should_stop: exit exactly on threshold ─────────────────────────
def test_fidelity_passes_at_or_above_threshold():
    stop, passed, reason = analyst.fidelity_should_stop(config.FIDELITY_THRESHOLD, 1)
    assert stop is True
    assert passed is True
    assert "on brand" in reason


def test_fidelity_9_1_passes():
    """The top of the canon climb passes (9.1 ≥ 8.5)."""
    stop, passed, _ = analyst.fidelity_should_stop(9.1, 3)
    assert (stop, passed) == (True, True)


def test_fidelity_8_4_fails_under_max_rounds():
    """The middle of the canon climb FAILS — 8.4 < 8.5 — and continues."""
    stop, passed, reason = analyst.fidelity_should_stop(8.4, 2)
    assert stop is False
    assert passed is False
    assert "regenerate" in reason


def test_fidelity_6_8_fails():
    """The bottom of the canon climb fails and continues."""
    stop, passed, _ = analyst.fidelity_should_stop(6.8, 1)
    assert (stop, passed) == (False, False)


def test_fidelity_max_rounds_escalates_not_passes():
    """Hitting the round cap below the bar escalates — it must NOT report a pass."""
    low = config.FIDELITY_THRESHOLD - 0.5
    stop, passed, reason = analyst.fidelity_should_stop(low, config.MAX_FIDELITY_ROUNDS)
    assert stop is True
    assert passed is False
    assert "escalate" in reason


def test_fidelity_threshold_branch_wins_at_round_cap():
    """A score over the bar AND at the round cap reports 'on brand', not 'escalate'
    — the threshold branch is checked before the max-round branch."""
    stop, passed, reason = analyst.fidelity_should_stop(9.1, config.MAX_FIDELITY_ROUNDS)
    assert (stop, passed) == (True, True)
    assert "on brand" in reason


def test_fidelity_is_deterministic():
    args = (8.4, 2)
    assert analyst.fidelity_should_stop(*args) == analyst.fidelity_should_stop(*args)


# ─── the canon climb sequenced through the loop (6.8 fail, 8.4 fail, 9.1 pass) ─
def test_canon_climb_exits_exactly_at_the_top():
    climb = config.CANON["fidelity_climb"]
    assert climb == [6.8, 8.4, 9.1]
    # rounds are 1-indexed by the check-agent (increment-after).
    r1 = analyst.fidelity_should_stop(climb[0], 1)   # 6.8 @ round 1
    r2 = analyst.fidelity_should_stop(climb[1], 2)   # 8.4 @ round 2
    r3 = analyst.fidelity_should_stop(climb[2], 3)   # 9.1 @ round 3
    assert r1[0] is False                            # continue
    assert r2[0] is False                            # 8.4 fails → continue
    assert r3[:2] == (True, True)                    # 9.1 passes at the top


# ─── read_score: tolerant of dict or JSON-string state ───────────────────────
def test_read_score_parses_dict_and_text():
    assert analyst.read_score({"score": 9.1}) == 9.1
    assert analyst.read_score('{"score": 8.4}') == 8.4
    assert analyst.read_score("not json") == 0.0
    assert analyst.read_score(None) == 0.0


# ─── estimate_spend (kalai's only world-facing act) ──────────────────────────
def test_estimate_spend_shape_and_monotonic():
    out = analyst.estimate_spend(3, 3)
    assert set(out) >= {"platforms", "gen_passes", "spend_usd", "note"}
    assert out["spend_usd"] == round(3 * 0.06 + 3 * 0.04, 2)
    # more passes cost more.
    assert analyst.estimate_spend(3, 5)["spend_usd"] > analyst.estimate_spend(3, 1)["spend_usd"]
