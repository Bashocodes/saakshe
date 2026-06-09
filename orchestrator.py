"""saakshe — the flywheel orchestrator (the resumable 2-gate state machine).

The hero loop is NOT one call. It halts and persists at each founder tap, exactly
like arivu's run→approve lifted to the company level:

    start()                      manas grounds → arivu decides → HALT at gate 1
      → approve(g1)              arivu executes + A2A dispatch → kalai makes →
                                 handoff → kural engages → HALT at gate 2
        → approve(g2)            kural publishes (dry-run) → manas learns (Pack
                                 vN → vN+1) → the flywheel closes

Exactly two founder gates: tap 1 at arivu's decision, tap 2 at kural's mouth.
kalai's compliance is internal and fail-closed — no founder tap there. Every step
emits to the one ordered stream; the witness and the cockpit are pure renders of it.

arivu is the untouched, already-green module — driven through its public runner
(deliberate / execute_decision / build_transcript). The other three quadrants
expose the uniform interface in their runner modules.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional
from uuid import uuid4

import common  # noqa: F401  (bootstraps arivu onto sys.path)
from common import a2a, config, project
from common.stream import STREAM, EventStream

import manas.runner as manas
import kalai.runner as kalai
import kural.runner as kural

# arivu — the reference module, imported through the common bootstrap, untouched.
from arivu import config as arivu_config
from arivu import runner as arivu_runner
from arivu.util import parse_json as _arivu_parse

_ASK = arivu_config.StateKeys


@dataclass
class FlywheelState:
    run_id: str
    question: str
    org: dict
    status: str = "running"          # running | awaiting_approval | completed | no_safe_decision
    step: str = "start"
    open_gate: Optional[dict] = None
    context_pack: dict = field(default_factory=dict)
    arivu_state: dict = field(default_factory=dict)
    master: dict = field(default_factory=dict)
    kural_state: dict = field(default_factory=dict)
    verdict: dict = field(default_factory=dict)
    actions: list[dict] = field(default_factory=list)
    store: Any = None                # the per-user store this run is bound to
    user_id: str = ""                # the founder who owns this run (route-layer auth)
    spend_idem_key: str = ""         # the stable credit-spend key (for refund-on-failure)
    charged: bool = False            # whether this run was actually billed


_RUNS: dict[str, FlywheelState] = {}


def _verdict_of(arivu_state: dict) -> dict:
    v = arivu_state.get(_ASK.VERDICT, {})
    return v if isinstance(v, dict) else _arivu_parse(v)


def _brief_from_verdict(verdict: dict) -> str:
    decision = verdict.get("decision", config.CANON["verdict_decision"])
    return f"Launch announcement for the decision: {decision}"


# ─── start: manas grounds → arivu decides → halt at gate 1 ───────────────────
async def start(
    question: Optional[str] = None,
    org: Optional[dict] = None,
    stream: EventStream = STREAM,
    store: Any = None,
    user_id: str = "",
    spend_idem_key: str = "",
    charged: bool = False,
) -> dict:
    config.sync_runtime_mode()
    # Resolve + bind the per-user store for the whole run so every deep read
    # (manas.ground→corpus, kalai/kural org, manas.learn) sees THIS founder's
    # memory — never another tenant's, never the global default by accident.
    store = store or project.current_store()
    token = project.set_current_store(store)
    try:
        return await _start(question, org, stream, store, user_id, spend_idem_key, charged)
    finally:
        project.reset_current_store(token)


async def _start(question, org, stream, store, user_id="", spend_idem_key="", charged=False) -> dict:
    run_id = "fw_" + uuid4().hex[:10]
    # The question is the founder's (from chat); the org is the REAL connected
    # company from the project store — never a canned default.
    q = question or "Should we make this change?"
    org = org or dict(store.org_for_flywheel())
    state = FlywheelState(run_id=run_id, question=q, org=org, store=store,
                          user_id=user_id, spend_idem_key=spend_idem_key, charged=charged)
    _RUNS[run_id] = state

    stream.emit(run_id, "saakshe", "founder", f'asks: "{q}"', span="invocation", kind="span_start")
    stream.emit(run_id, "saakshe", "witness", "stakes here — route to arivu (decide)", span="agent_run")

    # manas grounds the whole flywheel in the company's own memory (read-side A2A).
    stream.a2a(run_id, "arivu", "manas", "get_founder_context", state="submitted")
    pack = await manas.ground(stream, run_id, topic=q)
    state.context_pack = pack.as_dict()
    stream.a2a(run_id, "manas", "arivu", "Context Pack served", state="completed", version=pack.version)

    # arivu deliberates (real, untouched) and halts at the gate.
    arivu_state = await arivu_runner.deliberate(q, org)
    state.arivu_state = arivu_state
    state.verdict = _verdict_of(arivu_state)
    stream.emit_transcript(run_id, "arivu", arivu_runner.build_transcript(arivu_state))
    from common.usage import emit_authoritative
    emit_authoritative(stream, run_id, "arivu", arivu_state.get("_usage"), live=config.is_live())

    gate_status = arivu_state.get(_ASK.GATE_STATUS)
    defens = arivu_state.get(_ASK.DEFENSIBILITY)
    if gate_status != "awaiting_approval":
        state.status = "no_safe_decision"
        state.step = "rolled_back"
        stream.emit(run_id, "arivu", "gate", "no safe decision — verdict did not survive prosecution",
                    span="invocation", kind="note")
        return _summary(state, stream)

    conf = state.verdict.get("confidence", "—")
    proposal = (f"{state.verdict.get('decision', config.CANON['verdict_decision'])}  "
                f"· conf {conf} · defensibility {defens} ≥ {config.DEFENSIBILITY_THRESHOLD}")
    gate = a2a.GateRequest(
        gate_id="g1", quadrant="arivu", agent="Chair-synthesizer", gate_kind="decision",
        proposal=proposal, reversible=True,
        detail={"confidence": conf, "defensibility": defens,
                "dissent": state.verdict.get("dissent", "")},
    )
    stream.gate(run_id, "arivu", "Prosecutor", gate.gate_id, gate.proposal,
                gate_kind="decision", reversible=True, defensibility=defens, confidence=conf)
    state.open_gate = gate.as_dict()
    state.status = "awaiting_approval"
    state.step = "gate1"
    return _summary(state, stream)


# ─── approve: advance the flywheel one tap ───────────────────────────────────
async def approve(run_id: str, gate_id: Optional[str] = None, stream: EventStream = STREAM,
                  store: Any = None) -> dict:
    state = _RUNS.get(run_id)
    if state is None:
        raise KeyError(f"unknown flywheel run_id {run_id!r}")
    # Bind the SAME store the run started under so the closing manas.learn + the
    # kalai/kural reads write to this founder's memory, not the global default.
    store = store or state.store or project.current_store()
    token = project.set_current_store(store)
    try:
        return await _approve(run_id, state, gate_id, stream)
    finally:
        project.reset_current_store(token)


async def _approve(run_id: str, state: FlywheelState, gate_id: Optional[str],
                   stream: EventStream) -> dict:
    if state.status != "awaiting_approval" or not state.open_gate:
        raise RuntimeError(f"run {run_id} is not awaiting approval (status={state.status!r})")

    open_id = state.open_gate["gate_id"]
    if gate_id and gate_id != open_id:
        raise RuntimeError(f"gate {gate_id!r} is not the open gate ({open_id!r})")

    stream.resolve_gate(run_id, open_id, "approved")
    state.open_gate = None

    if open_id == "g1":
        await _after_decision(state, stream)
    elif open_id == "g2":
        await _after_publish(state, stream)
    return _summary(state, stream)


async def _after_decision(state: FlywheelState, stream: EventStream) -> None:
    run_id = state.run_id
    # arivu executes the approved verdict (dry-run) — commit + A2A dispatch + resolution.
    exec_result = arivu_runner.execute_decision(state.arivu_state, dry_run=True)
    commit = exec_result.get("commit", {})
    resolution = exec_result.get("resolution", {})
    stream.action(run_id, "arivu", "Executor",
                  f"commit {commit.get('flag','flag')} {commit.get('from','')}→{commit.get('to','')} · "
                  f"file resolution {resolution.get('url','')}",
                  resolution_url=resolution.get("url"))
    state.actions.append({"quadrant": "arivu", "text": "feature-flag flip + signed board resolution"})

    brief = _brief_from_verdict(state.verdict)
    stream.a2a(run_id, "arivu", "kalai", "render_asset", state="submitted", brief=brief)
    stream.a2a(run_id, "arivu", "kural", "launch_campaign (held at publish gate)", state="submitted")

    # kalai makes — handoff, no gate. Serve manas's brand-asset vault into the
    # studio. Fail-soft: a vault error never sinks the render (demo = empty = [] =
    # the designer prompt stays byte-identical to the pre-vault path).
    try:
        assets = a2a.dispatch("manas", "get_assets", kinds=["logo", "reference"])
    except Exception:
        assets = []
    kalai_res = await kalai.make(stream, run_id, brief, state.context_pack, assets=assets)
    if kalai_res.status != "handoff":
        state.status = "no_safe_decision"
        state.step = "kalai_blocked"
        return
    state.master = kalai_res.output

    # kural engages — halts at the publish gate (tap 2).
    kural_res = await kural.engage(stream, run_id, state.master, state.context_pack)
    state.kural_state = kural_res.state
    if kural_res.status != "awaiting_approval" or not kural_res.gate:
        state.status = "no_safe_decision"
        state.step = "kural_blocked"
        return
    state.open_gate = kural_res.gate.as_dict()
    state.status = "awaiting_approval"
    state.step = "gate2"


async def _after_publish(state: FlywheelState, stream: EventStream) -> None:
    run_id = state.run_id
    result = await kural.publish(stream, run_id, state.kural_state, dry_run=True)
    state.actions.append({"quadrant": "kural", "text": "publish (dry-run) to x · ig · linkedin"})

    # manas learns — the closing beat, Context Pack ticks.
    learn = await manas.learn(stream, run_id, {"decision": state.verdict.get("decision", "")})
    state.actions.append({"quadrant": "manas", "text": "remember the decision · " + learn.output.get("context_pack_to", "")})

    stream.emit(run_id, "saakshe", "witness",
                "the company remembers its own decision — flywheel closed", span="invocation", kind="span_end")
    state.status = "completed"
    state.step = "done"


# ─── summary (JSON-serializable view for the server / witness) ───────────────
def _summary(state: FlywheelState, stream: EventStream) -> dict:
    return {
        "run_id": state.run_id,
        "mode": config.mode(),
        "status": state.status,
        "step": state.step,
        "question": state.question,
        "org": state.org.get("name"),
        "verdict": state.verdict,
        "open_gate": state.open_gate,
        "gate_queue": stream.open_gates(state.run_id),
        "actions": state.actions,
        "stream_cursor": stream.cursor,
    }


def get_run(run_id: str) -> Optional[FlywheelState]:
    return _RUNS.get(run_id)
