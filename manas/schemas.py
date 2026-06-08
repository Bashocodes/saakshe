"""manas — forced-shape schemas for the two Claude-via-Vertex seats.

The two highest-stakes outputs in manas are the Curator's commit synthesis and the
Founder Voice's answer. Constraining each with an ADK ``output_schema`` (exactly as
arivu does with VerdictSchema / ProsecutionSchema) makes well-formed JSON the only
possible output, so a live Claude reply can never collapse to prose →
  * the curator check reading groundedness=0.0 → a permanent "no safe commit", or
  * the refusal flag getting lost so an out-of-corpus question is silently answered.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class Claim(BaseModel):
    claim: str = Field(description="one specific factual statement about the company")
    source: str = Field(description="the imbibed source it is grounded in (imbiber · file · day)")


class CuratorSchema(BaseModel):
    """The Curator's verify-before-commit synthesis (Claude · Vertex)."""

    claims: list[Claim] = Field(
        description="the claims proposed for commit — EVERY one must cite a source"
    )
    contradictions: list[str] = Field(
        default_factory=list,
        description="any contradictions found among the claims (empty when clean)",
    )
    groundedness: float = Field(description="0.0-1.0 self-assessed groundedness of the claim set")
    version_to: str = Field(description="the Context Pack version this commit would produce")
    note: str = Field(default="", description="what was revised this round to tighten grounding")


class FounderVoiceSchema(BaseModel):
    """The Founder Voice answer (Claude · Vertex) — REFUSES out-of-corpus."""

    answer: str = Field(description="the answer in the founder's voice, or the refusal")
    citations: list[Claim] = Field(
        default_factory=list,
        description="the corpus sources the answer is grounded in; EMPTY when refused",
    )
    refused: bool = Field(
        description="True iff the question is out-of-corpus — the hard refusal contract"
    )
