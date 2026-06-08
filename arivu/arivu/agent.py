"""arivu — the assembled chamber. Exports `root_agent`.

The ONE earned convergence pipeline:

    chair_frame (Gemini Pro · frames + grounds)
      → ParallelAgent: 5 mantris (Gemini Flash · disjoint lenses, in parallel)
      → LoopAgent: debate (moderator + deterministic convergence check)
      → chair_synthesizer (Claude · Vertex · the verdict)
      → LoopAgent: prosecution (prosecutor + defensibility ≥ 0.80 check / rollback)
      → gate (halts at the single HITL approval)

Parallel and Loop are *earned* here: multi-lens deliberation genuinely needs
Parallel; the debate and the prosecution genuinely need Loop. Every loop exits on
a numeric threshold or a max-iteration rollback — never on "the advisors agreed."

The executor (real, irreversible action) is deliberately NOT part of root_agent:
the pipeline halts at the gate, and execution fires only after a human approval —
see runner.execute_decision / tools.executor.
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

from . import config, models, sub_agents
from .tools import analyst
from .util import parse_json

models.configure_runtime()
SK = config.StateKeys


# ─── Deterministic termination agents (no model — pure safety logic) ──────────
class DebateCheckAgent(BaseAgent):
    """Computes convergence from the positions and escalates on threshold / cap."""

    async def _run_async_impl(
        self, ctx: InvocationContext
    ) -> AsyncGenerator[Event, None]:
        state = ctx.session.state
        rnd = int(state.get(SK.DEBATE_ROUND, 0)) + 1
        positions = analyst.read_positions(state)
        conv = analyst.compute_convergence(positions, rnd)
        stop, reason = analyst.debate_should_stop(conv, rnd)
        history = list(state.get(SK.DEBATE_HISTORY, []))
        history.append({"round": rnd, "convergence": conv, "reason": reason})
        delta = {
            SK.DEBATE_ROUND: rnd,
            SK.CONVERGENCE: conv,
            SK.DEBATE_DONE: stop,
            SK.DEBATE_HISTORY: history,
        }
        state.update(delta)
        yield Event(
            author=self.name,
            actions=EventActions(state_delta=delta, escalate=stop),
        )


class ProsecutionCheckAgent(BaseAgent):
    """Reads the prosecutor's self-assessed defensibility and escalates on
    threshold; a max-iteration cap triggers a rollback ('no safe decision')."""

    async def _run_async_impl(
        self, ctx: InvocationContext
    ) -> AsyncGenerator[Event, None]:
        state = ctx.session.state
        prosecution = state.get(SK.PROSECUTION, {})
        if not isinstance(prosecution, dict):
            prosecution = parse_json(prosecution)
        try:
            defens = float(prosecution.get("defensibility", 0.0))
        except (TypeError, ValueError):
            defens = 0.0
        rnd = int(state.get(SK.PROSECUTION_ROUND, 0)) + 1
        stop, survived, reason = analyst.prosecution_should_stop(defens, rnd)
        history = list(state.get(SK.PROSECUTION_HISTORY, []))
        history.append({"round": rnd, "defensibility": defens, "survived": survived, "reason": reason})
        delta = {
            SK.PROSECUTION_ROUND: rnd,
            SK.DEFENSIBILITY: defens,
            SK.VERDICT_SURVIVED: survived,
            SK.PROSECUTION_HISTORY: history,
        }
        state.update(delta)
        yield Event(
            author=self.name,
            actions=EventActions(state_delta=delta, escalate=stop),
        )


class GateAgent(BaseAgent):
    """The single HITL gate. Sets the gate status and halts — the pipeline ends
    here; execution is a separate, human-approved step."""

    async def _run_async_impl(
        self, ctx: InvocationContext
    ) -> AsyncGenerator[Event, None]:
        state = ctx.session.state
        survived = bool(state.get(SK.VERDICT_SURVIVED, False))
        status = "awaiting_approval" if survived else "no_safe_decision"
        state[SK.GATE_STATUS] = status
        yield Event(
            author=self.name,
            actions=EventActions(state_delta={SK.GATE_STATUS: status}),
        )


# ─── Assemble the chamber ────────────────────────────────────────────────────
def build_root_agent() -> SequentialAgent:
    deliberation = ParallelAgent(
        name="sabha_deliberation",
        description="Five disjoint mantris argue in parallel — anti-groupthink fan-out.",
        sub_agents=sub_agents.build_mantris(),
    )
    debate_loop = LoopAgent(
        name="debate_loop",
        description="Cross-rebuttal until a numeric convergence threshold or cap.",
        sub_agents=[sub_agents.build_debate_moderator(), DebateCheckAgent(name="debate_check")],
        max_iterations=config.MAX_DEBATE_ROUNDS,
    )
    prosecution_loop = LoopAgent(
        name="prosecution_loop",
        description="Verdict ↔ prosecution until defensibility ≥ 0.80 or rollback.",
        sub_agents=[sub_agents.build_prosecutor(), ProsecutionCheckAgent(name="prosecution_check")],
        max_iterations=config.MAX_PROSECUTION_ROUNDS,
    )
    return SequentialAgent(
        name="arivu",
        description=(
            "arivu — the faculty of judgment. A grounded chamber that deliberates, "
            "prosecutes its own verdict, and halts at one human gate before acting."
        ),
        sub_agents=[
            sub_agents.build_frame_agent(),
            deliberation,
            debate_loop,
            sub_agents.build_chair_synthesizer(),
            prosecution_loop,
            GateAgent(name="gate"),
        ],
    )


root_agent = build_root_agent()
