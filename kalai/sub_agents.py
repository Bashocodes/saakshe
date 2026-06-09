"""kalai — the studio as ADK agents.

A Claude-via-Vertex Creative Director (coordinator + taste), two disjoint Gemini
production seats that run in PARALLEL (Designer/Producer + Copy & SEO), a Gemini
Brand-Fidelity scorer that runs IN the loop, and a second Claude-via-Vertex seat:
the fail-closed Compliance gate.

Exactly two Claude seats (director + compliance); everything else Gemini. The two
Claude outputs are forced into a pydantic ``output_schema`` (like arivu's
VerdictSchema) so a live reply can never collapse to prose and silently defeat the
deterministic loop/gate logic.

Every dynamic instruction is an InstructionProvider callable so we build the prompt
from live state ourselves — no ADK brace-templating, JSON-schema examples stay safe.
"""

from __future__ import annotations

import json

from google.adk.agents import LlmAgent
from google.adk.agents.readonly_context import ReadonlyContext
from pydantic import BaseModel, Field

from common import config, models
from . import prompts
from .state import NS, PRODUCERS, StateKeys
from .tools import analyst
from .util import brand_block, parse_json


# ─── Forced-shape schemas for the two Claude seats ───────────────────────────
class CreativeFrameSchema(BaseModel):
    concept: str = Field(description="one clear creative concept for the launch master")
    brand_guardrails: list[str] = Field(description="hard brand rules the desks must honour")
    platforms: list[str] = Field(description="target platforms, e.g. x / ig / linkedin")


class ComplianceSchema(BaseModel):
    compliance: str = Field(description="'cleared' or 'blocked' — fail-closed")
    checks: dict = Field(description="per-area verdicts: claims/rights/tone/sensitive")
    reasons: list[str] = Field(description="why, especially if blocked")


def _org_name(ctx: ReadonlyContext) -> str:
    org = ctx.state.get("org") or {}
    return org.get("name", "the company") if isinstance(org, dict) else str(org)


def _brief(ctx: ReadonlyContext) -> str:
    return ctx.state.get(StateKeys.BRIEF) or ""


def _brand(ctx: ReadonlyContext) -> str:
    return ctx.state.get(StateKeys.BRAND_BLOCK, "(brand canon pending)")


def render_brand_block(assets) -> str:
    """Render the served vault assets into the designer's brand-asset-bank text.
    Empty/None -> "" so the prompt is byte-identical to the pre-vault path."""
    assets = assets or []
    if not assets:
        return ""
    lines = ["BRAND ASSETS ON FILE (use these — they are the company's real marks):"]
    for a in assets:
        lines.append(
            f"  - {a.get('kind')}: {a.get('filename')} ({a.get('uri')}) — from {a.get('provenance', '')}"
        )
    return "\n".join(lines)


# ─── before-agent callback: seed the studio's deterministic state ────────────
def prime_studio(callback_context):
    """before_agent_callback on the Creative Director: render the brand asset bank
    from the Context Pack and zero the loop counters. Mirrors arivu's
    grounding.ground_callback so the studio starts every run clean."""
    state = callback_context.state
    pack = state.get(StateKeys.CONTEXT_PACK)
    state[StateKeys.BRAND_BLOCK] = brand_block(pack if isinstance(pack, dict) else {})
    state[StateKeys.FIDELITY_ROUND] = 0
    state.setdefault(StateKeys.TRANSCRIPT, [])
    return None  # do not skip the agent


# ─── Creative Director (Claude · Vertex — seat 1 of 2) ───────────────────────
def _director_instruction(ctx: ReadonlyContext) -> str:
    return (
        prompts.CREATIVE_DIRECTOR.replace("{org}", _org_name(ctx))
        + f"\n\nAPPROVED BRIEF:\n{_brief(ctx)}\n\n"
        + f"BRAND ASSET BANK (manas canon):\n{_brand(ctx)}\n"
    )


def build_creative_director() -> LlmAgent:
    return LlmAgent(
        name="creative_director",
        model=models.claude(NS, "director"),     # CLAUDE seat #1
        description="Claude via Vertex — frames the concept + brand guardrails for the desks.",
        instruction=_director_instruction,
        output_schema=CreativeFrameSchema,        # no tools alongside output_schema
        output_key=StateKeys.CREATIVE_FRAME,
        before_agent_callback=prime_studio,
    )


# ─── Parallel production desk (Gemini) ───────────────────────────────────────
def _frame_block(ctx: ReadonlyContext) -> str:
    frame = ctx.state.get(StateKeys.CREATIVE_FRAME, {})
    if not isinstance(frame, dict):
        frame = parse_json(frame)
    return json.dumps(frame, indent=2)


def _producer_instruction(role: str):
    body = prompts.DESIGNER if role == "designer" else prompts.COPY_SEO

    def provider(ctx: ReadonlyContext) -> str:
        prompt = (
            body.replace("{org}", _org_name(ctx))
            + f"\n\nCREATIVE DIRECTOR'S FRAME:\n{_frame_block(ctx)}\n\n"
            + f"BRAND ASSET BANK (manas canon):\n{_brand(ctx)}\n"
        )
        # Ground the Designer on the SERVED vault assets — but ONLY when manas
        # actually served some. Empty/demo -> render_brand_block("") -> zero chars
        # appended -> the designer prompt is byte-for-byte the pre-vault path.
        if role == "designer":
            served = render_brand_block(ctx.state.get(StateKeys.ASSETS))
            if served:
                prompt = prompt + "\n" + served + "\n"
        return prompt

    return provider


def build_producers() -> list[LlmAgent]:
    agents: list[LlmAgent] = []
    for role, display, state_key, lane in PRODUCERS:
        agents.append(
            LlmAgent(
                name=f"producer_{role}",
                model=models.gemini_flash(NS, role),
                description=f"The {display} desk — {lane}.",
                instruction=_producer_instruction(role),
                output_key=state_key,
            )
        )
    return agents


# ─── Brand-Fidelity panel (Gemini · in the loop) ─────────────────────────────
# The single Brand-Fidelity scorer is replaced by a 4-seat ParallelAgent panel
# (brand · voice · platform · compliance) + a deterministic aggregate reducer —
# see ``kalai/scorers.py`` (build_scorer_panel) and ``kalai/agent.py``
# (ScorerReducer). The panel is kalai's chamber for the deciding question
# "is it on-brand + cleared?"; the loop exit stays owned by the checker.


# ─── Compliance gate (Claude · Vertex — seat 2 of 2, FAIL-CLOSED) ────────────
def _compliance_instruction(ctx: ReadonlyContext) -> str:
    design = ctx.state.get(StateKeys.DESIGN, {})
    copy = ctx.state.get(StateKeys.COPY, {})
    if not isinstance(design, dict):
        design = parse_json(design)
    if not isinstance(copy, dict):
        copy = parse_json(copy)
    brief = _brief(ctx)
    return (
        prompts.COMPLIANCE.replace("{org}", _org_name(ctx))
        # Marker the demo resolver reads to gate the canned verdict on the brief.
        + f"\n\n[BRIEF::{brief}::BRIEF]\n\n"
        + f"BRIEF:\n{brief}\n\n"
        + f"FINISHED MASTER — DESIGN:\n{json.dumps(design, indent=2)}\n\n"
        + f"FINISHED MASTER — COPY:\n{json.dumps(copy, indent=2)}\n"
    )


def build_compliance_gate() -> LlmAgent:
    return LlmAgent(
        name="compliance_gate",
        model=models.claude(NS, "compliance"),    # CLAUDE seat #2
        description="Claude via Vertex — fail-closed compliance review; blocks unless cleared.",
        instruction=_compliance_instruction,
        output_schema=ComplianceSchema,            # no tools alongside output_schema
        output_key=StateKeys.COMPLIANCE,
    )
