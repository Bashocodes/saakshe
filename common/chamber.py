"""common.chamber — the reusable decision-chamber skeleton.

This is arivu's proven 6-stage pipeline generalised into ONE reusable primitive:

    frame? → ParallelAgent(panel) → debate_loop? → verdict
           → prosecution_loop(prosecutor[, reviser]) → gate

``build_chamber`` owns the genuinely-reusable, fiddly ADK part: the topology, the
three deterministic control agents lifted out of ``arivu/arivu/agent.py``
(``DebateCheckAgent`` / ``ProsecutionCheckAgent`` / ``GateAgent``), the loop
wiring, the DEBATE_HISTORY / PROSECUTION_HISTORY accumulation, the escalate /
rollback semantics, and the gate. Every arivu-specific coupling — the state-key
bindings, the stop/rollback predicates, the gate condition — is a parameter on
``ChamberSpec``, defaulted to a generic threshold implementation. arivu passes its
EXACT ``analyst`` predicates + its ``StateKeys`` so the extraction is
byte-identical; faculties take the generic defaults.

TWO HARD RULES (the skeleton's contract):
  1. This module NEVER imports arivu (skeleton only — no faculty coupling).
  2. ``build_chamber`` / ``run_chamber`` construct NO model. Callers build their
     own LLM seats (with their own factory / prompts / schemas / tools / demo
     replay) and pass them in. arivu wires seats to arivu's replay → its 4 tests
     stay byte-identical; faculties wire seats to ``common.models`` → their replay
     routes through ``_RESOLVERS``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, AsyncGenerator, Callable, Optional

from google.adk.agents import (
    BaseAgent,
    LoopAgent,
    ParallelAgent,
    SequentialAgent,
)
from google.adk.agents.invocation_context import InvocationContext
from google.adk.events import Event, EventActions


# ─── Token budget (constraint #5 — RESERVED now, enforced in Track B) ─────────
@dataclass
class TokenBudget:
    """A per-chamber token ceiling. Reserved on the spec NOW so bolting on
    enforcement later (Track B, step 9) doesn't churn every call site. The
    ``charge`` hook is a no-op passthrough until then."""

    total: Optional[int] = None
    spent: int = 0

    def charge(self, tokens: int) -> None:  # pragma: no cover — no-op until Track B
        """No-op placeholder. Track B turns this into a hard gate."""
        return None


# ─── JSON coercion (no faculty dep — a tiny local parse) ──────────────────────
def _as_dict(raw: Any) -> dict:
    """Coerce a model output (already a dict, or a JSON string) into a dict."""
    if isinstance(raw, dict):
        return raw
    if not raw:
        return {}
    import json

    try:
        out = json.loads(raw)
        return out if isinstance(out, dict) else {}
    except (TypeError, ValueError):
        # Tolerate prose-wrapped JSON the way arivu's util.parse_json does.
        try:
            text = str(raw)
            start, end = text.find("{"), text.rfind("}")
            if start != -1 and end != -1 and end > start:
                out = json.loads(text[start : end + 1])
                return out if isinstance(out, dict) else {}
        except (TypeError, ValueError):
            pass
    return {}


# ─── Default predicates (faculties take these; arivu injects its own) ─────────
def _default_should_stop(
    score: float, round_: int, threshold: float, max_rounds: int
) -> tuple[bool, bool, str]:
    """Generic prosecution stop/rollback predicate — reproduces arivu's exact
    ``prosecution_should_stop`` semantics: survive only when the score crosses
    the bar; at the max round still below it, stop with a rollback (survived
    False, "no safe decision"); else continue. arivu passes its own bound
    version so 2a is byte-identical; faculties bind this with their threshold."""
    if score >= threshold:
        return True, True, (
            f"score {score:.2f} ≥ {threshold} — survives"
        )
    if round_ >= max_rounds:
        return True, False, (
            f"max rounds ({max_rounds}) reached at {score:.2f} — "
            "rollback: no safe decision, re-frame"
        )
    return False, False, (
        f"score {score:.2f} < {threshold} — continue"
    )


def _default_debate_should_stop(
    convergence: float, round_: int, threshold: float, max_rounds: int
) -> tuple[bool, str]:
    """Generic debate stop predicate — reproduces arivu's ``debate_should_stop``
    semantics: stop on convergence ≥ threshold or at the round cap."""
    if convergence >= threshold:
        return True, f"converged (score {convergence:.2f} ≥ {threshold})"
    if round_ >= max_rounds:
        return True, f"max rounds ({max_rounds}) reached"
    return False, f"score {convergence:.2f} < {threshold} — continue"


# ─── The chamber spec (caller-built seats + bindings + injectable predicates) ─
@dataclass
class ChamberSpec:
    namespace: str                          # "arivu"|"kalai"|"kural"|"manas" — labels/stream only
    # ── caller-built seats (each side wires its own model + demo replay) ──
    panel: list[BaseAgent]                  # the parallel advisors (may be ensembles)
    verdict: BaseAgent                      # the synthesizer (a Claude seat)
    prosecutor: BaseAgent                   # the adversary (a Claude seat)
    reviser: Optional[BaseAgent] = None     # graduated step: revises ONE reason between rounds (2b)
    frame: Optional[BaseAgent] = None       # chair/frame (or None)
    debate: Optional[BaseAgent] = None      # debate moderator (or None to skip the convergence loop)
    # ── deciding factor (the one question this chamber answers) ──
    score_key: str = ""                     # key the prosecutor's score lives under (dict field + state key)
    survived_key: str = ""                  # state key for the survived bool
    threshold: float = 0.80
    max_prosecution_rounds: int = 3
    # ── prosecution state-key bindings (history accumulation) ──
    prosecution_key: str = ""               # the prosecutor seat's output_key (default: prosecutor.output_key)
    prosecution_round_key: str = "prosecution_round"
    prosecution_history_key: str = "prosecution_history"
    # ── optional debate/convergence stage ──
    convergence_fn: Optional[Callable[[list, int], float]] = None
    convergence_key: str = "convergence_score"
    convergence_threshold: float = 0.0
    max_debate_rounds: int = 0
    debate_round_key: str = "debate_round"
    debate_done_key: str = "debate_done"
    debate_history_key: str = "debate_history"
    positions_reader: Optional[Callable[[Any], list]] = None  # state -> [position dict]
    # ── injectable control predicates (arivu passes its own; faculties default) ──
    prosecution_should_stop: Optional[Callable[[float, int], tuple[bool, bool, str]]] = None
    debate_should_stop: Optional[Callable[[float, int], tuple[bool, str]]] = None
    # ── frame-time grounding (live; 2b) ──
    grounding_callback: Optional[Callable[[Any], None]] = None
    # ── gate ──
    human_tap: bool = False                 # True = halt for the founder (ONLY company arivu, tap-1)
    gate_status_key: str = "gate_status"
    gate_condition: Optional[Callable[[dict], bool]] = None  # default: survived_key is True
    # ── cosmetic: the parallel-panel agent name (preserves a caller's exact ADK
    #    node name; default keeps it namespaced) ──
    deliberation_name: str = ""             # default: f"{namespace}_deliberation"
    # ── token budget (constraint #5 — RESERVED now, enforced Track B) ──
    budget: Optional[TokenBudget] = None    # default None = no-op passthrough

    def _positions(self, state) -> list:
        if self.positions_reader is not None:
            return self.positions_reader(state)
        # Generic default: read every panel seat's output_key as a position dict.
        out: list = []
        for seat in self.panel:
            key = getattr(seat, "output_key", None)
            if not key:
                continue
            d = _as_dict(state.get(key))
            if d:
                out.append(d)
        return out

    def _stop_prosecution(self, score: float, round_: int) -> tuple[bool, bool, str]:
        if self.prosecution_should_stop is not None:
            return self.prosecution_should_stop(score, round_)
        return _default_should_stop(
            score, round_, self.threshold, self.max_prosecution_rounds
        )

    def _stop_debate(self, convergence: float, round_: int) -> tuple[bool, str]:
        if self.debate_should_stop is not None:
            return self.debate_should_stop(convergence, round_)
        return _default_debate_should_stop(
            convergence, round_, self.convergence_threshold, self.max_debate_rounds
        )

    def _gate_open(self, state: dict) -> bool:
        if self.gate_condition is not None:
            return bool(self.gate_condition(state))
        return bool(state.get(self.survived_key, False))


# ─── Deterministic termination agents (no model — pure safety logic) ──────────
class DebateCheckAgent(BaseAgent):
    """Computes convergence from the positions and escalates on threshold / cap.

    Generalised from arivu's ``DebateCheckAgent``: the state-key bindings and the
    convergence/stop predicates come from the spec, not a module-global SK."""

    spec: ChamberSpec

    async def _run_async_impl(
        self, ctx: InvocationContext
    ) -> AsyncGenerator[Event, None]:
        state = ctx.session.state
        spec = self.spec
        rnd = int(state.get(spec.debate_round_key, 0)) + 1
        positions = spec._positions(state)
        conv = spec.convergence_fn(positions, rnd) if spec.convergence_fn else 0.0
        stop, reason = spec._stop_debate(conv, rnd)
        history = list(state.get(spec.debate_history_key, []))
        history.append({"round": rnd, "convergence": conv, "reason": reason})
        delta = {
            spec.debate_round_key: rnd,
            spec.convergence_key: conv,
            spec.debate_done_key: stop,
            spec.debate_history_key: history,
        }
        state.update(delta)
        yield Event(
            author=self.name,
            actions=EventActions(state_delta=delta, escalate=stop),
        )


class ProsecutionCheckAgent(BaseAgent):
    """Reads the prosecutor's self-assessed score and escalates on threshold; a
    max-iteration cap triggers a rollback ('no safe decision').

    Generalised from arivu's ``ProsecutionCheckAgent``: which state key the
    prosecutor wrote to, which field carries the score, the survived/round/history
    keys, and the stop/rollback predicate all come from the spec."""

    spec: ChamberSpec

    async def _run_async_impl(
        self, ctx: InvocationContext
    ) -> AsyncGenerator[Event, None]:
        state = ctx.session.state
        spec = self.spec
        prosecution = _as_dict(state.get(spec.prosecution_key, {}))
        try:
            score = float(prosecution.get(spec.score_key, 0.0))
        except (TypeError, ValueError):
            score = 0.0
        rnd = int(state.get(spec.prosecution_round_key, 0)) + 1
        stop, survived, reason = spec._stop_prosecution(score, rnd)
        history = list(state.get(spec.prosecution_history_key, []))
        history.append(
            {"round": rnd, spec.score_key: score, "survived": survived, "reason": reason}
        )
        delta = {
            spec.prosecution_round_key: rnd,
            spec.score_key: score,
            spec.survived_key: survived,
            spec.prosecution_history_key: history,
        }
        state.update(delta)
        yield Event(
            author=self.name,
            actions=EventActions(state_delta=delta, escalate=stop),
        )


class GateAgent(BaseAgent):
    """The chamber's gate. With ``human_tap`` it is the single HITL gate (the
    company arivu, tap-1): it halts the pipeline awaiting a human. Without it the
    gate is fail-closed: it clears iff ``gate_condition`` holds, else blocks.

    Generalised from arivu's ``GateAgent``: the gate-status key, the gate
    condition, and the human_tap behaviour all come from the spec."""

    spec: ChamberSpec

    async def _run_async_impl(
        self, ctx: InvocationContext
    ) -> AsyncGenerator[Event, None]:
        state = ctx.session.state
        spec = self.spec
        if spec.human_tap:
            survived = bool(state.get(spec.survived_key, False))
            status = "awaiting_approval" if survived else "no_safe_decision"
        else:
            status = "cleared" if spec._gate_open(state) else "blocked"
        state[spec.gate_status_key] = status
        yield Event(
            author=self.name,
            actions=EventActions(state_delta={spec.gate_status_key: status}),
        )


# ─── Assemble the chamber ─────────────────────────────────────────────────────
def build_chamber(spec: ChamberSpec) -> BaseAgent:
    """Assemble the chamber from the caller's seats. Constructs NO model.

    SequentialAgent([frame?, ParallelAgent(panel), debate_loop?, verdict,
    prosecution_loop(prosecutor[, reviser], ProsecutionCheck), gate]) — the
    prosecution loop accumulates history and escalates on
    ``spec.prosecution_should_stop(score, round)``; the gate halts for a human
    iff ``spec.human_tap``, else sets gate_status fail-closed from
    ``spec.gate_condition``."""
    # Default the prosecution-read key to the prosecutor seat's own output_key so
    # callers needn't restate it (arivu binds it explicitly to SK.PROSECUTION).
    if not spec.prosecution_key:
        spec.prosecution_key = getattr(spec.prosecutor, "output_key", "") or "prosecution"

    # Wire the frame's grounding callback if the caller supplied one (live; 2b).
    if spec.frame is not None and spec.grounding_callback is not None:
        try:
            spec.frame.before_agent_callback = spec.grounding_callback
        except (AttributeError, ValueError):
            pass

    deliberation = ParallelAgent(
        name=spec.deliberation_name or f"{spec.namespace}_deliberation",
        description="Disjoint advisors argue in parallel — anti-groupthink fan-out.",
        sub_agents=list(spec.panel),
    )

    stages: list[BaseAgent] = []
    if spec.frame is not None:
        stages.append(spec.frame)
    stages.append(deliberation)

    if spec.debate is not None:
        debate_loop = LoopAgent(
            name="debate_loop",
            description="Cross-rebuttal until a numeric convergence threshold or cap.",
            sub_agents=[spec.debate, DebateCheckAgent(name="debate_check", spec=spec)],
            max_iterations=spec.max_debate_rounds,
        )
        stages.append(debate_loop)

    stages.append(spec.verdict)

    prosecution_sub: list[BaseAgent] = [spec.prosecutor]
    if spec.reviser is not None:
        prosecution_sub.append(spec.reviser)
    prosecution_sub.append(ProsecutionCheckAgent(name="prosecution_check", spec=spec))
    prosecution_loop = LoopAgent(
        name="prosecution_loop",
        description="Verdict ↔ prosecution until the score crosses the bar or rollback.",
        sub_agents=prosecution_sub,
        max_iterations=spec.max_prosecution_rounds,
    )
    stages.append(prosecution_loop)

    stages.append(GateAgent(name="gate", spec=spec))

    return SequentialAgent(
        name=spec.namespace,
        description=(
            f"{spec.namespace} chamber — deliberates, prosecutes its own verdict, "
            "and gates before acting."
        ),
        sub_agents=stages,
    )


# ─── Run helper (InMemoryRunner; mirrors arivu.runner.deliberate) ─────────────
async def run_chamber(spec: ChamberSpec, init_state: Optional[dict] = None) -> dict:
    """Run the chamber to its gate and return the final session state as a dict.

    An ``InMemoryRunner`` helper mirroring ``arivu.runner.deliberate``: it seeds
    the session with ``init_state``, drives the pipeline, sums real metered token
    usage into ``state['_usage']``, and returns the final state. Constructs NO
    model — the seats inside ``spec`` already carry their own model/replay."""
    from google.adk.runners import InMemoryRunner
    from google.genai import types

    agent = build_chamber(spec)
    app = spec.namespace
    user = "founder"

    runner = InMemoryRunner(agent=agent, app_name=app)
    session = await runner.session_service.create_session(
        app_name=app, user_id=user, state=dict(init_state or {})
    )
    msg = types.Content(role="user", parts=[types.Part(text="run")])
    events = []
    async for _event in runner.run_async(
        user_id=user, session_id=session.id, new_message=msg
    ):
        events.append(_event)

    final = await runner.session_service.get_session(
        app_name=app, user_id=user, session_id=session.id
    )
    state = dict(final.state)
    inp = out = calls = 0
    for ev in events:
        um = getattr(ev, "usage_metadata", None)
        if not um:
            continue
        p = getattr(um, "prompt_token_count", 0) or 0
        c = getattr(um, "candidates_token_count", 0) or 0
        if p or c:
            inp += int(p)
            out += int(c)
            calls += 1
    state["_usage"] = {"input_tokens": inp, "output_tokens": out, "llm_calls": calls}
    return state
