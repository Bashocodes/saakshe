"""Pin the prosecution rollback path — the chamber's refusal to ship.

The most important safety behaviour is the *negative* one: when the adversarial
prosecutor cannot be defeated, the chamber must NOT survive to the gate. It rolls
back with "no safe decision" rather than approving a verdict it could not defend.
"""

from __future__ import annotations

from arivu import config
from arivu.tools import analyst


def test_max_iter_rollback_returns_no_safe_decision():
    """Drive prosecution across rounds; at the final round, still below the bar,
    it must stop with (True, False, ...) — survived is False, the rollback."""
    below_bar = config.DEFENSIBILITY_THRESHOLD - 0.10

    # Rounds before the max: must keep going, never declaring survival.
    for r in range(config.MAX_PROSECUTION_ROUNDS):
        stop, survived, _ = analyst.prosecution_should_stop(below_bar, r)
        assert stop is False
        assert survived is False

    # The final round: stop, but explicitly NOT survived — the rollback.
    stop, survived, reason = analyst.prosecution_should_stop(
        below_bar, config.MAX_PROSECUTION_ROUNDS
    )
    assert stop is True
    assert survived is False
    assert (stop, survived) == (True, False)
    assert "no safe decision" in reason


def test_below_threshold_never_survives_early():
    """A verdict under the defensibility bar must never survive before the
    chamber has exhausted its prosecution rounds."""
    just_under = config.DEFENSIBILITY_THRESHOLD - 0.01
    for r in range(config.MAX_PROSECUTION_ROUNDS):
        _stop, survived, _reason = analyst.prosecution_should_stop(just_under, r)
        assert survived is False


def test_a_weak_verdict_can_recover_then_survive():
    """The realistic Sundara arc: round 1 nearly shatters (0.71 < bar, continue),
    round 2 re-forms above the bar (survives). The loop neither survives early nor
    rolls back when a later round crosses the threshold."""
    r1_stop, r1_survived, _ = analyst.prosecution_should_stop(0.71, 1)
    assert (r1_stop, r1_survived) == (False, False)  # continue, do not ship yet

    r2_stop, r2_survived, _ = analyst.prosecution_should_stop(0.84, 2)
    assert (r2_stop, r2_survived) == (True, True)  # re-formed above the bar => ship


def test_rollback_only_at_or_past_max_rounds():
    """Below the bar but with rounds still remaining => continue, not rollback."""
    low = config.DEFENSIBILITY_THRESHOLD - 0.20
    stop, survived, reason = analyst.prosecution_should_stop(
        low, config.MAX_PROSECUTION_ROUNDS - 1
    )
    assert stop is False
    assert survived is False
    assert "rollback" not in reason
