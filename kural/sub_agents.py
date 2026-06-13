"""kural — the mouth as ADK agents.

The seats (after the separation fix — kural authors nothing):

  * Envoy Lead / Coordinator      — CLAUDE · the qualify decision, the spine entry
  * Prospect Scout, Market Watcher — Gemini · disjoint research, in a ParallelAgent
  * Email Envoy (Sender), Channel Mouth (Publisher) — Gemini · the channel desk
    (driven by the runner's gate, NOT inside root_agent — see agent.py)

The old Outreach Writer + Claim Judge are retired: kalai owns all copy (caption +
every channel variant, fact-checked in its own fidelity loop), and kural carries
that cleared master untouched. One company, one author.

The Claude qualify seat is forced through an ADK ``output_schema`` (pydantic) so a
live reply can never collapse to prose. This is arivu's VerdictSchema discipline
applied to the highest-stakes output of the mouth.

Every dynamic instruction is an InstructionProvider callable so we build the
prompt from live state ourselves — no ADK brace-templating, JSON schemas safe.
"""

from __future__ import annotations

import json

from google.adk.agents import LlmAgent
from google.adk.agents.readonly_context import ReadonlyContext
from pydantic import BaseModel, Field

from common import config, models

from . import prompts
from .state import StateKeys


# ─── Forced-shape schemas for the two Claude steps ───────────────────────────
class QualifySchema(BaseModel):
    worth_engaging: bool = Field(description="is this worth saying to the audience now")
    channel: str = Field(description="the channel(s) to engage on")
    as_voice: str = Field(description="whose voice — always the founder, plain and candid")
    rationale: str = Field(description="one sentence: why this is worth saying now")


# ─── small state readers ──────────────────────────────────────────────────────
def _org_name(ctx: ReadonlyContext) -> str:
    org = ctx.state.get(StateKeys.ORG) or {}
    return org.get("name", "the company") if isinstance(org, dict) else str(org)


def _grounding_block(ctx: ReadonlyContext) -> str:
    return ctx.state.get("grounding_text", "(grounding pending)")


def _brief(ctx: ReadonlyContext) -> str:
    return ctx.state.get(StateKeys.BRIEF) or "(no brief)"


def _master_block(ctx: ReadonlyContext) -> str:
    master = ctx.state.get(StateKeys.MASTER) or {}
    return json.dumps(master, indent=2) if master else "(no creative master)"


# ─── Envoy Lead / Coordinator (Claude · Vertex) — qualify ─────────────────────
def _coordinator_instruction(ctx: ReadonlyContext) -> str:
    return (
        prompts.COORDINATOR.replace("{org}", _org_name(ctx))
        + f"\n\nTHE APPROVED DECISION (brief):\n{_brief(ctx)}\n\n"
        + f"KALAI'S COMPLIANCE-CLEARED MASTER:\n{_master_block(ctx)}\n\n"
        + f"THE ORG'S OWN GROUNDING (manas Context Pack + funnel):\n{_grounding_block(ctx)}\n"
    )


def build_coordinator() -> LlmAgent:
    return LlmAgent(
        name="envoy_lead",
        model=models.claude("kural", "coordinator"),
        description="Claude via Vertex — the Envoy Lead qualifies the engagement and enters the spine.",
        instruction=_coordinator_instruction,
        output_schema=QualifySchema,
        output_key=StateKeys.QUALIFY,
    )

# The research fan-out (Prospect Scout + Market Watcher) was replaced in Phase 4 by
# the four deep delivery readers (consent · reach · topic-fit · timing) — see
# kural/delivery.py. kural still authors nothing; the readers feed the planner.


# ─── faculty-v2: kural AUTHORS the words (Outreach Writer + Claim Judge) ───────
# kalai is media-only now; the WORD faculty writes the copy and a Claim Judge
# proves every claim before the gate. Both seats are gated into the graph only
# under SAAKSHE_FACULTY_V2 (see agent.build_root_agent); v1 stays authoring-free.
class OutreachDraftSchema(BaseModel):
    caption: str = Field(description="the one caption — the founder's plain, candid line")
    x: str = Field(description="the X variant")
    ig: str = Field(description="the Instagram variant")
    linkedin: str = Field(description="the LinkedIn variant")


class ClaimJudgeSchema(BaseModel):
    claim_support: float = Field(description="0.0–1.0 — the fraction of claims the grounding supports")
    reasons: list[str] = Field(description="one line per claim: grounded by … / UNSUPPORTED")


def _draft_block(ctx: ReadonlyContext) -> str:
    draft = ctx.state.get(StateKeys.DRAFT) or {}
    return json.dumps(draft, indent=2) if draft else "(no draft yet)"


def _writer_instruction(ctx: ReadonlyContext) -> str:
    return (
        prompts.OUTREACH_WRITER.replace("{org}", _org_name(ctx))
        + f"\n\nTHE APPROVED DECISION (brief):\n{_brief(ctx)}\n\n"
        + f"KALAI'S CREATIVE (media — pair your words to it; do NOT describe it):\n{_master_block(ctx)}\n\n"
        + f"THE ORG'S OWN GROUNDING (manas Context Pack + funnel):\n{_grounding_block(ctx)}\n"
    )


def build_outreach_writer() -> LlmAgent:
    return LlmAgent(
        name="outreach_writer",
        model=models.gemini_flash("kural", "outreach_writer"),
        description="Gemini — writes the caption + per-channel copy in the founder's voice (faculty-v2).",
        instruction=_writer_instruction,
        output_schema=OutreachDraftSchema,
        output_key=StateKeys.DRAFT,
    )


def _judge_instruction(ctx: ReadonlyContext) -> str:
    return (
        prompts.CLAIM_JUDGE.replace("{org}", _org_name(ctx))
        + f"\n\nTHE APPROVED DECISION (brief):\n{_brief(ctx)}\n\n"
        + f"THE OUTREACH WRITER'S DRAFT (judge every claim in it):\n{_draft_block(ctx)}\n\n"
        + f"THE ORG'S OWN GROUNDING (the only evidence a claim may rest on):\n{_grounding_block(ctx)}\n"
    )


def build_claim_judge() -> LlmAgent:
    return LlmAgent(
        name="claim_judge",
        model=models.claude("kural", "claim_judge"),
        description="Claude via Vertex — fact-checks the authored words; every claim must be grounded (faculty-v2).",
        instruction=_judge_instruction,
        output_schema=ClaimJudgeSchema,
        output_key=StateKeys.CLAIM,
    )
