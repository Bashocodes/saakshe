"""kalai — the 4-scorer Brand-Fidelity panel (the studio's chamber).

The single Brand-Fidelity scorer is decomposed into a panel of THREE Gemini Flash
seats, each judging one MEDIA lens of "on-brand + cleared" (the voice lens lives in
kural, the word faculty):

  * **brand**      — brand-consistency: palette / lockups / grid vs. the asset bank
  * **platform**   — platform-fit: the crop/format right for x · ig · linkedin
  * **compliance** — compliance-edge: claims/rights/tone risk a hair before the gate

A deterministic aggregate (a documented WEIGHTED MEAN, reported to the canon's
1-decimal precision) folds the sub-scores into the ONE ``FIDELITY_SCORE`` the
loop's deterministic checker reads. The model's three numbers are *reported*; the
loop exit stays owned by ``tools.analyst.fidelity_should_stop`` — never "looks good."

This mirrors arivu's mantri-ensemble shape (``ParallelAgent`` of disjoint seats →
a deterministic reducer), instantiated for kalai's deciding question: *is it
on-brand + cleared?* The seats are Gemini Flash (panel advisors), as the company's
model split prescribes.

**Demo invariant (the regression bar):** ``aggregate(demo_subscores(rnd))`` equals
the sealed canon climb ``[6.8, 8.4, 9.1][rnd-1]`` EXACTLY, so decomposing the score
never moves the loop's exit. The demo fixtures and the loop reducer both route
through THIS module (``demo_subscores`` / ``aggregate``), so the unit test and the
live climb can't drift onto two hand-tuned tables.
"""

from __future__ import annotations

from typing import Any

from google.adk.agents import LlmAgent
from google.adk.agents.readonly_context import ReadonlyContext

from common import config, models
from . import prompts
from .state import NS, SCORERS, StateKeys
from .util import brand_block, parse_json

# ─── the documented weighted mean (a partition of unity) ──────────────────────
# brand-consistency is the heaviest lens (the master lives or dies on the asset
# bank); the other three lenses split the remainder evenly. The weights name the
# same lenses as the seats / sub-state-keys / ``demo_subscores`` keys, so there is
# never a mapping table to get wrong.
# kalai is MEDIA-ONLY — the voice lens lives in kural (the word faculty). The three
# media lenses partition to unity, brand heaviest (the master lives or dies on the
# asset bank), platform + compliance splitting the remainder. The demo climb below
# is sealed to the canon [6.8, 8.4, 9.1] under these weights.
WEIGHTS: dict[str, float] = {
    "brand": 0.50,
    "platform": 0.25,
    "compliance": 0.25,
}

# Reported to ONE decimal — the canon's reporting precision (every fidelity beat
# streams ``.1f``). Rounding here makes the weighted mean land EXACTLY on the canon
# literals (e.g. a raw 6.800000000000001 → 6.8), so the tolerant unit test and
# ``test_make.py``'s exact list-equality climb both stay green.
_REPORT_DP = 1


def aggregate(subs: dict[str, float]) -> float:
    """Fold the four sub-scores into the one fidelity score: a weighted mean.

    ``subs`` maps each lens in :data:`WEIGHTS` to its 0–10 score. The result is the
    ``WEIGHTS``-weighted mean, reported to one decimal place. Missing lenses score
    0.0 (a silent seat drags the master down — fail-toward-safe, not fail-open).
    """
    total = sum(float(subs.get(lens, 0.0)) * weight for lens, weight in WEIGHTS.items())
    return round(total, _REPORT_DP)


# ─── deterministic demo sub-scores: the canon climb, decomposed per seat ──────
# Each round's four numbers are genuine per-seat judgements (the seats DISAGREE —
# brand-consistency is the lagging lens that climbs the most; compliance-edge stays
# strong throughout), whose weighted mean is the sealed climb value for that round.
# 1-INDEXED by round (round 1 → 6.8), matching ``CANON["fidelity_climb"]``.
# voice dropped (it lives in kural): .5·brand + .25·platform + .25·compliance lands
# EXACTLY on the canon — r1 .5·6.4+.25·6.9+.25·7.5 = 6.8, r2 .5·8.1+.25·8.4+.25·9.0
# = 8.4, r3 .5·9.0+.25·9.0+.25·9.4 = 9.1. brand stays the lagging lens that climbs
# most; compliance stays strong — the same narrative, three lenses.
_DEMO_SUBSCORES: dict[int, dict[str, float]] = {
    1: {"brand": 6.4, "platform": 6.9, "compliance": 7.5},  # → 6.8
    2: {"brand": 8.1, "platform": 8.4, "compliance": 9.0},  # → 8.4
    3: {"brand": 9.0, "platform": 9.0, "compliance": 9.4},  # → 9.1
}


def demo_subscores(rnd: int) -> dict[str, float]:
    """The four scripted sub-scores for a 1-indexed loop round.

    ``aggregate(demo_subscores(rnd)) == CANON["fidelity_climb"][rnd-1]`` exactly.
    Out-of-range rounds clamp to the nearest end of the climb (so a runaway loop
    keeps reporting the top-of-climb value rather than 0.0)."""
    n = len(config.CANON["fidelity_climb"])
    clamped = min(max(int(rnd), 1), n)
    return dict(_DEMO_SUBSCORES[clamped])


# ─── the four scorer seats (Gemini Flash · panel advisors) ────────────────────
def _org_name(ctx: ReadonlyContext) -> str:
    org = ctx.state.get("org") or {}
    return org.get("name", "the company") if isinstance(org, dict) else str(org)


def _brand(ctx: ReadonlyContext) -> str:
    blk = ctx.state.get(StateKeys.BRAND_BLOCK)
    if blk:
        return blk
    # Same re-fetch as sub_agents._brand: scorers must grade against the real
    # canon, never a "(brand canon pending)" placeholder, whenever the Context
    # Pack is in state.
    pack = ctx.state.get(StateKeys.CONTEXT_PACK)
    if isinstance(pack, dict) and pack:
        return brand_block(pack)
    return "(brand canon pending)"


def _scorer_instruction(lens: str, display: str, focus: str):
    """Build one scorer seat's instruction from live state — the lens-specific
    steer, the current design + copy, the brand asset bank, and the round marker
    the deterministic demo resolver keys on."""

    def provider(ctx: ReadonlyContext) -> str:
        rnd = ctx.state.get(StateKeys.FIDELITY_ROUND, 0)
        design = ctx.state.get(StateKeys.DESIGN, {})
        copy = ctx.state.get(StateKeys.COPY, {})
        if not isinstance(design, dict):
            design = parse_json(design)
        if not isinstance(copy, dict):
            copy = parse_json(copy)
        return (
            prompts.SCORER_BASE
            .replace("{org}", _org_name(ctx))
            .replace("{display}", display)
            .replace("{lens}", lens)
            .replace("{round}", str(rnd))
            + f"\nLENS FOCUS: {focus}\n\n"
            + f"DESIGN:\n{_dumps(design)}\n\n"
            + f"COPY:\n{_dumps(copy)}\n\n"
            + f"BRAND ASSET BANK (manas canon):\n{_brand(ctx)}\n"
        )

    return provider


def _dumps(obj: Any) -> str:
    import json

    return json.dumps(obj, indent=2)


def _sub_state_key(lens: str) -> str:
    """The disjoint sub-key a scorer seat writes (e.g. ``fidelity_sub_brand``)."""
    return f"{StateKeys.FIDELITY_SCORE}_sub_{lens}"


def build_scorer_panel() -> list[LlmAgent]:
    """The four Brand-Fidelity scorer seats, each writing a DISJOINT sub-key so the
    parallel seats never clobber each other (they'd race on one ``output_key``)."""
    panel: list[LlmAgent] = []
    for lens, display, focus in SCORERS:
        if lens not in WEIGHTS:
            continue  # the voice lens lives in kural — media lenses only
        panel.append(
            LlmAgent(
                name=f"fidelity_{lens}_scorer",
                model=models.gemini_flash(NS, f"fidelity__{lens}"),
                description=f"The {display} scorer — scores the {lens} lens (in the fidelity loop).",
                instruction=_scorer_instruction(lens, display, focus),
                output_key=_sub_state_key(lens),
            )
        )
    return panel
