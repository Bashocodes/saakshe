"""kural — the assembled mouth. Exports ``root_agent``.

The ONE earned engagement pipeline (after the separation fix):

    envoy_lead (Claude · Vertex · qualify + spine entry, grounds)
      → ParallelAgent: delivery fan-out (consent · reach · topic-fit · timing, Gemini)
      → outreach_writer (Gemini · authors the copy) → claim_judge (Claude · fact-checks)
      → delivery_planner (Claude · PICKS variant×segment×window) → assembler
      → gate (HALTS — the publish sign-off is the founder's tap 2, NOT auto)

kalai is media-only; kural AUTHORS all copy. The Outreach Writer drafts the caption
+ every channel variant in the founder's voice, the Claim Judge fact-checks every
claim, and the planner then PICKS how to carry it out — qualifying the engagement
and reading audience/timing in parallel before it HALTS at the publish gate. One
company, one mouth, one author of the words.

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

from . import delivery, grounding, sub_agents
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

    readers = ParallelAgent(
        name="delivery_fanout",
        description="Four disjoint delivery readers (consent · reach · topic-fit · timing) in parallel — the kural panel.",
        sub_agents=delivery.build_delivery_readers(),
    )
    seats = [coordinator, readers]
    # kalai is media-only — kural AUTHORS the words. The Outreach Writer drafts the
    # copy and the Claim Judge fact-checks it BEFORE the planner picks how to carry
    # it out.
    seats.append(sub_agents.build_outreach_writer())
    seats.append(sub_agents.build_claim_judge())
    seats.append(delivery.build_delivery_planner())
    seats.append(delivery.DeliveryAssembler(name="delivery_assembler"))
    seats.append(GateAgent(name="gate"))
    return SequentialAgent(
        name="kural",
        description=(
            "kural — the company's only mouth. Qualifies the engagement, reads the "
            "delivery facts in parallel (consent · reach · topic-fit · timing), a "
            "planner PICKS variant × segment × window, and it HALTS at the founder's "
            "publish sign-off before saying anything to the world."
        ),
        sub_agents=seats,
    )


root_agent = build_root_agent()
