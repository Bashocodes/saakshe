"""saakshe.common.a2a — cross-quadrant contracts (CONTRACT 2 & 3).

The per-quadrant *shape* is given by arivu's template. The cross-quadrant *seams*
are new and shared, so they live here, defined once, before any builder fans out:

  CONTRACT 2 — A2A handoff payloads
    * ContextPack            manas → everyone   (get_founder_context)
    * FounderVoiceAnswer     manas → arivu      (ask_founder_voice; refuses out-of-corpus)
    * Dispatch               arivu → kalai/kural (commands on approval)
    * CreativeMaster         kalai → kural      (the compliance-cleared handoff)

  CONTRACT 3 — orchestrator ↔ quadrant interface
    * QuadrantResult         the uniform return every quadrant gives the orchestrator
    * GateRequest            a pending founder tap, lifted into the stream's gate queue

Agent cards are served manually over FastAPI (exactly as arivu already does) —
the blocked a2a-sdk ``to_a2a()`` is noted as pending, not fought. Dispatch is an
in-process registry in demo; the same call shape addresses a real A2A endpoint in
live, so the seam is identical.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Optional


# ─── CONTRACT 2 · A2A handoff payloads ───────────────────────────────────────
@dataclass
class ContextPack:
    """manas's versioned company memory — the one thing the others are bound by.

    Returned by manas.get_founder_context(topic). Every fact carries a source so
    downstream work can cite it; out-of-corpus topics come back ``grounded=False``.
    """

    version: str                      # "v14"
    topic: str
    facts: list[dict] = field(default_factory=list)   # [{claim, source}]
    voice_rules: list[str] = field(default_factory=list)
    brand_rules: list[str] = field(default_factory=list)
    grounded: bool = True

    def as_dict(self) -> dict:
        return {
            "version": self.version, "topic": self.topic, "facts": self.facts,
            "voice_rules": self.voice_rules, "brand_rules": self.brand_rules,
            "grounded": self.grounded,
        }


@dataclass
class FounderVoiceAnswer:
    """manas.ask_founder_voice — answers AS the founder, grounded ONLY in corpus.

    ``refused=True`` (with citations empty) when the question is out-of-corpus —
    the hard refusal that keeps the company from being bound by a hallucinated
    founder-opinion. This is a contract, not a nicety: an eval fails otherwise.
    """

    answer: str
    citations: list[dict] = field(default_factory=list)
    refused: bool = False

    def as_dict(self) -> dict:
        return {"answer": self.answer, "citations": self.citations, "refused": self.refused}


@dataclass
class Dispatch:
    """An A2A command arivu's executor fires on approval (to kalai and/or kural)."""

    to: str                            # "kalai" | "kural"
    command: str                       # "render_asset" | "launch_campaign"
    brief: str
    hands_to: Optional[str] = None     # kalai's render hands_to "kural"
    gate: Optional[str] = None         # kural's campaign held at the publish gate
    meta: dict = field(default_factory=dict)

    def as_dict(self) -> dict:
        return {
            "to": self.to, "command": self.command, "brief": self.brief,
            "hands_to": self.hands_to, "gate": self.gate, "meta": self.meta,
        }


@dataclass
class CreativeMaster:
    """kalai → kural handoff: the compliance-cleared, on-brand multi-platform master.

    kalai never publishes and holds no channel keys; its only world-facing act is
    token spend. The master is what kural formats and puts live behind tap 2.
    """

    asset_id: str
    brief: str
    formats: dict = field(default_factory=dict)        # {"x":..., "ig":..., "linkedin":...}
    fidelity_score: float = 0.0
    compliance: str = "cleared"                        # fail-closed: must be "cleared"
    spend_usd: float = 0.0

    def as_dict(self) -> dict:
        return {
            "asset_id": self.asset_id, "brief": self.brief, "formats": self.formats,
            "fidelity_score": self.fidelity_score, "compliance": self.compliance,
            "spend_usd": self.spend_usd,
        }


# ─── CONTRACT 2b · manas's pre-grounding clarifying questions ─────────────────
@dataclass
class ClarifyingQuestion:
    """A doubt manas raises while grounding a newly-connected project.

    The contract that keeps "no fabricated data" sacred during ingestion: manas
    asks because a DETERMINISTIC trigger found a gap — a contradiction between two
    sources, or a required field it could not extract — never because a model
    imagined a question. Phrasing may be Gemini-written; the *trigger* is code.

    These are NOT flywheel gates. They are a manas-internal step BEFORE the company
    is grounded enough to decide. Answering one folds the answer back into the
    corpus with real provenance ("founder answer · day 0") and re-curates, ticking
    the Context Pack. The two HITL gates (arivu decision, kural publish) are
    untouched — a ClarifyingQuestion must never become a third gate.
    """

    id: str
    text: str                       # the question, in plain words
    why: str                        # what the trigger saw (the honest reason it's asking)
    trigger: str                    # "contradiction" | "missing_field"
    blocks: str = ""                # what staying-unanswered blocks (e.g. "pricing grounding")
    status: str = "open"            # "open" | "answered"
    answer: str = ""                # the founder's answer (folded back into corpus)
    options: list[str] = field(default_factory=list)  # for a contradiction: the candidate values
    sources: list[str] = field(default_factory=list)  # provenance of the clashing/missing evidence

    def as_dict(self) -> dict:
        return {
            "id": self.id, "text": self.text, "why": self.why, "trigger": self.trigger,
            "blocks": self.blocks, "status": self.status, "answer": self.answer,
            "options": list(self.options), "sources": list(self.sources),
        }


# ─── CONTRACT 3 · orchestrator ↔ quadrant interface ──────────────────────────
@dataclass
class GateRequest:
    """A pending founder tap. The orchestrator lifts this into the stream's gate
    queue; resolving it (the tap) advances the flywheel."""

    gate_id: str
    quadrant: str
    agent: str
    gate_kind: str          # "decision" (tap 1 @ arivu) | "publish" (tap 2 @ kural)
    proposal: str
    reversible: bool
    detail: dict = field(default_factory=dict)

    def as_dict(self) -> dict:
        return {
            "gate_id": self.gate_id, "quadrant": self.quadrant, "agent": self.agent,
            "gate_kind": self.gate_kind, "proposal": self.proposal,
            "reversible": self.reversible, "detail": self.detail,
        }


@dataclass
class QuadrantResult:
    """The uniform result every quadrant hands the orchestrator.

    status:
      * "completed"          ran to the end, no gate (e.g. manas ground/learn)
      * "handoff"            produced output for the next quadrant, no gate (kalai)
      * "awaiting_approval"  halted at a founder gate (arivu decision, kural publish)
      * "no_safe_decision"   a deterministic rollback (arivu prosecution failed)
    """

    quadrant: str
    status: str
    output: dict = field(default_factory=dict)         # verdict / master / draft / pack
    gate: Optional[GateRequest] = None
    transcript: list[dict] = field(default_factory=list)  # [{actor, text}]
    state: dict = field(default_factory=dict)          # opaque carry-state for the next step

    def as_dict(self) -> dict:
        return {
            "quadrant": self.quadrant, "status": self.status, "output": self.output,
            "gate": self.gate.as_dict() if self.gate else None,
            "transcript": self.transcript,
        }


# ─── In-process A2A registry + agent cards ───────────────────────────────────
# A quadrant registers a handler keyed by (quadrant, skill); another quadrant (or
# the orchestrator) dispatches to it by the same name. The call shape is identical
# to a live A2A request, so wiring real endpoints later changes only the transport.
_HANDLERS: dict[str, Callable[..., Any]] = {}
_CARDS: dict[str, dict] = {}


def register_skill(quadrant: str, skill: str, handler: Callable[..., Any]) -> None:
    _HANDLERS[f"{quadrant}.{skill}"] = handler


def dispatch(quadrant: str, skill: str, *args, **kwargs) -> Any:
    """Call another quadrant's A2A skill in-process."""
    key = f"{quadrant}.{skill}"
    handler = _HANDLERS.get(key)
    if handler is None:
        raise KeyError(f"no A2A skill registered for {key!r}")
    return handler(*args, **kwargs)


def has_skill(quadrant: str, skill: str) -> bool:
    return f"{quadrant}.{skill}" in _HANDLERS


def register_card(quadrant: str, card: dict) -> None:
    _CARDS[quadrant] = card


def agent_card(quadrant: str) -> Optional[dict]:
    return _CARDS.get(quadrant)


def all_cards() -> dict[str, dict]:
    return dict(_CARDS)
