"""kural — the delivery chamber (4 deep readers + the delivery planner).

After the separation fix kural authors NOTHING. The delivery chamber decides the
ONE thing the mouth owns: HOW to carry kalai's cleared master out — to whom
(segment), when (window), and which pre-authored variant. It never writes a word:
the planner PICKS a variant; a deterministic assembler copies kalai's
``formats[variant]`` VERBATIM into the plan, so the carried text is kalai's,
byte-for-byte (the planner's schema has no ``text`` field — it cannot author).

Four disjoint Gemini readers (consent · reach · topic-fit · timing) fan out in
parallel — the kural-arivu panel, each citing the org's own grounding — then a
Claude delivery planner selects variant × segment × window from their findings.
This is the arivu mantri-ensemble shape applied to delivery: many specialized,
cited reads → one decision, fail-closed.
"""

from __future__ import annotations

import json
from typing import AsyncGenerator

from google.adk.agents import BaseAgent, LlmAgent, ParallelAgent
from google.adk.agents.invocation_context import InvocationContext
from google.adk.agents.readonly_context import ReadonlyContext
from google.adk.events import Event, EventActions
from pydantic import BaseModel, Field

from common import models

from . import prompts
from .state import StateKeys
from .util import parse_json

# The four delivery readers — disjoint lenses, in parallel (the kural panel).
# (role, display, lens, output_key)
DELIVERY_READERS = [
    ("consent", "Consent Reader", "consent & permission", StateKeys.DELIVERY_CONSENT),
    ("reach", "Reach Reader", "reachable audience size", StateKeys.DELIVERY_REACH),
    ("topic_fit", "Topic-fit Reader", "topic match", StateKeys.DELIVERY_TOPIC),
    ("timing", "Timing Reader", "open window", StateKeys.DELIVERY_TIMING),
]


class DeliveryPickSchema(BaseModel):
    """The planner PICKS — it never authors. No ``text`` field by construction, so
    a live Claude reply structurally cannot smuggle in new copy."""

    variant: str = Field(description="which pre-authored channel variant to carry: x | ig | linkedin")
    segment: str = Field(description="the consented, topic-fit slice to send to")
    window: str = Field(description="when to publish — the open window")
    rationale: str = Field(description="one sentence: why this variant/segment/window")


def _org_name(ctx: ReadonlyContext) -> str:
    org = ctx.state.get(StateKeys.ORG) or {}
    return org.get("name", "the company") if isinstance(org, dict) else str(org)


def _grounding_block(ctx: ReadonlyContext) -> str:
    return ctx.state.get("grounding_text", "(grounding pending)")


def _master_formats(state) -> dict:
    master = state.get(StateKeys.MASTER) or {}
    fmts = master.get("formats", {}) if isinstance(master, dict) else {}
    return fmts if isinstance(fmts, dict) else {}


# ─── The four deep readers (Gemini · disjoint lenses, in parallel) ────────────
def _reader_instruction(role: str, display: str, lens: str):
    def provider(ctx: ReadonlyContext) -> str:
        base = (
            prompts.DELIVERY_READER_BASE
            .replace("{display}", display)
            .replace("{org}", _org_name(ctx))
            .replace("{lens}", lens)
        )
        steer = prompts.DELIVERY_READER_LENS.get(role, "")
        return (
            base
            + f"\nLENS FOCUS: {steer}\n\n"
            + f"THE ORG'S OWN GROUNDING:\n{_grounding_block(ctx)}\n"
        )

    return provider


def build_delivery_readers() -> list[LlmAgent]:
    agents: list[LlmAgent] = []
    for role, display, lens, out_key in DELIVERY_READERS:
        agents.append(
            LlmAgent(
                name=f"delivery_{role}",
                model=models.gemini_flash("kural", role),
                description=f"The {display} — {lens} lens (delivery fan-out).",
                instruction=_reader_instruction(role, display, lens),
                output_key=out_key,
            )
        )
    return agents


# ─── The delivery planner (Claude) — picks variant × segment × window ─────────
def _readers_block(ctx: ReadonlyContext) -> str:
    out: dict = {}
    for role, _display, _lens, key in DELIVERY_READERS:
        d = ctx.state.get(key)
        out[role] = d if isinstance(d, dict) else parse_json(d)
    return json.dumps(out, indent=2)


def _planner_instruction(ctx: ReadonlyContext) -> str:
    fmts = _master_formats(ctx.state)
    return (
        prompts.DELIVERY_PLANNER.replace("{org}", _org_name(ctx))
        + "\n\nTHE PRE-AUTHORED VARIANTS YOU MAY CHOOSE FROM (kalai's — do NOT edit):\n"
        + json.dumps(list(fmts.keys()))
        + f"\n\nWHAT THE READERS FOUND:\n{_readers_block(ctx)}\n\n"
        + f"THE ORG'S OWN GROUNDING:\n{_grounding_block(ctx)}\n"
    )


def build_delivery_planner() -> LlmAgent:
    return LlmAgent(
        name="delivery_planner",
        model=models.claude("kural", "delivery_planner"),
        description="Claude via Vertex — picks variant × segment × window from the readers. Authors NOTHING.",
        instruction=_planner_instruction,
        output_schema=DeliveryPickSchema,
        output_key=StateKeys.DELIVERY_PICK,
    )


class DeliveryAssembler(BaseAgent):
    """Deterministically assemble the delivery plan: copy kalai's chosen variant
    VERBATIM. The planner picked a variant; this guarantees the carried text is
    kalai's ``formats[variant]`` byte-for-byte — kural authors nothing, ever."""

    async def _run_async_impl(
        self, ctx: InvocationContext
    ) -> AsyncGenerator[Event, None]:
        state = ctx.session.state
        pick = state.get(StateKeys.DELIVERY_PICK, {})
        pick = pick if isinstance(pick, dict) else parse_json(pick)
        formats = _master_formats(state)
        variant = pick.get("variant", "")
        if variant not in formats:
            # Fail-closed to a real, pre-authored variant — never invent text.
            variant = next(iter(formats), "")
        plan = {
            "variant": variant,
            "segment": pick.get("segment", "the consented, topic-fit slice"),
            "window": pick.get("window", "the open window"),
            "text": formats.get(variant, ""),     # kalai's words, VERBATIM
            "rationale": pick.get("rationale", ""),
            "carries_kalai_words": True,
        }
        delta = {StateKeys.DELIVERY_PLAN: plan}
        state.update(delta)
        yield Event(author=self.name, actions=EventActions(state_delta=delta))
