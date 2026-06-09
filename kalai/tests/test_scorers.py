"""Pin the 4-scorer fidelity panel — the chamber decomposition of the brand score.

The single Brand-Fidelity scorer is now a panel of four Gemini Flash seats
(brand-consistency · voice-tone · platform-fit · compliance-edge). A deterministic
aggregate (a documented weighted mean, reported to the canon's 1-dp precision) folds
the four sub-scores into the ONE FIDELITY_SCORE the loop reads.

The safety property these tests pin: the demo sub-scores per round AGGREGATE to the
sealed canon climb 6.8 → 8.4 → 9.1, so decomposing the score never moves the loop's
exit. ``test_fidelity.py`` (the climb math) and ``test_make.py`` (the live climb +
9.1 crossing) are the regression bar this must keep green.
"""

from __future__ import annotations

from common import config
from kalai import scorers


# ─── the panel rosters exactly four seats, named to the chamber ───────────────
def test_panel_has_four_named_scorer_seats():
    assert set(scorers.WEIGHTS) == {"brand", "voice", "platform", "compliance"}
    # a documented weighted mean: the weights are a partition of unity.
    assert abs(sum(scorers.WEIGHTS.values()) - 1.0) < 1e-9


# ─── the aggregate of the 4 demo sub-scores reproduces the canon climb ────────
def test_four_scorers_aggregate_to_canon_climb():
    for rnd, expected in enumerate(config.CANON["fidelity_climb"], start=1):
        subs = scorers.demo_subscores(rnd)            # {brand,voice,platform,compliance}
        assert len(subs) == 4
        assert set(subs) == set(scorers.WEIGHTS)
        assert abs(scorers.aggregate(subs) - expected) < 1e-6


# ─── exact-float pin: the aggregate must land ON the canon literal ────────────
def test_aggregate_lands_exactly_on_the_canon_float():
    """test_make.py asserts the streamed climb == [6.8, 8.4, 9.1] with list
    equality; a weighted mean that lands on 6.800000000000001 would break it.
    The aggregate reports to 1-dp (the canon's reporting precision), so it lands
    exactly on the literal — pin that here as the discriminator."""
    for rnd, expected in enumerate(config.CANON["fidelity_climb"], start=1):
        agg = scorers.aggregate(scorers.demo_subscores(rnd))
        assert agg == expected                        # EXACT float equality, not a tolerance


# ─── the top of the climb passes the bar (9.1 ≥ 8.5) — loop still exits there ─
def test_top_of_the_climb_crosses_the_threshold():
    top = scorers.aggregate(scorers.demo_subscores(len(config.CANON["fidelity_climb"])))
    assert top == config.CANON["fidelity_pass"]       # 9.1
    assert top >= config.FIDELITY_THRESHOLD           # crosses 8.5


# ─── aggregate is deterministic and tolerant of stray keys it weights ─────────
def test_aggregate_is_deterministic():
    subs = scorers.demo_subscores(2)
    assert scorers.aggregate(subs) == scorers.aggregate(dict(subs))


# ─── every round's sub-scores are real per-seat numbers (not a flat copy) ─────
def test_demo_subscores_are_per_seat_not_flat():
    """The panel earns its name only if the seats disagree — a flat copy of the
    target across all four would make the decomposition cosmetic. At least one
    round must carry genuinely differing per-seat scores."""
    differ = False
    for rnd in range(1, len(config.CANON["fidelity_climb"]) + 1):
        vals = list(scorers.demo_subscores(rnd).values())
        if len(set(vals)) > 1:
            differ = True
    assert differ, "demo sub-scores never differ across seats — the panel is cosmetic"
