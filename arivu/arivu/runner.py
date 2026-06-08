"""arivu — run helpers.

`deliberate()` runs the chamber and HALTS at the gate (no side effects).
`execute_decision()` is the separate, human-approved step that fires the executor.
`build_transcript()` renders ordered chamber lines for a CLI or the live bridge.
"""

from __future__ import annotations

from typing import Any

from google.genai import types

from . import config
from .tools import analyst, executor
from .util import parse_json

SK = config.StateKeys
_APP = "arivu"
_USER = "founder"


async def deliberate(question: str | None = None, org: dict | None = None) -> dict[str, Any]:
    """Run the full deliberation chamber; return the final session state as a dict.

    The pipeline ends at the gate — nothing is committed, dispatched, or published.
    """
    from google.adk.runners import InMemoryRunner
    from .agent import root_agent

    runner = InMemoryRunner(agent=root_agent, app_name=_APP)
    init_state: dict[str, Any] = {}
    if question:
        init_state[SK.QUESTION] = question
    init_state[SK.ORG] = org or dict(config.DEFAULT_ORG)

    session = await runner.session_service.create_session(
        app_name=_APP, user_id=_USER, state=init_state
    )
    msg = types.Content(
        role="user",
        parts=[types.Part(text=question or config.DEFAULT_QUESTION)],
    )
    events = []
    async for _event in runner.run_async(
        user_id=_USER, session_id=session.id, new_message=msg
    ):
        events.append(_event)

    final = await runner.session_service.get_session(
        app_name=_APP, user_id=_USER, session_id=session.id
    )
    state = dict(final.state)
    # Real metered token usage (live) — summed inline so arivu keeps no deps.
    inp = out = calls = 0
    for ev in events:
        um = getattr(ev, "usage_metadata", None)
        if not um:
            continue
        p = getattr(um, "prompt_token_count", 0) or 0
        c = getattr(um, "candidates_token_count", 0) or 0
        if p or c:
            inp += int(p)
            out += int(c)
            calls += 1
    state["_usage"] = {"input_tokens": inp, "output_tokens": out, "llm_calls": calls}
    return state


def execute_decision(state: dict, dry_run: bool | None = None) -> dict:
    """Fire the executor on an approved verdict. Real side effects only when
    dry_run is False (the server sets that only after a human approval)."""
    if state.get(SK.GATE_STATUS) not in ("awaiting_approval", "approved", "executed"):
        raise RuntimeError(
            f"Refusing to execute: gate status is {state.get(SK.GATE_STATUS)!r} "
            "(verdict did not survive prosecution)."
        )
    return executor.execute(state, dry_run=dry_run)


def _verdict(state: dict) -> dict:
    v = state.get(SK.VERDICT, {})
    return v if isinstance(v, dict) else parse_json(v)


def _prosecution(state: dict) -> dict:
    p = state.get(SK.PROSECUTION, {})
    return p if isinstance(p, dict) else parse_json(p)


def build_transcript(state: dict) -> list[dict[str, str]]:
    """Ordered, human-readable chamber transcript built from final state."""
    lines: list[dict[str, str]] = []

    def add(actor: str, text: str) -> None:
        lines.append({"actor": actor, "text": text})

    org = state.get(SK.ORG, config.DEFAULT_ORG)
    org_name = org.get("name", "the company") if isinstance(org, dict) else str(org)
    add("question", f'received: "{state.get(SK.QUESTION, config.DEFAULT_QUESTION)}" · {org_name}')

    subq = state.get(SK.SUBQUESTIONS)
    subq_parsed = parse_json(subq) if isinstance(subq, str) else (subq or {})
    qs = subq_parsed.get("subquestions") if isinstance(subq_parsed, dict) else None
    if qs:
        add("chair», frame", "decompose + ground via tools: manas A2A + admin_stats + admin_analytics")

    for pos in analyst.read_positions(state):
        lens = pos.get("lens", "?")
        claim = pos.get("claim", "")
        conf = pos.get("confidence", "")
        add(f"{_lens_actor(lens)}»", f"{claim}  (conf {conf})")

    # Risk highlight — the chamber's signature catch.
    risk = next(
        (p for p in analyst.read_positions(state) if "downside" in p.get("lens", "")),
        None,
    )
    if risk:
        add("risk», CATCH", "the churn cliff the lone-analyst path misses")

    conv = state.get(SK.CONVERGENCE)
    if conv is not None:
        add("debate»", f"converged — score {conv} (deterministic threshold, not 'they agreed')")

    v = _verdict(state)
    if v:
        add("chair», verdict [Claude·Vertex]", v.get("decision", ""))
        if v.get("dissent"):
            add("chair», dissent preserved", v["dissent"])

    history = state.get("prosecution_history") or []
    for h in history:
        verb = "survives" if h.get("survived") else "re-verdict"
        add(
            "prosecutor» [Claude·Vertex]",
            f"round {h.get('round')}: defensibility {h.get('defensibility')} → {verb}",
        )
    defens = state.get(SK.DEFENSIBILITY)
    survived = state.get(SK.VERDICT_SURVIVED)
    if defens is not None and not history:
        add(
            "prosecutor» [Claude·Vertex]",
            f"defensibility {defens} → {'survives' if survived else 'rollback: no safe decision'}",
        )

    gate = state.get(SK.GATE_STATUS)
    if gate == "awaiting_approval":
        add(
            "gate»",
            f"HALT — awaiting founder approval · conf {v.get('confidence', '—')} · "
            f"defensibility {defens} ≥ {config.DEFENSIBILITY_THRESHOLD}",
        )
    elif gate == "no_safe_decision":
        add("gate»", "no safe decision — re-frame (verdict did not survive prosecution)")
    elif gate == "executed":
        res = state.get(SK.RESOLUTION, {})
        add("approved»", f"committed · A2A → kural/kalai · resolution {res.get('url', '')}")
    return lines


def _lens_actor(lens: str) -> str:
    table = {
        "unit-economics": "economist",
        "funnel": "growth",
        "canon": "brand",
        "downside": "risk",
        "can-we-ship": "ops",
    }
    for needle, name in table.items():
        if needle in lens:
            return name
    return lens
