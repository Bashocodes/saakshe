"""Deterministic analyst math + chamber-termination logic.

These functions never depend on what a model says — they are the safety
property of the chamber. Every loop ends on one of these numeric thresholds or a
max-iteration rollback, never on "the advisors agreed." Pure functions live here
so tests can pin them; the ADK check-agents in agent.py call them.
"""

from __future__ import annotations

import statistics
from typing import Any

from .. import config
from ..util import parse_json
from google.adk.tools import FunctionTool


def read_positions(state) -> list[dict[str, Any]]:
    """Parse the five mantri positions out of state (output_key stores raw text)."""
    out: list[dict[str, Any]] = []
    for _key, _display, state_key, _lens in config.MANTRIS:
        raw = state.get(state_key)
        d = raw if isinstance(raw, dict) else parse_json(raw)
        if d:
            out.append(d)
    return out


# ─── Convergence (debate loop exit) ──────────────────────────────────────────
def compute_convergence(positions: list[dict[str, Any]], round_: int) -> float:
    """A converged-confidence value in [0, 1].

    Rises as the advisors' confidences tighten (agreement) and as rounds
    accumulate (deliberation). Deterministic given the positions and the round.
    """
    confs = [
        float(p.get("confidence", 0.5))
        for p in positions
        if isinstance(p, dict)
    ]
    if len(confs) < 2:
        agreement = 0.5
    else:
        spread = statistics.pstdev(confs)
        agreement = max(0.0, 1.0 - spread / 0.5)  # 0 spread -> 1.0
    convergence = 0.5 * agreement + 0.25 * round_
    return round(min(1.0, convergence), 4)


def debate_should_stop(convergence: float, round_: int) -> tuple[bool, str]:
    if convergence >= config.CONVERGENCE_THRESHOLD:
        return True, f"converged (score {convergence:.2f} ≥ {config.CONVERGENCE_THRESHOLD})"
    if round_ >= config.MAX_DEBATE_ROUNDS:
        return True, f"max rounds ({config.MAX_DEBATE_ROUNDS}) reached"
    return False, f"score {convergence:.2f} < {config.CONVERGENCE_THRESHOLD} — continue"


# ─── Defensibility (prosecution loop exit) ───────────────────────────────────
def prosecution_should_stop(
    defensibility: float, round_: int
) -> tuple[bool, bool, str]:
    """Return (stop, survived, reason).

    Survives only when defensibility crosses the bar. If the max iteration is hit
    without crossing, the chamber stops with a rollback: "no safe decision".
    """
    if defensibility >= config.DEFENSIBILITY_THRESHOLD:
        return True, True, (
            f"defensibility {defensibility:.2f} ≥ {config.DEFENSIBILITY_THRESHOLD} — verdict survives"
        )
    if round_ >= config.MAX_PROSECUTION_ROUNDS:
        return True, False, (
            f"max prosecution rounds ({config.MAX_PROSECUTION_ROUNDS}) reached at "
            f"{defensibility:.2f} — rollback: no safe decision, re-frame"
        )
    return False, False, (
        f"defensibility {defensibility:.2f} < {config.DEFENSIBILITY_THRESHOLD} — re-verdict"
    )


# ─── Deterministic tools the mantris call in live mode ───────────────────────
def elasticity_estimate(
    current_price: float,
    new_price: float,
    base_retention_pct: float,
    margin_pct: float,
) -> dict:
    """Estimate the margin/retention trade of a price move (Economist's tool)."""
    delta = (new_price - current_price) / max(current_price, 1e-9)
    # Simple constant-elasticity proxy; retention erodes ~0.6 per unit price rise.
    est_retention = max(0.0, base_retention_pct * (1 - 0.6 * max(delta, 0)))
    gross_per_user = new_price * (margin_pct / 100.0)
    return {
        "price_delta_pct": round(delta * 100, 1),
        "est_retention_pct": round(est_retention, 1),
        "gross_margin_per_user": round(gross_per_user, 2),
        "note": "retention-adjusted margin; higher price only wins if retention holds",
    }


def scenario_stress(new_price: float, cliff_price: float) -> dict:
    """Stress a price against a known churn cliff (Risk's tool)."""
    over = new_price >= cliff_price
    return {
        "crosses_cliff": over,
        "headroom_usd": round(cliff_price - new_price, 2),
        "verdict": (
            "DANGER: at/above the retention cliff" if over
            else "safe: below the retention cliff"
        ),
    }


elasticity_tool = FunctionTool(func=elasticity_estimate)
scenario_stress_tool = FunctionTool(func=scenario_stress)
