"""arivu — the sabha as ADK agents.

Five disjoint Gemini mantris (genuine agents — disjoint lens, disjoint data, so
they cannot collapse into one prompt), a Gemini chair-orchestrator that frames
and grounds, a debate moderator, and the two Claude-via-Vertex high-stakes
agents: the chair-synthesizer (verdict) and the prosecutor.

Every dynamic instruction is an InstructionProvider callable so we build the
prompt from live state ourselves — no ADK brace-templating, JSON schemas safe.
"""

from __future__ import annotations

import json

from google.adk.agents import LlmAgent
from google.adk.agents.readonly_context import ReadonlyContext
from pydantic import BaseModel, Field

from . import config, models, prompts
from .tools import analyst, grounding


# ─── Forced-shape schemas for the two Claude steps ───────────────────────────
# The highest-stakes outputs are the verdict and the prosecution's defensibility.
# Constraining them with an ADK output_schema makes well-formed JSON the only
# possible output, so a live Claude reply can never collapse to prose → the
# prosecution check reading defensibility=0.0 → a permanent "no safe decision".
class VerdictSchema(BaseModel):
    decision: str = Field(description="one specific, executable decision")
    reasons: list[str] = Field(description="grounded reasons, with cited numbers")
    dissent: str = Field(description="the preserved minority position and who held it")
    confidence: float = Field(description="0.0-1.0")


class ProsecutionSchema(BaseModel):
    attack: str = Field(description="the strongest steelmanned case against the verdict")
    rebuttal: str = Field(description="whether/how the verdict answers the attack")
    defensibility: float = Field(description="0.0-1.0 — probability a board upholds it")
    survived: bool = Field(description="whether the verdict survives the attack")


def _org_name(ctx: ReadonlyContext) -> str:
    org = ctx.state.get(config.StateKeys.ORG) or config.DEFAULT_ORG
    return org.get("name", "the company") if isinstance(org, dict) else str(org)


def _question(ctx: ReadonlyContext) -> str:
    return ctx.state.get(config.StateKeys.QUESTION) or config.DEFAULT_QUESTION


def _grounding_block(ctx: ReadonlyContext) -> str:
    return ctx.state.get("grounding_text", "(grounding pending)")


# ─── Chair-orchestrator: frame + ground + decompose ──────────────────────────
def _frame_instruction(ctx: ReadonlyContext) -> str:
    return (
        prompts.CHAIR_FRAME.replace("{org}", _org_name(ctx))
        + f"\n\nFOUNDER'S QUESTION:\n{_question(ctx)}\n\n"
        + f"THE ORG'S OWN LIVE NUMBERS:\n{_grounding_block(ctx)}\n"
    )


def build_frame_agent() -> LlmAgent:
    return LlmAgent(
        name="chair_frame",
        model=models.gemini_pro(),
        description="The chair frames the loaded question and grounds it in the org's numbers.",
        instruction=_frame_instruction,
        output_key=config.StateKeys.SUBQUESTIONS,
        before_agent_callback=grounding.ground_callback,
    )


# ─── The five mantris ────────────────────────────────────────────────────────
def _mantri_instruction(role: str, display: str, lens: str):
    def provider(ctx: ReadonlyContext) -> str:
        base = (
            prompts.MANTRI_BASE
            .replace("{display}", display)
            .replace("{org}", _org_name(ctx))
            .replace("{lens}", lens)
        )
        steer = prompts.MANTRI_LENS.get(role, "")
        return (
            base
            + f"\nLENS FOCUS: {steer}\n\n"
            + f"THE QUESTION:\n{_question(ctx)}\n\n"
            + f"THE ORG'S OWN LIVE NUMBERS:\n{_grounding_block(ctx)}\n"
        )

    return provider


def build_mantris() -> list[LlmAgent]:
    agents: list[LlmAgent] = []
    extra_tools = {
        "economist": [analyst.elasticity_tool],
        "risk": [analyst.scenario_stress_tool],
    }
    live_mcp = grounding.example_mcp_toolset() if config.is_live() else None
    for role, display, state_key, lens in config.MANTRIS:
        tools = list(extra_tools.get(role, []))
        if live_mcp is not None:
            tools.append(live_mcp)
        agents.append(
            LlmAgent(
                name=f"mantri_{role}",
                model=models.gemini_flash(role),
                description=f"The {display} mantri — {lens} lens.",
                instruction=_mantri_instruction(role, display, lens),
                tools=tools,
                output_key=state_key,
            )
        )
    return agents


# ─── Debate moderator ────────────────────────────────────────────────────────
def _debate_instruction(ctx: ReadonlyContext) -> str:
    positions = analyst.read_positions(ctx.state)
    return (
        prompts.DEBATE_MODERATOR
        + "\n\nPOSITIONS:\n"
        + json.dumps(positions, indent=2)
    )


def build_debate_moderator() -> LlmAgent:
    return LlmAgent(
        name="debate_moderator",
        model=models.gemini_flash("debate"),
        description="Moderates one round of cross-rebuttal in the debate loop.",
        instruction=_debate_instruction,
        output_key=config.StateKeys.DEBATE_TRANSCRIPT,
    )


# ─── Chair-synthesizer (Claude · Vertex) ─────────────────────────────────────
def _synthesis_instruction(ctx: ReadonlyContext) -> str:
    positions = analyst.read_positions(ctx.state)
    debate = ctx.state.get(config.StateKeys.DEBATE_TRANSCRIPT, "")
    return (
        prompts.CHAIR_SYNTHESIS
        + f"\n\nQUESTION:\n{_question(ctx)}\n\n"
        + f"SURVIVING POSITIONS:\n{json.dumps(positions, indent=2)}\n\n"
        + f"DEBATE SUMMARY:\n{debate}\n"
    )


def build_chair_synthesizer() -> LlmAgent:
    return LlmAgent(
        name="chair_synthesizer",
        model=models.claude_verdict(),
        description="Claude via Vertex — reconciles positions into one verdict.",
        instruction=_synthesis_instruction,
        output_schema=VerdictSchema,
        output_key=config.StateKeys.VERDICT,
    )


# ─── Prosecutor (Claude · Vertex) ────────────────────────────────────────────
def _prosecutor_instruction(ctx: ReadonlyContext) -> str:
    verdict = ctx.state.get(config.StateKeys.VERDICT, {})
    if not isinstance(verdict, dict):
        from .util import parse_json

        verdict = parse_json(verdict)
    rnd = ctx.state.get(config.StateKeys.PROSECUTION_ROUND, 0)
    return (
        prompts.PROSECUTOR
        + f"\n\n[PROSECUTION_ROUND::{rnd}]\n\n"
        + f"THE VERDICT UNDER PROSECUTION:\n{json.dumps(verdict, indent=2)}\n\n"
        + f"THE ORG'S OWN LIVE NUMBERS:\n{_grounding_block(ctx)}\n"
    )


def build_prosecutor() -> LlmAgent:
    return LlmAgent(
        name="prosecutor",
        model=models.claude_prosecutor(),
        description="Claude via Vertex — steelmans the null case and tries to defeat the verdict.",
        instruction=_prosecutor_instruction,
        output_schema=ProsecutionSchema,
        output_key=config.StateKeys.PROSECUTION,
    )
