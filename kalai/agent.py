"""kalai — the assembled studio. Exports ``root_agent``.

The ONE earned production pipeline:

    creative_director (Claude · Vertex · frames concept + brand guardrails)
      → ParallelAgent: Designer/Producer + Copy & SEO (disjoint lanes, in parallel)
      → LoopAgent: Brand-Fidelity (scorer + deterministic checker · climb to threshold)
      → compliance_gate (Claude · Vertex · FAIL-CLOSED — blocks unless cleared)

Parallel is *earned*: the Designer and the Copy desk are genuinely independent and
run concurrently — anti-bottleneck fan-out, not a stylistic flourish. Loop is
*earned*: a real numeric climb (6.8 → 8.4 → 9.1) to FIDELITY_THRESHOLD with a
max-round rollback, and the exit is owned by the deterministic checker — never
"looks good." Compliance is fail-closed by construction (default-deny), so the
handoff is safe even if the model misbehaves.

There is NO founder gate here: the only creative gate is at the mouth (kural, tap 2).
kalai's only world-facing irreversible act is token spend; it holds no channel keys
and never publishes. The handoff to kural is assembled by runner.make() from the
final pipeline state.
"""

from __future__ import annotations

from typing import AsyncGenerator

from google.adk.agents import (
    BaseAgent,
    LoopAgent,
    ParallelAgent,
    SequentialAgent,
)
from google.adk.agents.invocation_context import InvocationContext
from google.adk.events import Event, EventActions

from common import config
from . import scorers, sub_agents
from .state import StateKeys as SK
from .tools import analyst


# ─── Deterministic panel reducer (no model — pure assembly of the 4 sub-scores) ─
class ScorerReducer(BaseAgent):
    """Fold the four Brand-Fidelity scorer seats into the ONE FIDELITY_SCORE the
    loop's checker reads. No model — pure assembly: read each seat's disjoint
    sub-key, pull its 0–10 ``score``, and write the documented weighted mean
    (``scorers.aggregate``) as a DICT ``{"score", "subs"}`` (a dict because
    ``analyst.read_score`` does ``d.get("score")`` — a bare float would parse to
    0.0 and silently stall the climb). Routing both the demo replay and this reducer
    through ``scorers`` keeps the unit test and the live climb on ONE table."""

    async def _run_async_impl(
        self, ctx: InvocationContext
    ) -> AsyncGenerator[Event, None]:
        state = ctx.session.state
        subs: dict[str, float] = {}
        for lens in scorers.WEIGHTS:
            raw = state.get(scorers._sub_state_key(lens))
            subs[lens] = analyst.read_score(raw)
        score = scorers.aggregate(subs)
        consolidated = {"score": score, "subs": subs}
        state[SK.FIDELITY_SCORE] = consolidated
        yield Event(
            author=self.name,
            actions=EventActions(state_delta={SK.FIDELITY_SCORE: consolidated}),
        )


# ─── Deterministic termination / safety agents (no model — pure safety logic) ─
class FidelityCheckAgent(BaseAgent):
    """Reads the scorer's reported fidelity and escalates on threshold; a
    max-iteration cap escalates as 'not on brand' (no false pass). The loop exit
    is OWNED here, not by the model — the score is reported, the decision is math."""

    async def _run_async_impl(
        self, ctx: InvocationContext
    ) -> AsyncGenerator[Event, None]:
        state = ctx.session.state
        score = analyst.read_score(state.get(SK.FIDELITY_SCORE))
        rnd = int(state.get(SK.FIDELITY_ROUND, 0)) + 1
        stop, passed, reason = analyst.fidelity_should_stop(score, rnd)
        history = list(state.get(SK.FIDELITY_HISTORY, []))
        history.append({"round": rnd, "score": score, "passed": passed, "reason": reason})
        delta = {
            SK.FIDELITY_ROUND: rnd,
            SK.FIDELITY_SCORE: score,
            SK.FIDELITY_DONE: stop,
            SK.FIDELITY_PASSED: passed,
            SK.FIDELITY_HISTORY: history,
        }
        state.update(delta)
        yield Event(
            author=self.name,
            actions=EventActions(state_delta=delta, escalate=stop),
        )


class ComplianceCheckAgent(BaseAgent):
    """Reads the Claude compliance gate's verdict FAIL-CLOSED: cleared only on the
    exact 'cleared' token, blocked otherwise (missing/malformed/anything-else).
    Records the boolean the handoff is gated on — safe by construction."""

    async def _run_async_impl(
        self, ctx: InvocationContext
    ) -> AsyncGenerator[Event, None]:
        state = ctx.session.state
        cleared = analyst.is_cleared(state.get(SK.COMPLIANCE))
        # Belt-and-suspenders: the deterministic brief screen can hard-block too,
        # so an unsafe brief is blocked even if a live gate were ever fooled.
        safe, _hits = analyst.compliance_screen(state.get(SK.BRIEF, ""))
        cleared = cleared and safe
        state[SK.COMPLIANCE_CLEARED] = cleared
        yield Event(
            author=self.name,
            actions=EventActions(state_delta={SK.COMPLIANCE_CLEARED: cleared}),
        )


# ─── Assemble the studio ─────────────────────────────────────────────────────
def build_root_agent() -> SequentialAgent:
    production = ParallelAgent(
        name="kalai_production",
        description="Designer/Producer + Copy & SEO produce in parallel — disjoint lanes.",
        sub_agents=sub_agents.build_producers(),
    )
    scorer_panel = ParallelAgent(
        name="brand_fidelity_panel",
        description="Three disjoint media scorers (brand · platform · compliance) score in parallel.",
        sub_agents=scorers.build_scorer_panel(),
    )
    fidelity_loop = LoopAgent(
        name="brand_fidelity_loop",
        description="Panel-score against the brand asset bank until ≥ threshold or max-round rollback.",
        sub_agents=[
            scorer_panel,
            ScorerReducer(name="fidelity_reducer"),
            FidelityCheckAgent(name="fidelity_check"),
        ],
        max_iterations=config.MAX_FIDELITY_ROUNDS,
    )
    return SequentialAgent(
        name="kalai",
        description=(
            "kalai — the studio that MAKES. A brief enters; an on-brand, "
            "compliance-cleared multi-platform master exits and is handed to kural. "
            "No channel keys; never publishes; its only world-facing act is token spend."
        ),
        sub_agents=[
            sub_agents.build_creative_director(),
            production,
            fidelity_loop,
            sub_agents.build_compliance_gate(),
            ComplianceCheckAgent(name="compliance_check"),
        ],
    )


root_agent = build_root_agent()
