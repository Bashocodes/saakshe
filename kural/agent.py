"""kural — the assembled mouth. Exports ``root_agent``.

The ONE earned engagement pipeline:

    envoy_lead (Claude · Vertex · qualify + spine entry, grounds)
      → ParallelAgent: research fan-out (Prospect Scout + Market Watcher, Gemini)
      → LoopAgent: message (Outreach Writer + deterministic Claim-Judge gate)
      → gate (HALTS — the publish sign-off is the founder's tap 2, NOT auto)

Parallel and Loop are *earned* here: the two research lenses are genuinely
disjoint (audience vs timing) and independent, so they belong in a ParallelAgent;
the write↔fact-check needs a real LoopAgent because a failed claim sends the draft
back to the writer to re-ground, bounded by MAX_CLAIM_ROUNDS. Every loop exits on
a numeric threshold (claim_support ≥ CLAIM_THRESHOLD) or a max-iteration rollback
— never on "the copy reads well."

The world-facing acts (send, publish) are deliberately NOT part of root_agent:
the pipeline halts at the gate, and the publish fires only after the founder's
tap-2 approval — see runner.publish / tools.channels. This is arivu's
"executor is not in root_agent" discipline applied to the mouth.
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

from . import grounding, sub_agents
from .state import StateKeys
from .tools import analyst


# ─── Deterministic termination agent (no model — pure safety logic) ───────────
class ClaimCheckAgent(BaseAgent):
    """Reads the Claim-Judge's self-assessed support and escalates on threshold;
    a max-iteration cap stops the loop UNVERIFIED (the mouth stays shut)."""

    async def _run_async_impl(
        self, ctx: InvocationContext
    ) -> AsyncGenerator[Event, None]:
        state = ctx.session.state
        report = analyst.read_claim_report(state)
        support = analyst.claim_support_of(report)
        rnd = int(state.get(StateKeys.CLAIM_ROUND, 0)) + 1
        stop, verified, reason = analyst.claim_should_stop(support, rnd)
        history = list(state.get(StateKeys.CLAIM_HISTORY, []))
        history.append({"round": rnd, "claim_support": support, "verified": verified, "reason": reason})
        delta = {
            StateKeys.CLAIM_ROUND: rnd,
            StateKeys.CLAIM_SUPPORT: support,
            StateKeys.CLAIM_VERIFIED: verified,
            StateKeys.CLAIM_HISTORY: history,
        }
        state.update(delta)
        yield Event(
            author=self.name,
            actions=EventActions(state_delta=delta, escalate=stop),
        )


class GateAgent(BaseAgent):
    """The publish gate (the HITL · tap 2). Sets the gate status and HALTS — the
    pipeline ends here; the publish is a separate, human-approved step. When the
    message never verified, the gate is 'no_safe_message' and nothing is offered."""

    async def _run_async_impl(
        self, ctx: InvocationContext
    ) -> AsyncGenerator[Event, None]:
        state = ctx.session.state
        verified = bool(state.get(StateKeys.CLAIM_VERIFIED, False))
        status = "awaiting_approval" if verified else "no_safe_message"
        state[StateKeys.GATE_STATUS] = status
        yield Event(
            author=self.name,
            actions=EventActions(state_delta={StateKeys.GATE_STATUS: status}),
        )


# ─── Assemble the mouth ───────────────────────────────────────────────────────
def build_root_agent() -> SequentialAgent:
    coordinator = sub_agents.build_coordinator()
    # Ground at the spine entry, before any seat speaks.
    coordinator.before_agent_callback = grounding.ground_callback

    research = ParallelAgent(
        name="research_fanout",
        description="Two disjoint scouts (audience, timing) research in parallel — earned fan-out.",
        sub_agents=sub_agents.build_research_scouts(),
    )
    # Writer drafts → Claim-Judge (Claude) fact-checks every claim → the
    # deterministic ClaimCheck reads the judge's claim_support and either escalates
    # (verified) or loops back to the writer to re-ground (bounded by MAX_CLAIM_ROUNDS).
    message_loop = LoopAgent(
        name="message_loop",
        description="Writer → Claim-Judge → numeric gate, until claim_support ≥ 0.80 or a bounded rollback.",
        sub_agents=[
            sub_agents.build_writer(),
            sub_agents.build_claim_judge(),
            ClaimCheckAgent(name="claim_check"),
        ],
        max_iterations=config.MAX_CLAIM_ROUNDS,
    )
    return SequentialAgent(
        name="kural",
        description=(
            "kural — the company's only mouth. Qualifies the engagement, researches "
            "in parallel, writes founder-voice outreach, fact-checks every claim at a "
            "numeric gate, and HALTS at the founder's publish sign-off before saying "
            "anything to the world."
        ),
        sub_agents=[coordinator, research, message_loop, GateAgent(name="gate")],
    )


root_agent = build_root_agent()
