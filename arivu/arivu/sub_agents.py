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
from typing import AsyncGenerator

from google.adk.agents import BaseAgent, LlmAgent, ParallelAgent, SequentialAgent
from google.adk.agents.invocation_context import InvocationContext
from google.adk.agents.readonly_context import ReadonlyContext
from google.adk.events import Event, EventActions
from pydantic import BaseModel, Field

from . import config, models, prompts
from .tools import analyst, grounding
from .util import parse_json


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
    faulted_reason_index: int = Field(
        default=-1,
        description="0-based index of the verdict reason the attack targets, or -1 if none/survived",
    )


class RevisionSchema(BaseModel):
    """The graduated reviser's output: strengthen ONE faulted reason (2b.2)."""

    target_reason_index: int = Field(description="0-based index of the faulted reason, or -1 if none")
    revised_reason: str = Field(description="the strengthened, grounded reason (empty if none)")
    note: str = Field(description="one line on how the strengthening answers the attack")


def _org_name(ctx: ReadonlyContext) -> str:
    org = ctx.state.get(config.StateKeys.ORG) or config.DEFAULT_ORG
    return org.get("name", "the company") if isinstance(org, dict) else str(org)


def _question(ctx: ReadonlyContext) -> str:
    return ctx.state.get(config.StateKeys.QUESTION) or config.DEFAULT_QUESTION


def _grounding_block(ctx: ReadonlyContext) -> str:
    return ctx.state.get("grounding_text", "(grounding pending)")


def _grounding_section(ctx: ReadonlyContext) -> str:
    """The grounding block with HONEST provenance: 'live numbers' only when a
    live source actually resolved at frame time; the seed fallback says so."""
    label = ("THE ORG'S OWN LIVE NUMBERS" if ctx.state.get("grounding_live")
             else "GROUNDING BASELINE (seed bundle — not live numbers)")
    return f"{label}:\n{_grounding_block(ctx)}\n"


# ─── Chair-orchestrator: frame + ground + decompose ──────────────────────────
def _frame_instruction(ctx: ReadonlyContext) -> str:
    return (
        prompts.CHAIR_FRAME.replace("{org}", _org_name(ctx))
        + f"\n\nFOUNDER'S QUESTION:\n{_question(ctx)}\n\n"
        + _grounding_section(ctx)
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


# ─── The five mantris — each fans into a 3-advisor ensemble (2b.1) ────────────
# A mantri is no longer a lone advisor. Each is a SequentialAgent of:
#   ParallelAgent([three disjoint sub-advisors])  → a deterministic reducer.
# The three sub-advisors argue disjoint sub-lenses in parallel (anti-groupthink
# WITHIN the lens) and write disjoint sub-keys; the reducer folds them into the
# SAME consolidated POS_* position the chamber already reads — now carrying a
# cited `evidence` list. The consolidated claim/confidence/stance are lifted
# verbatim from the PRIMARY sub-advisor, so the rolled-up position stays
# byte-identical to today's _POSITIONS[role] (the original four tests pin this).

# Extra deterministic tools belong to the sub-lens that reasons over them.
_SUBLENS_TOOLS = {
    "economist__margin": ["elasticity_tool"],
    "economist__retention": ["elasticity_tool"],
    "risk__churn_cliff": ["scenario_stress_tool"],
}
_TOOLS = {
    "elasticity_tool": analyst.elasticity_tool,
    "scenario_stress_tool": analyst.scenario_stress_tool,
}


def _subadvisor_instruction(role: str, sub_role: str, display: str, lens: str, sub_display: str):
    def provider(ctx: ReadonlyContext) -> str:
        base = (
            prompts.SUBADVISOR_BASE
            .replace("{sub_display}", sub_display)
            .replace("{display}", display)
            .replace("{org}", _org_name(ctx))
            .replace("{lens}", lens)
        )
        steer = prompts.MANTRI_SUBLENS.get(sub_role, prompts.MANTRI_LENS.get(role, ""))
        return (
            base
            + f"\nSUB-LENS FOCUS: {steer}\n\n"
            + f"THE QUESTION:\n{_question(ctx)}\n\n"
            + _grounding_section(ctx)
        )

    return provider


def _sub_state_key(state_key: str, sub: str) -> str:
    """The disjoint sub-key a sub-advisor writes (e.g. pos_economist__margin)."""
    return f"{state_key}__{sub}"


class MantriReducer(BaseAgent):
    """Deterministically fold three disjoint sub-claims into the lens's
    consolidated POS_* position. No model — pure assembly, so the rolled-up
    claim/confidence/stance stay byte-identical to today's _POSITIONS[role]
    while the position gains a cited `evidence` list of >= 3 sub-claims."""

    role: str
    display: str
    lens: str
    state_key: str
    sub_keys: list[str]
    primary_sub: str

    async def _run_async_impl(
        self, ctx: InvocationContext
    ) -> AsyncGenerator[Event, None]:
        state = ctx.session.state
        evidence: list[dict] = []
        primary: dict = {}
        for sub, sub_key in zip(
            [s for s, _d in config.MANTRI_ENSEMBLES[self.role]], self.sub_keys
        ):
            raw = state.get(sub_key)
            d = raw if isinstance(raw, dict) else parse_json(raw)
            entry = {
                "sub_lens": d.get("sub_lens", sub),
                "claim": d.get("claim", ""),
                "source": d.get("source", d.get("citation", "")),
                "confidence": d.get("confidence"),
            }
            evidence.append(entry)
            if sub == self.primary_sub:
                primary = d

        # The consolidated position: claim/confidence/stance/citation lifted
        # verbatim from the primary sub-advisor (byte-identical roll-up), plus
        # the disjoint sub-claims as cited evidence.
        consolidated = {
            "lens": primary.get("lens", self.lens),
            "claim": primary.get("claim", ""),
            "citation": primary.get("citation", primary.get("source", "")),
            "confidence": primary.get("confidence"),
            "stance": primary.get("stance"),
            "evidence": evidence,
        }
        delta = {self.state_key: consolidated}
        state.update(delta)
        yield Event(author=self.name, actions=EventActions(state_delta=delta))


def build_mantri_ensemble(role: str, display: str, state_key: str, lens: str) -> SequentialAgent:
    """One mantri as a 3-advisor parallel ensemble + a deterministic reducer."""
    live_mcp = grounding.example_mcp_toolset() if config.is_live() else None
    subs: list[LlmAgent] = []
    sub_keys: list[str] = []
    for sub, sub_display in config.MANTRI_ENSEMBLES[role]:
        sub_role = f"{role}__{sub}"
        tools = [_TOOLS[t] for t in _SUBLENS_TOOLS.get(sub_role, [])]
        if live_mcp is not None:
            tools.append(live_mcp)
        sub_key = _sub_state_key(state_key, sub)
        sub_keys.append(sub_key)
        subs.append(
            LlmAgent(
                name=f"mantri_{role}__{sub}",
                model=models.gemini_flash(sub_role),
                description=f"The {sub_display} sub-advisor of the {display} mantri.",
                instruction=_subadvisor_instruction(role, sub_role, display, lens, sub_display),
                tools=tools,
                output_key=sub_key,
            )
        )
    panel = ParallelAgent(
        name=f"mantri_{role}_ensemble",
        description=f"The {display} mantri — three disjoint sub-advisors on the {lens} lens.",
        sub_agents=subs,
    )
    reducer = MantriReducer(
        name=f"mantri_{role}_reducer",
        role=role,
        display=display,
        lens=lens,
        state_key=state_key,
        sub_keys=sub_keys,
        primary_sub=config.ensemble_primary(role),
    )
    return SequentialAgent(
        name=f"mantri_{role}",
        description=f"The {display} mantri — {lens} lens (3-advisor ensemble).",
        sub_agents=[panel, reducer],
    )


def build_mantris() -> list[BaseAgent]:
    return [
        build_mantri_ensemble(role, display, state_key, lens)
        for role, display, state_key, lens in config.MANTRIS
    ]


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


# ─── Prosecutor (Claude · Vertex) — graduated re-prosecution (2b.2) ───────────
def _prosecutor_instruction(ctx: ReadonlyContext) -> str:
    verdict = ctx.state.get(config.StateKeys.VERDICT, {})
    if not isinstance(verdict, dict):
        verdict = parse_json(verdict)
    rnd = ctx.state.get(config.StateKeys.PROSECUTION_ROUND, 0)
    body = (
        prompts.PROSECUTOR
        + f"\n\n[PROSECUTION_ROUND::{rnd}]\n\n"
        + f"THE VERDICT UNDER PROSECUTION:\n{json.dumps(verdict, indent=2)}\n\n"
        + _grounding_section(ctx)
    )
    # Graduated: on a re-prosecution round, the chamber has strengthened the ONE
    # reason the prior round faulted — narrow the attack to that, don't reset.
    if int(rnd or 0) >= 1:
        revisions = ctx.state.get(config.StateKeys.REASON_REVISIONS, []) or []
        prior = ctx.state.get(config.StateKeys.PROSECUTION, {})
        if not isinstance(prior, dict):
            prior = parse_json(prior)
        body += (
            prompts.PROSECUTOR_GRADUATED
            + f"\nYOUR PRIOR ATTACK:\n{prior.get('attack', '')}\n\n"
            + f"THE STRENGTHENED REASON(S):\n{json.dumps(revisions, indent=2)}\n"
        )
    return body


def build_prosecutor() -> LlmAgent:
    return LlmAgent(
        name="prosecutor",
        model=models.claude_prosecutor(),
        description="Claude via Vertex — steelmans the null case and tries to defeat the verdict.",
        instruction=_prosecutor_instruction,
        output_schema=ProsecutionSchema,
        output_key=config.StateKeys.PROSECUTION,
    )


# ─── Reviser (Claude · Vertex) — strengthen the ONE faulted reason (2b.2) ─────
def _reviser_instruction(ctx: ReadonlyContext) -> str:
    prosecution = ctx.state.get(config.StateKeys.PROSECUTION, {})
    if not isinstance(prosecution, dict):
        prosecution = parse_json(prosecution)
    verdict = ctx.state.get(config.StateKeys.VERDICT, {})
    if not isinstance(verdict, dict):
        verdict = parse_json(verdict)
    survived = bool(prosecution.get("survived"))
    try:
        idx = int(prosecution.get("faulted_reason_index", -1))
    except (TypeError, ValueError):
        idx = -1
    # A marker the deterministic offline replay keys on; in live it just narrows
    # the Claude reviser to the faulted reason (or tells it there's nothing to do).
    marker = "[REVISE::none]" if (survived or idx < 0) else f"[REVISE::reason_index={idx}]"
    reasons = verdict.get("reasons", []) if isinstance(verdict, dict) else []
    return (
        prompts.REVISER
        + f"\n\n{marker}\n\n"
        + f"THE PROSECUTOR'S ATTACK:\n{prosecution.get('attack', '')}\n\n"
        + f"THE VERDICT'S REASONS:\n{json.dumps(reasons, indent=2)}\n\n"
        + _grounding_section(ctx)
    )


class ReviserReducer(BaseAgent):
    """Append the reviser's per-round targeted revision to the revisions ledger.

    Deterministic — records ONLY a real repair (target_reason_index >= 0 with a
    non-empty revised reason), so a surviving round (the reviser returns -1) adds
    nothing. This keeps the ledger a faithful record of graduated repairs."""

    async def _run_async_impl(
        self, ctx: InvocationContext
    ) -> AsyncGenerator[Event, None]:
        state = ctx.session.state
        raw = state.get(config.StateKeys.LATEST_REASON_REVISION)
        rev = raw if isinstance(raw, dict) else parse_json(raw)
        revisions = list(state.get(config.StateKeys.REASON_REVISIONS, []))
        try:
            idx = int(rev.get("target_reason_index", -1))
        except (TypeError, ValueError):
            idx = -1
        if idx >= 0 and rev.get("revised_reason"):
            rnd = int(state.get(config.StateKeys.PROSECUTION_ROUND, 0)) + 1
            revisions.append(
                {
                    "round": rnd,
                    "target_reason_index": idx,
                    "revised_reason": rev.get("revised_reason", ""),
                    "note": rev.get("note", ""),
                }
            )
        delta = {config.StateKeys.REASON_REVISIONS: revisions}
        state.update(delta)
        yield Event(author=self.name, actions=EventActions(state_delta=delta))


def build_reviser() -> SequentialAgent:
    """The graduated repair step inside the prosecution loop: a Claude seat that
    strengthens ONLY the faulted reason, then a deterministic reducer that records
    the repair in the revisions ledger. Runs between the prosecutor and the
    prosecution check, so the next round re-prosecutes the strengthened verdict."""
    author = LlmAgent(
        name="reviser_author",
        model=models.claude_reviser(),
        description="Claude via Vertex — strengthens ONLY the reason the prosecutor faulted.",
        instruction=_reviser_instruction,
        output_schema=RevisionSchema,
        output_key=config.StateKeys.LATEST_REASON_REVISION,
    )
    return SequentialAgent(
        name="reviser",
        description="Targeted reason-repair (Claude) + a deterministic revision ledger.",
        sub_agents=[author, ReviserReducer(name="reviser_reducer")],
    )
