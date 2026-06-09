"""kural — the assembled mouth. Exports ``root_agent``.

The ONE earned engagement pipeline (after the separation fix):

    envoy_lead (Claude · Vertex · qualify + spine entry, grounds)
      → ParallelAgent: research fan-out (Prospect Scout + Market Watcher, Gemini)
      → gate (HALTS — the publish sign-off is the founder's tap 2, NOT auto)

kural authors NOTHING. kalai owns all copy (caption + every channel variant,
fact-checked in its own fidelity loop); kural reads that cleared master, qualifies
the engagement, researches the audience/timing in parallel, and HALTS at the
publish gate. The old Outreach Writer + Claim Judge are retired — kural carries
kalai's master untouched, so the company has exactly one mouth and one author.

Parallel is *earned* here: the two research lenses are genuinely disjoint
(audience vs timing) and independent, so they belong in a ParallelAgent. The gate
opens on send-eligibility (the engagement is qualified AND the send is eligible),
fail-closed — never on "the copy reads well."

The world-facing acts (send, publish) are deliberately NOT part of root_agent:
the pipeline halts at the gate, and the publish fires only after the founder's
tap-2 approval — see runner.publish / tools.channels. This is arivu's
"executor is not in root_agent" discipline applied to the mouth.
"""

from __future__ import annotations

from typing import AsyncGenerator

from google.adk.agents import (
    BaseAgent,
    ParallelAgent,
    SequentialAgent,
)
from google.adk.agents.invocation_context import InvocationContext
from google.adk.events import Event, EventActions

from . import grounding, sub_agents
from .state import StateKeys
from .tools import analyst
from .util import parse_json


# ─── Deterministic publish gate (no model — pure send-eligibility logic) ──────
class GateAgent(BaseAgent):
    """The publish gate (the HITL · tap 2). Opens on send-eligibility — the
    engagement is qualified AND the send is eligible (consented, within the value
    cap) — and HALTS. The pipeline ends here; the publish is a separate,
    human-approved step. When the engagement isn't qualified or the send isn't
    eligible, the gate is 'no_safe_message' and nothing is offered (fail-closed)."""

    async def _run_async_impl(
        self, ctx: InvocationContext
    ) -> AsyncGenerator[Event, None]:
        state = ctx.session.state
        qualify = state.get(StateKeys.QUALIFY, {})
        qualify = qualify if isinstance(qualify, dict) else parse_json(qualify)
        qualified = bool(qualify.get("worth_engaging", False))
        eligible, _reason = analyst.send_eligibility(
            recipient="consented-launch-list", consent=True, value_usd=0.0
        )
        status = "awaiting_approval" if (qualified and eligible) else "no_safe_message"
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
    return SequentialAgent(
        name="kural",
        description=(
            "kural — the company's only mouth. Qualifies the engagement, researches "
            "in parallel, and HALTS at the founder's publish sign-off before saying "
            "anything to the world. It authors nothing — it carries kalai's "
            "compliance-cleared master untouched."
        ),
        sub_agents=[coordinator, research, GateAgent(name="gate")],
    )


root_agent = build_root_agent()
