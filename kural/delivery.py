"""kural — the delivery chamber (4 deep readers + the delivery planner).

kural AUTHORS the copy (the Outreach Writer's draft); the delivery chamber decides
the OTHER thing the mouth owns: HOW to carry that copy out — to whom (segment), when
(window), and which authored variant. The planner never writes a word: it PICKS a
variant; a deterministic assembler copies the chosen ``DRAFT[variant]`` VERBATIM
into the plan (the planner's schema has no ``text`` field — it cannot author). When
no draft exists yet it falls back to kalai's ``formats[variant]``, fail-closed.

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

from common import config, models

from . import prompts
from .state import StateKeys
from .tools import analyst
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


def _carried_formats(state) -> dict:
    """The per-channel variants the mouth carries: kural's OWN authored draft (the
    Outreach Writer's StateKeys.DRAFT, channel keys only). Falls back to kalai's
    master formats if no draft exists yet (fail-closed — never invents text)."""
    draft = state.get(StateKeys.DRAFT) or {}
    draft = draft if isinstance(draft, dict) else parse_json(draft)
    variants = {k: v for k, v in draft.items() if k in ("x", "ig", "linkedin")}
    if variants:
        return variants
    return _master_formats(state)


# ─── Live read-tools over the org's own funnel/feed (Phase 4.3) ───────────────
# Each reader holds a read-tool to compute over the org's REAL list/consent/feed
# numbers — audience-fit for the audience lenses, the timing window for the feed.
# Attached ONLY in live (like arivu's mantri MCP tools): demo readers stay
# tool-free, so the scripted replay + the demo-published-output byte-identical
# contract hold. In live the reader reads the org's own funnel (grounded by 4.1).
_READER_TOOLS = {
    "consent": [analyst.audience_fit_tool],
    "reach": [analyst.audience_fit_tool],
    "topic_fit": [analyst.audience_fit_tool],
    "timing": [analyst.timing_window_tool],
}


def read_tools_for(role: str) -> list:
    """The live read-tools a delivery reader holds over the org's funnel/feed.

    Empty in demo (scripted readers cite the seed bundle; no tool fires) so demo
    stays byte-identical; in live the reader can read the org's own
    list/consent/topic-fit (audience_fit) or feed timing (timing_window)."""
    return list(_READER_TOOLS.get(role, [])) if config.is_live() else []


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
                tools=read_tools_for(role),   # live: read the org's own funnel/feed
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
    fmts = _carried_formats(ctx.state)
    return (
        prompts.DELIVERY_PLANNER.replace("{org}", _org_name(ctx))
        + "\n\nTHE PRE-AUTHORED VARIANTS YOU MAY CHOOSE FROM (do NOT edit the words):\n"
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
    """Deterministically assemble the delivery plan: copy the chosen variant
    VERBATIM. The planner picked a variant; this guarantees the carried text is the
    authored ``DRAFT[variant]`` byte-for-byte (kalai's ``formats[variant]`` as the
    fail-closed fallback) — the planner authors nothing, ever."""

    async def _run_async_impl(
        self, ctx: InvocationContext
    ) -> AsyncGenerator[Event, None]:
        state = ctx.session.state
        pick = state.get(StateKeys.DELIVERY_PICK, {})
        pick = pick if isinstance(pick, dict) else parse_json(pick)
        formats = _carried_formats(state)
        variant = pick.get("variant", "")
        if variant not in formats:
            # Fail-closed to a real, pre-authored variant — never invent text.
            variant = next(iter(formats), "")
        # When kural authored a draft, the carried text is kural's OWN words
        # (authored); otherwise it falls back to kalai's master formats verbatim.
        authored = bool(state.get(StateKeys.DRAFT))
        plan = {
            "variant": variant,
            "segment": pick.get("segment", "the consented, topic-fit slice"),
            "window": pick.get("window", "the open window"),
            "text": formats.get(variant, ""),
            "rationale": pick.get("rationale", ""),
            "carries_kalai_words": not authored,
        }
        if authored:
            plan["authored_by"] = "kural"
        delta = {StateKeys.DELIVERY_PLAN: plan}
        state.update(delta)
        yield Event(author=self.name, actions=EventActions(state_delta=delta))
