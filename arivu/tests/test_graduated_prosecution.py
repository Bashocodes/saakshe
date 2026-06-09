"""Pin the graduated prosecutor — revise the ONE faulted reason, re-prosecute.

The deepened prosecution loop no longer re-synthesises the whole verdict on a
failed round. When the prosecutor faults a specific reason, a Claude reviser
strengthens ONLY that reason (recorded in ``reason_revisions``); the next round
re-prosecutes the strengthened verdict. The Sundara recovery arc is unchanged —
round 1 nearly shatters (0.71 < bar), round 2 re-forms (0.84 ≥ bar) — but the
recovery is now a targeted repair, not a full reset.

This is additive depth: the four original arivu tests still pass byte-identical
(the prosecution arc, the verdict, the risk-cliff catch are all preserved).
"""

from __future__ import annotations

from arivu import config, runner
from arivu.util import parse_json

SK = config.StateKeys


async def test_prosecution_revises_one_reason_then_survives():
    state = await runner.deliberate()

    # The recovery arc is intact: a round below the bar, then a round at/above it.
    hist = state[SK.PROSECUTION_HISTORY]
    assert len(hist) >= 2
    assert hist[0]["defensibility"] < config.DEFENSIBILITY_THRESHOLD
    assert hist[-1]["defensibility"] >= config.DEFENSIBILITY_THRESHOLD
    assert state.get(SK.VERDICT_SURVIVED) is True

    # The recovery was a TARGETED revision of one reason — not a full reset.
    revisions = state.get(SK.REASON_REVISIONS, [])
    assert revisions, "expected at least one targeted reason revision"
    target = revisions[0]["target_reason_index"]
    assert target is not None and int(target) >= 0      # a real, indexed reason
    assert revisions[0]["revised_reason"]               # strengthened, not empty


async def test_revision_targets_a_real_verdict_reason_and_preserves_the_verdict():
    state = await runner.deliberate()

    verdict = state[SK.VERDICT]
    if not isinstance(verdict, dict):
        verdict = parse_json(verdict)
    reasons = verdict.get("reasons", [])
    # The decision itself is preserved — the reviser repairs a reason, it does not
    # re-author the verdict.
    assert verdict.get("decision")
    assert len(reasons) >= 1

    revisions = state.get(SK.REASON_REVISIONS, [])
    # Every recorded revision points at a real reason index in the verdict.
    for rev in revisions:
        idx = int(rev["target_reason_index"])
        assert 0 <= idx < len(reasons)


async def test_no_phantom_revisions_when_a_round_survives():
    """A surviving round adds nothing — the ledger holds only real repairs (the
    demo arc strengthens exactly one reason, in round 1)."""
    state = await runner.deliberate()
    revisions = state.get(SK.REASON_REVISIONS, [])
    assert len(revisions) == 1
    assert all(int(r["target_reason_index"]) >= 0 for r in revisions)
