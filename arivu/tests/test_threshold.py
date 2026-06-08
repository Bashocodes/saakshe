"""Pin the deterministic chamber math — the safety property.

Every loop in the chamber ends on one of these numeric thresholds (or a
max-iteration rollback), never on "the advisors agreed." If any of these drift,
the safety contract is broken, so the formulas are pinned to exact literals.
"""

from __future__ import annotations

from arivu import config
from arivu.tools import analyst


# ─── compute_convergence ─────────────────────────────────────────────────────
def test_convergence_zero_spread_is_full_agreement():
    """Identical confidences => agreement 1.0 => 0.5*1.0 + 0.25*round."""
    assert analyst.compute_convergence([{"confidence": 0.8}, {"confidence": 0.8}], 0) == 0.5
    assert analyst.compute_convergence([{"confidence": 0.8}, {"confidence": 0.8}], 1) == 0.75


def test_convergence_rises_with_rounds():
    """The same positions converge harder as deliberation rounds accumulate."""
    r0 = analyst.compute_convergence([{"confidence": 0.7}, {"confidence": 0.7}], 0)
    r1 = analyst.compute_convergence([{"confidence": 0.7}, {"confidence": 0.7}], 1)
    assert r1 > r0


def test_convergence_spread_lowers_agreement():
    """Wider confidence spread => lower convergence at the same round."""
    tight = analyst.compute_convergence([{"confidence": 0.8}, {"confidence": 0.8}], 1)
    wide = analyst.compute_convergence([{"confidence": 0.1}, {"confidence": 0.9}], 1)
    assert wide < tight


def test_convergence_fewer_than_two_positions_defaults_half_agreement():
    """With <2 positions there is no spread to measure: agreement defaults 0.5."""
    assert analyst.compute_convergence([{"confidence": 0.8}], 0) == 0.25
    assert analyst.compute_convergence([], 2) == 0.75


def test_convergence_is_clamped_to_unit_interval():
    """Many rounds + full agreement must not exceed 1.0."""
    v = analyst.compute_convergence([{"confidence": 0.9}, {"confidence": 0.9}], 5)
    assert v == 1.0
    assert 0.0 <= v <= 1.0


def test_convergence_is_deterministic():
    """Same inputs => same output, every time."""
    args = ([{"confidence": 0.74}, {"confidence": 0.69}, {"confidence": 0.86}], 2)
    assert analyst.compute_convergence(*args) == analyst.compute_convergence(*args)


# ─── debate_should_stop: threshold AND max-round exits ────────────────────────
def test_debate_stops_when_converged_at_threshold():
    stop, reason = analyst.debate_should_stop(config.CONVERGENCE_THRESHOLD, 0)
    assert stop is True
    assert "converged" in reason


def test_debate_stops_above_threshold():
    stop, _ = analyst.debate_should_stop(config.CONVERGENCE_THRESHOLD + 0.1, 0)
    assert stop is True


def test_debate_continues_below_threshold_under_max_rounds():
    stop, reason = analyst.debate_should_stop(config.CONVERGENCE_THRESHOLD - 0.25, 0)
    assert stop is False
    assert "continue" in reason


def test_debate_stops_at_max_rounds_even_if_unconverged():
    """The other exit: never loop forever — stop at MAX_DEBATE_ROUNDS regardless."""
    low = config.CONVERGENCE_THRESHOLD - 0.25
    stop, reason = analyst.debate_should_stop(low, config.MAX_DEBATE_ROUNDS)
    assert stop is True
    assert "max rounds" in reason


# ─── prosecution_should_stop: survive / continue / rollback ───────────────────
def test_prosecution_survives_at_threshold():
    """Survives only when defensibility crosses the bar — at exactly the bar."""
    stop, survived, reason = analyst.prosecution_should_stop(
        config.DEFENSIBILITY_THRESHOLD, 0
    )
    assert stop is True
    assert survived is True
    assert "survives" in reason


def test_prosecution_survives_above_threshold():
    stop, survived, _ = analyst.prosecution_should_stop(
        config.DEFENSIBILITY_THRESHOLD + 0.05, 1
    )
    assert (stop, survived) == (True, True)


def test_prosecution_continues_below_threshold_under_max_rounds():
    stop, survived, reason = analyst.prosecution_should_stop(
        config.DEFENSIBILITY_THRESHOLD - 0.10, 1
    )
    assert stop is False
    assert survived is False
    assert "re-verdict" in reason


def test_prosecution_rolls_back_at_max_rounds_below_threshold():
    """Max prosecution rounds without crossing the bar => rollback, NOT survival."""
    stop, survived, reason = analyst.prosecution_should_stop(
        config.DEFENSIBILITY_THRESHOLD - 0.10, config.MAX_PROSECUTION_ROUNDS
    )
    assert stop is True
    assert survived is False
    assert "rollback" in reason


# ─── elasticity_estimate (Economist's tool) ──────────────────────────────────
def test_elasticity_estimate_shape_and_direction():
    out = analyst.elasticity_estimate(29, 39, 74.0, 71.0)
    assert set(out) >= {
        "price_delta_pct",
        "est_retention_pct",
        "gross_margin_per_user",
        "note",
    }
    # +$10 on $29 ~= +34.5% list price.
    assert out["price_delta_pct"] == 34.5
    # A price rise erodes retention from the base (0.6 per unit delta).
    assert out["est_retention_pct"] < 74.0
    # Gross margin per user = new_price * margin%.
    assert out["gross_margin_per_user"] == round(39 * 0.71, 2)


def test_elasticity_no_price_rise_keeps_retention_flat():
    """A flat (or cut) price does not erode the retention base."""
    flat = analyst.elasticity_estimate(29, 29, 80.0, 70.0)
    assert flat["est_retention_pct"] == 80.0
    cut = analyst.elasticity_estimate(29, 25, 80.0, 70.0)
    assert cut["est_retention_pct"] == 80.0  # max(delta, 0) clamps the cut


# ─── scenario_stress (Risk's tool) — cliff crossing ──────────────────────────
def test_scenario_stress_crosses_cliff_at_and_above():
    """crosses_cliff is True at >= the cliff price (the churn cliff catch)."""
    at = analyst.scenario_stress(36, 36)
    assert at["crosses_cliff"] is True
    assert at["headroom_usd"] == 0
    assert "DANGER" in at["verdict"]

    above = analyst.scenario_stress(39, 36)
    assert above["crosses_cliff"] is True
    assert above["headroom_usd"] == -3


def test_scenario_stress_safe_below_cliff():
    below = analyst.scenario_stress(34, 36)
    assert below["crosses_cliff"] is False
    assert below["headroom_usd"] == 2
    assert "safe" in below["verdict"]
