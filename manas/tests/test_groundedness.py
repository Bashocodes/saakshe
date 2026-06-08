"""Pin the deterministic curator math — manas's safety property.

The curate loop ends on the groundedness threshold (every claim cited &
non-contradictory) or a max-round rollback, NEVER on "the claims look grounded."
If these drift, the contract that the company's memory is always source-cited and
self-consistent is broken, so the formulas are pinned to exact literals.
"""

from __future__ import annotations

from common import config
from manas.tools import curator


# ─── compute_groundedness ────────────────────────────────────────────────────
def test_all_cited_clears_the_bar():
    """Every claim cites a source, non-contradictory => clears GROUNDING_THRESHOLD."""
    claims = [{"claim": "a", "source": "s1"}, {"claim": "b", "source": "s2"}]
    g = curator.compute_groundedness(claims, 2)
    assert g >= config.GROUNDING_THRESHOLD


def test_uncited_claim_drags_below_the_bar():
    """An uncited claim lowers the citation fraction below the bar on the first pass."""
    claims = [{"claim": "a", "source": "s1"}, {"claim": "b", "source": ""}]
    g = curator.compute_groundedness(claims, 1)
    assert g < config.GROUNDING_THRESHOLD


def test_groundedness_rises_with_rounds():
    """The same claims tighten as curation rounds accumulate (the refine pass)."""
    claims = [{"claim": "a", "source": "s1"}, {"claim": "b", "source": ""}]
    r1 = curator.compute_groundedness(claims, 1)
    r3 = curator.compute_groundedness(claims, 3)
    assert r3 > r1


def test_empty_claims_are_ungrounded():
    assert curator.compute_groundedness([], 3) == 0.0


def test_groundedness_is_clamped_and_deterministic():
    claims = [{"claim": "a", "source": "s1"}, {"claim": "b", "source": "s2"}]
    v = curator.compute_groundedness(claims, 9)
    assert 0.0 <= v <= 1.0
    assert v == curator.compute_groundedness(claims, 9)


# ─── contradiction gating (the negative safety behaviour) ────────────────────
def test_contradiction_gates_groundedness_to_zero():
    """A self-contradicting claim set can NEVER score high enough to commit —
    no matter how many rounds, groundedness is gated to 0.0."""
    contra = [
        {"claim": "we grandfather existing subscribers", "source": "s"},
        {"claim": "we never grandfather existing subscribers", "source": "s"},
    ]
    assert curator.find_contradictions(contra)
    for rnd in range(1, config.MAX_CURATE_ROUNDS + 2):
        assert curator.compute_groundedness(contra, rnd) == 0.0


def test_numeric_clash_is_a_contradiction():
    contra = [
        {"claim": "Pro list price is $29/mo", "source": "s"},
        {"claim": "Pro list price is $39/mo", "source": "s"},
    ]
    assert curator.find_contradictions(contra)


def test_non_contradictory_distinct_claims_do_not_false_positive():
    """Claims about different subjects are not contradictions."""
    fine = [
        {"claim": "Pro list price is $29/mo today", "source": "s1"},
        {"claim": "Palette is warm-paper plus espresso", "source": "s2"},
    ]
    assert curator.find_contradictions(fine) == []


# ─── curate_should_stop: commit / continue / rollback ────────────────────────
def test_commits_at_threshold():
    stop, committed, reason = curator.curate_should_stop(config.GROUNDING_THRESHOLD, 1)
    assert stop is True and committed is True
    assert "commit" in reason


def test_commits_above_threshold():
    stop, committed, _ = curator.curate_should_stop(config.GROUNDING_THRESHOLD + 0.05, 1)
    assert (stop, committed) == (True, True)


def test_continues_below_threshold_under_max_rounds():
    stop, committed, reason = curator.curate_should_stop(config.GROUNDING_THRESHOLD - 0.10, 1)
    assert stop is False and committed is False
    assert "re-synthesise" in reason


def test_rolls_back_at_max_rounds_below_threshold():
    """Max curate rounds without crossing the bar => rollback (no safe commit),
    NOT a commit — manas refuses to write an under-grounded memory."""
    stop, committed, reason = curator.curate_should_stop(
        config.GROUNDING_THRESHOLD - 0.10, config.MAX_CURATE_ROUNDS
    )
    assert stop is True and committed is False
    assert "no safe commit" in reason


def test_rollback_only_at_or_past_max_rounds():
    stop, committed, reason = curator.curate_should_stop(
        config.GROUNDING_THRESHOLD - 0.20, config.MAX_CURATE_ROUNDS - 1
    )
    assert stop is False and committed is False
    assert "rollback" not in reason


# ─── the deterministic FunctionTools (live curator's guards) ─────────────────
def test_verify_citations_flags_uncited():
    out = curator.verify_citations([{"claim": "a", "source": "s"}, {"claim": "b", "source": ""}])
    assert out["all_cited"] is False
    assert out["cited"] == 1
    assert "b" in out["uncited"]


def test_detect_contradiction_reports_pairs():
    out = curator.detect_contradiction([
        {"claim": "we grandfather users", "source": "s"},
        {"claim": "we never grandfather users", "source": "s"},
    ])
    assert out["has_contradiction"] is True
    assert out["contradictions"]
