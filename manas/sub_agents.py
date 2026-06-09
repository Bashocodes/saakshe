"""manas — the memory pipeline as ADK agents.

A Gemini Mind-Keeper router, four disjoint Gemini imbibers (genuine agents —
disjoint modality, disjoint data, so they cannot collapse into one prompt), and
the two Claude-via-Vertex high-stakes seats: the Memory Curator (verify-before-
commit) and the Founder Voice (refuses out-of-corpus).

Every dynamic instruction is an InstructionProvider callable so we build the
prompt from live state ourselves — no ADK brace-templating, JSON schemas safe.

Importing this module registers the demo payload resolver with the shared
scripted model, so the package import wires replay before any agent runs.
"""

from __future__ import annotations

import json

from google.adk.agents import BaseAgent, LlmAgent
from google.adk.agents.readonly_context import ReadonlyContext

from common import config, models
from . import prompts
from . import state as st
from .demo_fixtures import scripted_payload
from .schemas import CuratorSchema, FounderVoiceSchema
from .tools import curator

NS = "manas"

# Register the demo resolver at import (before any agent runs in demo mode).
models.register_demo(NS, scripted_payload)


# ─── context helpers ─────────────────────────────────────────────────────────
def _org_name(ctx: ReadonlyContext) -> str:
    org = ctx.state.get(st.StateKeys.ORG) or {}
    if isinstance(org, dict):
        return org.get("name") or "the company"
    return str(org) or "the company"


def _topic(ctx: ReadonlyContext) -> str:
    return ctx.state.get(st.StateKeys.TOPIC) or "pricing"


def _outcome_text(ctx: ReadonlyContext) -> str:
    outcome = ctx.state.get(st.StateKeys.OUTCOME) or {}
    if isinstance(outcome, dict):
        return outcome.get("decision", "") or json.dumps(outcome)
    return str(outcome)


# ─── Mind Keeper (Gemini Pro · router) ───────────────────────────────────────
def _keeper_instruction(ctx: ReadonlyContext) -> str:
    return (
        prompts.MIND_KEEPER.replace("{org}", _org_name(ctx))
        + f"\n\nTHE DAY'S OUTCOME TO REMEMBER:\n{_outcome_text(ctx)}\n"
        + f"TOPIC: {_topic(ctx)}\n"
    )


def build_mind_keeper() -> LlmAgent:
    return LlmAgent(
        name="mind_keeper",
        model=models.gemini_pro(NS, "mind_keeper"),
        description="The Mind Keeper routes ingestion across modalities; knows, never decides.",
        instruction=_keeper_instruction,
        output_key=st.StateKeys.ROUTE,
    )


# ─── The four imbibers — each fans into a 4-sub-reader pod (5.3) ──────────────
# A channel imbiber is no longer a lone reader. Each is a SequentialAgent of:
#   ParallelAgent([claims · voice · brand · contradiction sub-readers]) → a reducer.
# The four sub-readers read the SAME channel through four disjoint sub-lenses in
# parallel (anti-collapse WITHIN the channel) and write disjoint sub-keys; the
# reducer folds them into the SAME INGEST_* blob the curator already consumes —
# the consolidated claims/voice_rules/brand_rules are lifted VERBATIM from the
# PRIMARY sub-reader, so the rolled-up blob stays byte-identical to today's
# _INGEST[channel]. This mirrors arivu's build_mantri_ensemble exactly. The pod
# code lives in imbiber_pod.py (kept beside the arivu ensemble template).
def build_imbibers() -> list[BaseAgent]:
    from . import imbiber_pod

    return [imbiber_pod.build(role) for role, *_rest in st.IMBIBERS]


# ─── Memory Curator (Claude · Vertex · CLAUDE SEAT 1) ────────────────────────
def _curator_instruction(ctx: ReadonlyContext) -> str:
    ingested = curator.read_ingested(ctx.state)
    rnd = int(ctx.state.get(st.StateKeys.CURATE_ROUND, 0)) + 1
    version_to = config.CANON["context_pack_to"]
    return (
        prompts.CURATOR
        + f"\n\n[CURATE_ROUND::{rnd}] [VERSION_TO::{version_to}]\n\n"
        + f"PRIOR MEMORY: Context Pack {config.CANON['context_pack_from']}\n\n"
        + f"THE IMBIBERS' RAW EXTRACTIONS:\n{json.dumps(ingested, indent=2)}\n"
    )


def build_curator() -> LlmAgent:
    # output_schema forces well-formed JSON (the curation contract), exactly like
    # arivu's VerdictSchema/ProsecutionSchema. ADK forbids tools alongside an
    # output_schema, so the citation/contradiction MATH is the deterministic
    # CuratorCheckAgent's job (it calls tools.curator pure fns) — never the model's:
    # a model can never talk the loop past the groundedness bar.
    return LlmAgent(
        name="memory_curator",
        model=models.claude(NS, "curator"),         # CLAUDE SEAT 1
        description="Claude via Vertex — verifies every claim cites a source and is non-contradictory before commit.",
        instruction=_curator_instruction,
        output_schema=CuratorSchema,
        output_key=st.StateKeys.CURATION,
    )


# ─── Founder Voice (Claude · Vertex · CLAUDE SEAT 2) ─────────────────────────
def _founder_voice_instruction(ctx: ReadonlyContext) -> str:
    from .tools import corpus

    question = ctx.state.get("voice_question") or ""
    pack = corpus.context_pack(_topic(ctx))
    corpus_block = json.dumps(pack.as_dict().get("facts", []), indent=2)
    # The question is wrapped in an unambiguous marker so the demo resolver can
    # isolate it from the prompt/corpus text (otherwise keyword matching would hit
    # words like "voice"/"price" that legitimately appear in the instruction).
    return (
        prompts.FOUNDER_VOICE
        + f"\n\nTHE CORPUS (only ground in this):\n{corpus_block}\n\n"
        + f"THE QUESTION:\n[[VOICE_Q::{question}::VOICE_Q]]\n"
    )


def build_founder_voice() -> LlmAgent:
    return LlmAgent(
        name="founder_voice",
        model=models.claude(NS, "founder_voice"),   # CLAUDE SEAT 2
        description="Claude via Vertex — answers as the founder, grounded only in corpus; refuses out-of-corpus.",
        instruction=_founder_voice_instruction,
        output_schema=FounderVoiceSchema,
        output_key="founder_voice_answer",
    )
