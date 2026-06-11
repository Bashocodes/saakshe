"""Founder-taste questions — the chamber asks instead of pretending certainty.

The contract mirrors manas's doubts (see common/a2a.ClarifyingQuestion): a
DETERMINISTIC trigger decides that a question exists — never a model imagining
one. Two triggers, both numeric/structural:

  · close_call   — the verdict survived prosecution (defensibility ≥ threshold)
                   but landed below the comfort bar: the gap between "defensible"
                   and "comfortable" is exactly where founder taste decides.
  · no_safe_path — the chamber rolled back every candidate: only the founder can
                   name which trade-off to accept.

A founder-taste question never blocks grounding and never becomes a gate — it
rides the same questions surface as manas's doubts, signed by the asking agent,
and the founder's answer folds back into memory through the existing
answer-question path.
"""

from __future__ import annotations

from . import a2a, config


def _defens(value) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def close_call(run_id: str, question: str, verdict: dict, defensibility) -> list[a2a.ClarifyingQuestion]:
    """Survived prosecution, but below the comfort bar → ask the founder."""
    if not config.taste_questions_enabled():
        return []
    d = _defens(defensibility)
    if not (config.DEFENSIBILITY_THRESHOLD <= d < config.TASTE_COMFORT):
        return []
    decision = str(verdict.get("decision", "")).strip() or "the verdict"
    dissent = str(verdict.get("dissent", "")).strip()
    dissent_clause = f" The surviving dissent: {dissent}." if dissent else ""
    return [a2a.ClarifyingQuestion(
        id=f"taste-{run_id}",
        text=(f"On “{question}” the chamber settled on: {decision}. It survived "
              f"prosecution at {d:.2f} — defensible, but close enough that your "
              f"taste decides.{dissent_clause} Comfortable proceeding, or should "
              "we soften it?"),
        why=(f"defensibility {d:.2f} sits between the bar "
             f"({config.DEFENSIBILITY_THRESHOLD:.2f}) and the comfort line "
             f"({config.TASTE_COMFORT:.2f})"),
        trigger="founder_taste",
        asked_by="arivu · Verdict Chair",
    )]


def no_safe_path(run_id: str, question: str) -> list[a2a.ClarifyingQuestion]:
    """Every candidate rolled back → only the founder can pick the trade-off."""
    if not config.taste_questions_enabled():
        return []
    return [a2a.ClarifyingQuestion(
        id=f"taste-{run_id}",
        text=(f"On “{question}” no candidate survived the prosecutor — every "
              "path carried a risk the chamber wouldn't sign. Which trade-off "
              "should we accept, or should we drop it?"),
        why="the prosecution loop rolled back every candidate verdict",
        trigger="founder_taste",
        asked_by="arivu · Prosecutor",
    )]
