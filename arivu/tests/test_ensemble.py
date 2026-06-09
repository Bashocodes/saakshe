"""Pin the mantri ensembles — each lens fans into a 3-advisor cited ensemble.

2b.1 deepens the company arivu: every mantri is no longer a lone advisor but a
ParallelAgent of three disjoint sub-advisors (e.g. economist → margin · retention
· competitor-bench) whose disjoint sub-claims a deterministic reducer folds into
the SAME consolidated POS_* position the chamber already consumes — now carrying
an `evidence` list of >= 3 cited sub-claims.

The sacred invariant: the consolidated claim + confidence are byte-identical to
today's _POSITIONS[role] (so the original four arivu tests stay green), and the
signature risk "cliff" catch still survives the deeper path.
"""

from __future__ import annotations

from arivu import config, runner
from arivu.tools import analyst


async def test_each_mantri_fans_into_a_grounded_ensemble():
    state = await runner.deliberate()
    positions = analyst.read_positions(state)

    # The economist position is now backed by 3 cited sub-claims (margin ·
    # retention · competitor-bench), gathered by the parallel ensemble.
    econ = next(p for p in positions if "unit-economics" in p.get("lens", ""))
    assert len(econ.get("evidence", [])) >= 3
    assert all(e.get("source") for e in econ["evidence"])  # every sub-claim cited

    # The signature risk catch still survives the deeper (ensemble) path.
    risk = next(p for p in positions if "downside" in p.get("lens", ""))
    assert "cliff" in risk.get("claim", "").lower()


async def test_every_mantri_carries_three_cited_subclaims():
    """Not just the economist — all five lenses fan into >= 3 cited sub-claims."""
    state = await runner.deliberate()
    positions = analyst.read_positions(state)
    assert len(positions) == 5
    for pos in positions:
        evidence = pos.get("evidence", [])
        assert len(evidence) >= 3, f"{pos.get('lens')} has < 3 sub-claims"
        assert all(e.get("source") for e in evidence), f"{pos.get('lens')} sub-claim uncited"


async def test_consolidated_positions_are_byte_identical_to_today():
    """The deepening rolls UP to today's values: the consolidated claim +
    confidence per lens are unchanged, so convergence + the verdict are intact."""
    from arivu.demo_fixtures import _POSITIONS

    state = await runner.deliberate()
    positions = {p.get("lens"): p for p in analyst.read_positions(state)}
    for role, _display, _key, _lens in config.MANTRIS:
        canon = _POSITIONS[role]
        got = positions[canon["lens"]]
        assert got["claim"] == canon["claim"]
        assert got["confidence"] == canon["confidence"]
        assert got["stance"] == canon["stance"]
        assert got["citation"] == canon["citation"]
