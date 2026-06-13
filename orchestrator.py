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
from common import a2a, config, project, taste
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
    # faculty-v2 joined-clearance: a post reaches tap-2 only when the media is
    # cleared (kalai) AND the words are claim-checked (kural). v1 leaves both True.
    kalai_media_cleared: bool = False
    kural_copy_claim_checked: bool = False


_RUNS: dict[str, FlywheelState] = {}


# ── restart-proofing: _RUNS is a cache; the bound store is the system of record ─
def _snapshot(state: FlywheelState) -> dict:
    import json

    d = {
        "run_id": state.run_id, "question": state.question, "org": state.org,
        "status": state.status, "step": state.step, "open_gate": state.open_gate,
        "context_pack": state.context_pack, "arivu_state": state.arivu_state,
        "kural_state": state.kural_state, "master": state.master,
        "verdict": state.verdict, "actions": state.actions,
        "user_id": state.user_id, "spend_idem_key": state.spend_idem_key,
        "charged": state.charged,
        "kalai_media_cleared": state.kalai_media_cleared,
        "kural_copy_claim_checked": state.kural_copy_claim_checked,
    }
    return json.loads(json.dumps(d, default=str))   # scrub non-JSON leaves


def _persist_run(state: FlywheelState) -> None:
    """Snapshot the run via the bound store (file or Supabase) so a restart never
    orphans a charged run. Fail-soft: persistence is belt-and-braces — it must
    never break the run it is backing up."""
    store = state.store or project.current_store()
    save = getattr(store, "save_run", None)
    if not callable(save):
        return
    try:
        save(state.run_id, _snapshot(state))
    except Exception:  # noqa: BLE001
        pass


def _restore_run(run_id: str, store: Any) -> Optional[FlywheelState]:
    """Rehydrate a persisted run into _RUNS (the read-through on a cache miss)."""
    load = getattr(store, "load_run", None)
    try:
        snap = load(run_id) if callable(load) else None
    except Exception:  # noqa: BLE001
        snap = None
    if not isinstance(snap, dict) or not snap:
        return None
    state = FlywheelState(run_id=run_id, question=snap.get("question", ""),
                          org=snap.get("org") or {}, store=store)
    for k in ("status", "step", "open_gate", "context_pack", "arivu_state",
              "kural_state", "master", "verdict", "actions", "user_id",
              "spend_idem_key", "charged", "kalai_media_cleared",
              "kural_copy_claim_checked"):
        if k in snap:
            setattr(state, k, snap[k])
    _RUNS[run_id] = state
    return state


def _verdict_of(arivu_state: dict) -> dict:
    v = arivu_state.get(_ASK.VERDICT, {})
    return v if isinstance(v, dict) else _arivu_parse(v)


def _kalai_media_cleared(res) -> bool:
    """kalai's media clearance. kalai already refuses handoff when not cleared
    (handoff ⇒ cleared); read the explicit marker defensively."""
    try:
        out = res.output if isinstance(res.output, dict) else {}
        return out.get("compliance", "cleared") == "cleared"
    except Exception:  # noqa: BLE001 — a malformed result never crashes the run
        return False


def _kural_copy_claim_checked(res) -> bool:
    """kural claim-checked the words it authored (copy_claim_checked on its
    carry-state) — the orchestrator ANDs it with kalai's media clearance at tap-2."""
    try:
        st = res.state if isinstance(res.state, dict) else {}
        return bool(st.get("copy_claim_checked", False))
    except Exception:  # noqa: BLE001
        return False


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

    # Yesterday's results learn FIRST — measure → learn → ground, so today's
    # Context Pack stands on what actually happened, not only on what was decided.
    # Unconfigured stats surface (demo / CI) → no facts, no events, byte-identical.
    try:
        results = await kural.measure(stream, run_id)
        if results:
            await manas.learn(stream, run_id, {"results": results})
    except Exception:  # noqa: BLE001 — a flaky stats surface never blocks the day
        pass

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
        _ask_founder(taste.no_safe_path(run_id, q), store, stream, run_id)
        _persist_run(state)
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
    _ask_founder(taste.close_call(run_id, q, state.verdict, defens), store, stream, run_id)
    state.open_gate = gate.as_dict()
    state.status = "awaiting_approval"
    state.step = "gate1"
    _persist_run(state)
    return _summary(state, stream)


def _ask_founder(questions: list[a2a.ClarifyingQuestion], store, stream: EventStream, run_id: str) -> None:
    """Lift the chamber's founder-taste asks onto the questions surface, signed by
    the asking agent. Never a gate, never blocking — the founder answers through
    the same chat the doubts ride, whenever they like."""
    for q in questions:
        try:
            store.add_question(q)
            stream.emit(run_id, "arivu", q.asked_by.split("·")[-1].strip() or "Verdict Chair",
                        f"question for the founder — {q.text}", span="invocation", kind="note")
        except Exception:  # noqa: BLE001 — asking must never sink the run
            pass


# ─── approve: advance the flywheel one tap ───────────────────────────────────
def _live_send_armed() -> bool:
    """Whether a tap-2 may fire a REAL publish. Three independent keys must turn:
    the founder's explicit per-tap arm flag (caller), the deploy-level
    SAAKSHE_ALLOW_LIVE_SEND=1 env, and a registered channel client — so neither
    a stray flag, a stray env, nor a stray client can put anything live alone."""
    import os
    from kural.tools import channels as _channels

    return os.environ.get("SAAKSHE_ALLOW_LIVE_SEND") == "1" and _channels.has_channel_client()


async def approve(run_id: str, gate_id: Optional[str] = None, stream: EventStream = STREAM,
                  store: Any = None, *, arm_real_send: bool = False) -> dict:
    state = _RUNS.get(run_id)
    if state is None:
        # The cache lost it (a restart) — rehydrate from the persisted snapshot.
        state = _restore_run(run_id, store or project.current_store())
    if state is None:
        raise KeyError(f"unknown flywheel run_id {run_id!r}")
    # Bind the SAME store the run started under so the closing manas.learn + the
    # kalai/kural reads write to this founder's memory, not the global default.
    store = store or state.store or project.current_store()
    token = project.set_current_store(store)
    try:
        return await _approve(run_id, state, gate_id, stream,
                              arm_real_send=bool(arm_real_send))
    finally:
        project.reset_current_store(token)


async def _approve(run_id: str, state: FlywheelState, gate_id: Optional[str],
                   stream: EventStream, *, arm_real_send: bool = False) -> dict:
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
        # dry_run stays the hardcoded default; the ONLY way to a real side effect
        # is the founder's tap WITH the arm flag AND the env AND a real client.
        await _after_publish(state, stream,
                             dry_run=not (arm_real_send and _live_send_armed()))
    _persist_run(state)
    return _summary(state, stream)


def _warn_if_no_logo(state: FlywheelState, stream: EventStream, assets: list[dict]) -> None:
    """The honest make-time warning: a LIVE, connected company whose vault served
    no logo-kind asset hears it before kalai makes. Gated like the studio's
    ``if served:`` — demo mode (the canned flywheel, the baked seed) and an
    unconnected store emit nothing, so the demo stream stays byte-identical."""
    if not config.is_live():
        return
    if state.store is None or not state.store.is_connected():
        return
    if any(a.get("kind") == "logo" for a in assets):
        return
    stream.emit(state.run_id, "manas", "Brand Vault",
                "making without brand assets — the vault has no logo",
                span="agent_run", kind="note")


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
    _warn_if_no_logo(state, stream, assets)
    kalai_res = await kalai.make(stream, run_id, brief, state.context_pack, assets=assets)
    if kalai_res.status != "handoff":
        state.status = "no_safe_decision"
        state.step = "kalai_blocked"
        return
    state.master = kalai_res.output
    state.kalai_media_cleared = _kalai_media_cleared(kalai_res)

    # kural engages — halts at the publish gate (tap 2).
    kural_res = await kural.engage(stream, run_id, state.master, state.context_pack)
    state.kural_state = kural_res.state
    if kural_res.status != "awaiting_approval" or not kural_res.gate:
        state.status = "no_safe_decision"
        state.step = "kural_blocked"
        return
    state.kural_copy_claim_checked = _kural_copy_claim_checked(kural_res)
    # JOINED-CLEARANCE: a media-cleared but copy-UNCHECKED post must NOT reach tap-2.
    if not (state.kalai_media_cleared and state.kural_copy_claim_checked):
        state.status = "no_safe_decision"
        state.step = ("kural_copy_unchecked" if not state.kural_copy_claim_checked
                      else "kalai_media_unclear")
        return
    state.open_gate = kural_res.gate.as_dict()
    state.status = "awaiting_approval"
    state.step = "gate2"


async def _after_publish(state: FlywheelState, stream: EventStream, *, dry_run: bool = True) -> None:
    run_id = state.run_id
    result = await kural.publish(stream, run_id, state.kural_state, dry_run=dry_run)
    label = "publish (dry-run)" if dry_run else "PUBLISH LIVE"
    state.actions.append({"quadrant": "kural", "text": f"{label} to x · ig · linkedin"})

    # manas learns — the closing beat, Context Pack ticks.
    # the question rides along as smriti's deterministic supersede subject —
    # a re-decided question closes the old ruling instead of contradicting it
    learn = await manas.learn(stream, run_id, {"decision": state.verdict.get("decision", ""),
                                               "question": state.question})
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
    return _RUNS.get(run_id) or _restore_run(run_id, project.current_store())
