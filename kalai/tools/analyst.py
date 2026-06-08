"""Deterministic studio math + loop/gate-termination logic.

These functions never depend on what a model says — they are the safety property
of the studio. The Brand-Fidelity loop ends on a numeric threshold or a
max-iteration rollback, never on "looks good to me"; compliance is fail-closed
(default-deny). Pure functions live here so tests can pin them; the ADK
check-agents in agent.py call them, and the demo fixtures and the tests agree on
the SAME compliance sentinel by importing ``compliance_screen`` from here.
"""

from __future__ import annotations

from typing import Any

from common import config
from google.adk.tools import FunctionTool

from ..util import parse_json


# ─── Brand-Fidelity (loop exit) ──────────────────────────────────────────────
def fidelity_should_stop(score: float, round_: int) -> tuple[bool, bool, str]:
    """Return (stop, passed, reason).

    The loop stops when the fidelity score crosses ``FIDELITY_THRESHOLD`` (passed)
    or when ``MAX_FIDELITY_ROUNDS`` is reached without crossing (escalate — NOT a
    pass). The threshold branch is checked first, so a score that is both over the
    bar AND at the round cap reports "on brand", not "escalate". Mirrors arivu's
    prosecution_should_stop shape so the studio's loop has the same safety contract.
    """
    if score >= config.FIDELITY_THRESHOLD:
        return True, True, (
            f"fidelity {score:.1f} ≥ {config.FIDELITY_THRESHOLD} — on brand, ship"
        )
    if round_ >= config.MAX_FIDELITY_ROUNDS:
        return True, False, (
            f"max rounds ({config.MAX_FIDELITY_ROUNDS}) reached at {score:.1f} "
            "— escalate: not on brand"
        )
    return False, False, (
        f"fidelity {score:.1f} < {config.FIDELITY_THRESHOLD} — regenerate"
    )


def read_score(raw: Any) -> float:
    """Parse the scorer's reported fidelity out of state (output_key stores text)."""
    d = raw if isinstance(raw, dict) else parse_json(raw)
    try:
        return float(d.get("score", 0.0))
    except (TypeError, ValueError):
        return 0.0


# ─── Compliance (fail-closed gate) ───────────────────────────────────────────
# A deterministic pre-screen of the brief itself, shared by the demo fixture and
# the tests so they agree on exactly what trips the gate. Any brief carrying one
# of these sentinels is unsafe and MUST be blocked even before a model looks at
# it; the live Claude gate adds judgement on top, but the safety floor is here.
UNSAFE_SENTINELS = (
    "guaranteed",          # an unprovable performance/financial claim
    "cure",                # a health/medical claim a coffee brand can't make
    "miracle",
    "competitor logo",     # trademark / rights violation
    "#1 in the world",     # unsubstantiated superiority claim
    "[unsafe]",            # explicit test/planted marker
)


def compliance_screen(brief: str) -> tuple[bool, list[str]]:
    """Deterministic floor: (safe, reasons). safe=False if any sentinel is present.

    This is the fail-closed safety floor — it never *clears* a brief on its own
    (the Claude gate does that with judgement); it only forces a BLOCK when the
    brief plainly violates the rules. The fixture reads it so the canned compliance
    verdict matches; the test reads it so a planted-unsafe brief is provably blocked.
    """
    text = (brief or "").lower()
    hits = [s for s in UNSAFE_SENTINELS if s in text]
    return (not hits), hits


def is_cleared(raw: Any) -> bool:
    """Fail-closed read of a compliance verdict: cleared ONLY on the exact token.

    Missing / malformed / anything-but-"cleared" → blocked. This is the safety
    property, written as default-deny — not "if blocked then block".
    """
    d = raw if isinstance(raw, dict) else parse_json(raw)
    return d.get("compliance") == "cleared"


# ─── Deterministic tool the Designer calls in live mode ──────────────────────
def estimate_spend(platforms: int, gen_passes: int) -> dict:
    """Estimate kalai's token/media spend for a master (the studio's one
    irreversible act). Deterministic given the platform count and gen passes."""
    per_platform = 0.06          # media + copy gen per platform
    per_pass = 0.04              # each fidelity regeneration pass
    spend = round(platforms * per_platform + gen_passes * per_pass, 2)
    return {
        "platforms": platforms,
        "gen_passes": gen_passes,
        "spend_usd": spend,
        "note": "kalai's only world-facing act is token spend; it holds no channel keys",
    }


fidelity_check_tool = FunctionTool(func=estimate_spend)
estimate_spend_tool = FunctionTool(func=estimate_spend)
