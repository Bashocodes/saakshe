"""kural — the mouth as ADK agents.

Seven seats. Two are Claude via Vertex (the high-stakes judgment seats), the rest
are Gemini routine intelligence:

  * Envoy Lead / Coordinator      — CLAUDE · the qualify decision, the spine entry
  * Prospect Scout, Market Watcher — Gemini · disjoint research, in a ParallelAgent
  * Outreach Writer               — Gemini · founder-voice, manas-grounded
  * Claim Judge                   — CLAUDE · the after_agent LLM-as-judge gate @0.8
  * Email Envoy (Sender), Channel Mouth (Publisher) — Gemini · the channel desk
    (driven by the runner's gate, NOT inside root_agent — see agent.py)

The two Claude seats are forced through an ADK ``output_schema`` (pydantic) so a
live reply can never collapse to prose → the deterministic gate reading
``claim_support=0.0`` → a permanent "no safe message". This is arivu's
VerdictSchema discipline applied to the two highest-stakes outputs of the mouth.

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
from .tools import analyst


# ─── Forced-shape schemas for the two Claude steps ───────────────────────────
class QualifySchema(BaseModel):
    worth_engaging: bool = Field(description="is this worth saying to the audience now")
    channel: str = Field(description="the channel(s) to engage on")
    as_voice: str = Field(description="whose voice — always the founder, plain and candid")
    rationale: str = Field(description="one sentence: why this is worth saying now")


class ClaimReportSchema(BaseModel):
    per_claim: list[dict] = Field(
        description="one entry per load-bearing claim: {claim, verdict, evidence}"
    )
    claim_support: float = Field(description="0.0-1.0 — fraction of claims actually grounded")
    verified: bool = Field(description="whether every load-bearing claim is supported")
    fix: str = Field(description="if not verified, the minimal claim to cut/re-ground; else ''")


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


# ─── Research fan-out (two disjoint Gemini scouts, in parallel) ───────────────
def _research_instruction(role: str, display: str, lens: str):
    def provider(ctx: ReadonlyContext) -> str:
        base = (
            prompts.RESEARCH_BASE
            .replace("{display}", display)
            .replace("{org}", _org_name(ctx))
            .replace("{lens}", lens)
        )
        steer = prompts.RESEARCH_LENS.get(role, "")
        return (
            base
            + f"\nLENS FOCUS: {steer}\n\n"
            + f"THE APPROVED DECISION (brief):\n{_brief(ctx)}\n\n"
            + f"THE ORG'S OWN GROUNDING:\n{_grounding_block(ctx)}\n"
        )

    return provider


def build_research_scouts() -> list[LlmAgent]:
    specs = [
        ("prospect", "Prospect Scout", "audience & consent", StateKeys.RESEARCH_PROSPECT,
         [analyst.audience_fit_tool]),
        ("market", "Market Watcher", "timing & feed", StateKeys.RESEARCH_MARKET,
         [analyst.timing_window_tool]),
    ]
    agents: list[LlmAgent] = []
    for role, display, lens, out_key, tools in specs:
        agents.append(
            LlmAgent(
                name=f"research_{role}",
                model=models.gemini_flash("kural", role),
                description=f"The {display} — {lens} lens (research fan-out).",
                instruction=_research_instruction(role, display, lens),
                tools=tools,
                output_key=out_key,
            )
        )
    return agents


# ─── Outreach Writer (Gemini, founder-voice, manas-grounded) ──────────────────
def _writer_instruction(ctx: ReadonlyContext) -> str:
    rnd = ctx.state.get(StateKeys.CLAIM_ROUND, 0)
    prospect = ctx.state.get(StateKeys.RESEARCH_PROSPECT, "")
    market = ctx.state.get(StateKeys.RESEARCH_MARKET, "")
    report = ctx.state.get(StateKeys.CLAIM_REPORT, "")
    rewrite = f"\n\nPRIOR CLAIM-JUDGE FEEDBACK (fix this):\n{report}\n" if rnd else ""
    return (
        prompts.WRITER.replace("{org}", _org_name(ctx))
        + f"\n\n[CLAIM_ROUND::{rnd}]\n\n"
        + f"THE APPROVED DECISION (brief):\n{_brief(ctx)}\n\n"
        + f"RESEARCH — audience:\n{prospect}\n\nRESEARCH — timing:\n{market}\n\n"
        + f"THE ORG'S OWN GROUNDING (manas Context Pack):\n{_grounding_block(ctx)}\n"
        + rewrite
    )


def build_writer() -> LlmAgent:
    return LlmAgent(
        name="outreach_writer",
        model=models.gemini_flash("kural", "writer"),
        description="The Outreach Writer — founder-voice copy, every claim grounded in manas.",
        instruction=_writer_instruction,
        output_key=StateKeys.DRAFT,
    )


# ─── Claim Judge (Claude · Vertex) — after_agent LLM-as-judge gate ────────────
def _claim_judge_instruction(ctx: ReadonlyContext) -> str:
    draft = ctx.state.get(StateKeys.DRAFT, "")
    rnd = ctx.state.get(StateKeys.CLAIM_ROUND, 0)
    return (
        prompts.CLAIM_JUDGE
        + f"\n\n[CLAIM_ROUND::{rnd}]\n\n"
        + f"THE DRAFT UNDER FACT-CHECK:\n{draft}\n\n"
        + f"THE ORG'S OWN GROUNDING (the only admissible evidence):\n{_grounding_block(ctx)}\n"
    )


def build_claim_judge() -> LlmAgent:
    return LlmAgent(
        name="claim_judge",
        model=models.claude("kural", "claim_judge"),
        description="Claude via Vertex — fact-checks every claim and scores claim_support.",
        instruction=_claim_judge_instruction,
        output_schema=ClaimReportSchema,
        output_key=StateKeys.CLAIM_REPORT,
    )
