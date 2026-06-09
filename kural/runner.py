"""kural — the uniform quadrant interface (the only mouth).

Public (orchestrator-facing — LOCKED signatures):
  * engage(stream, run_id, master, context_pack) → QuadrantResult
        (status="awaiting_approval", gate = GateRequest(g2, "publish", reversible=False))
  * publish(stream, run_id, state, dry_run=True)  → dict   (post tap-2 side effect)
  * A2A skill: kural.launch_campaign(brief, ...) → dict

``engage`` drives the real ADK ``root_agent`` (Coordinator → ParallelAgent
research → Writer → Claim-Judge gate) and HALTS before publish — exactly as
arivu.runner.deliberate drives arivu's chamber and halts at its gate. The
Claim-Judge is an after-agent LLM-as-judge gate @0.8; nothing unverified passes.
The founder's publish sign-off is the day's second tap — the world-facing,
irreversible act, dry-run by default.
"""

from __future__ import annotations

from typing import Any

from common import a2a, config, project
from common.stream import EventStream

from . import demo_fixtures as fx
from .state import StateKeys
from .tools import analyst, channels
from .util import parse_json

NS = "kural"
_APP = "kural"
_USER = "founder"


# ─── drive the ADK mouth, halt before publish (no side effects) ───────────────
async def _run_engagement(master: dict, context_pack: dict, org: dict | None = None) -> dict[str, Any]:
    """Run the full engagement pipeline; return the final session state as a dict.

    The pipeline ends at the publish gate — nothing is sent or published. Mirrors
    arivu.runner.deliberate: a fresh InMemoryRunner over the assembled root_agent.
    """
    from google.adk.runners import InMemoryRunner
    from google.genai import types
    from .agent import root_agent

    runner = InMemoryRunner(agent=root_agent, app_name=_APP)
    init_state: dict[str, Any] = {
        StateKeys.MASTER: master or {},
        StateKeys.CONTEXT_PACK: context_pack or {},
        StateKeys.BRIEF: (master or {}).get("brief", config.CANON["verdict_decision"]),
        StateKeys.ORG: org or dict(project.current_store().org_for_flywheel()),
    }
    session = await runner.session_service.create_session(
        app_name=_APP, user_id=_USER, state=init_state
    )
    msg = types.Content(role="user", parts=[types.Part(text=init_state[StateKeys.BRIEF])])
    events = []
    async for _event in runner.run_async(user_id=_USER, session_id=session.id, new_message=msg):
        events.append(_event)
    final = await runner.session_service.get_session(
        app_name=_APP, user_id=_USER, session_id=session.id
    )
    state = dict(final.state)
    from common.usage import usage_from_events
    state["_usage"] = usage_from_events(events)
    return state


def _draft_of(state: dict) -> dict:
    d = state.get(StateKeys.DRAFT, {})
    return d if isinstance(d, dict) else parse_json(d)


def _build_post(state: dict, master: dict, context_pack: dict) -> dict:
    """Assemble the verified, gate-ready post from the run's draft + the master."""
    draft = _draft_of(state)
    pack_v = (context_pack or {}).get("version", config.CANON["context_pack_from"])
    variants = draft.get("channel_variants") if draft else None
    formats = master.get("formats", {}) if isinstance(master, dict) else {}
    return {
        "channel": "x+ig+linkedin",
        "as_voice": "founder · plain, warm, names the trade-off",
        "grounded_in": pack_v,
        "headline": draft.get("headline", "") if draft else "",
        "drafts": variants or formats or fx.launch_post(master, context_pack)["drafts"],
        "claim_support": float(state.get(StateKeys.CLAIM_SUPPORT, fx.CLAIM_SUPPORT)),
    }


# ─── engage: the orchestrator-facing entry (LOCKED) ───────────────────────────
async def engage(stream: EventStream, run_id: str, master: dict, context_pack: dict) -> a2a.QuadrantResult:
    pack_v = (context_pack or {}).get("version", "?")
    transcript: list[dict] = []

    # Drive the real ADK pipeline (Coordinator → parallel research → write/judge loop → halt).
    state = await _run_engagement(master, context_pack)
    from common.usage import emit_authoritative
    emit_authoritative(stream, run_id, NS, state.get("_usage"), live=config.is_live())

    # Spine entry — the Claude coordinator's qualify decision.
    qualify = state.get(StateKeys.QUALIFY, {})
    qualify = qualify if isinstance(qualify, dict) else parse_json(qualify)
    stream.emit(run_id, NS, "Envoy Lead",
                f"qualify: {'own it' if qualify.get('worth_engaging', True) else 'hold'} — "
                f"{qualify.get('rationale', 'launch announcement worth saying once')}",
                span="agent_run", model="claude·vertex",
                usage={"input_tokens": 800, "output_tokens": 140})
    transcript.append({"actor": "Envoy Lead [Claude·Vertex]",
                       "text": qualify.get("rationale", "qualify: this is worth saying — own it")})

    # Research fan-out (ran in a ParallelAgent inside root_agent).
    stream.emit(run_id, NS, "Prospect Scout", "scope the consented, topic-fit audience", span="execute_tool")
    stream.emit(run_id, NS, "Market Watcher", "check timing + recent posts (open window)", span="execute_tool")

    stream.emit(run_id, NS, "Outreach Writer",
                f"draft launch post in founder voice, grounded in manas {pack_v}", span="call_llm")
    transcript.append({"actor": "Outreach Writer", "text": f"draft (founder voice · grounded {pack_v})"})

    # Claim-Judge gate — surface every bounded rewrite round, then the verdict.
    history = state.get(StateKeys.CLAIM_HISTORY, []) or []
    for h in history:
        verb = "verified" if h.get("verified") else "re-ground"
        stream.emit(run_id, NS, "Claim Judge",
                    f"round {h.get('round')}: claim_support {h.get('claim_support')} → {verb}",
                    span="agent_run", model="claude·vertex", claim_support=h.get("claim_support"))
        transcript.append({"actor": "Claim Judge [Claude·Vertex]",
                           "text": f"round {h.get('round')}: {h.get('reason')}"})

    support = float(state.get(StateKeys.CLAIM_SUPPORT, 0.0))
    verified = bool(state.get(StateKeys.CLAIM_VERIFIED, False))
    if not history:  # one-shot replay path — still report the final
        passed, reason = (verified, "verified" if verified else "unverified")
        stream.emit(run_id, NS, "Claim Judge", f"after-agent judge: claim_support {support} — {reason}",
                    span="agent_run", model="claude·vertex", claim_support=support)
        transcript.append({"actor": "Claim Judge [Claude·Vertex]", "text": f"claim_support {support} — {reason}"})

    if not verified or state.get(StateKeys.GATE_STATUS) != "awaiting_approval":
        transcript.append({"actor": "Claim Judge [Claude·Vertex]",
                           "text": "unverified — the mouth stays shut (no safe message)"})
        return a2a.QuadrantResult(quadrant=NS, status="no_safe_decision",
                                  output={"claim_support": support}, transcript=transcript)

    # Confirm-before-send + ledger: arm the eligibility/value-cap gate (the actual
    # send fires only on tap-2 publish; here we prove the guard + ledger are live).
    eligible, elig_reason = analyst.send_eligibility(
        recipient="consented-launch-list", consent=True, value_usd=0.0
    )
    stream.emit(run_id, NS, "Email Envoy",
                f"before_tool: {elig_reason}; ledger armed (no double-send)",
                span="agent_run", send_eligible=eligible)
    transcript.append({"actor": "Email Envoy", "text": elig_reason})

    # HALT at the publish gate (tap 2) — never auto-publish.
    post = _build_post(state, master, context_pack)
    gate = a2a.GateRequest(
        gate_id="g2", quadrant=NS, agent="Channel Mouth", gate_kind="publish",
        proposal=f"Publish the Pro → ${config.CANON['verdict_price_to']} launch to x · ig · linkedin",
        reversible=False,
        detail={"claim_support": support, "grounded_in": pack_v, "as_buyer": True},
    )
    stream.gate(run_id, NS, "Channel Mouth", gate.gate_id, gate.proposal,
                gate_kind="publish", reversible=False, claim_support=support)
    transcript.append({"actor": "Channel Mouth», gate", "text": "HALT — awaiting founder publish sign-off (tap 2)"})

    return a2a.QuadrantResult(
        quadrant=NS, status="awaiting_approval", gate=gate,
        output={"post": post, "claim_support": support},
        transcript=transcript,
        state={"post": post, "run_id": run_id},
    )


# ─── publish: the post-tap-2 side effect (LOCKED) ─────────────────────────────
async def publish(stream: EventStream, run_id: str, state: dict, *, dry_run: bool = True) -> dict:
    """Fire the publish on the founder's tap-2 approval. Dry-run by default — the
    world-facing act stays gated. Goes through the no-double-send ledger so a retry
    cannot re-publish."""
    post = (state or {}).get("post") or fx.launch_post({}, {})
    # Ledger the publish itself so an approve-retry cannot double-publish.
    fired, key = analyst.LEDGER.record_send(
        run_id or state.get("run_id", "fw"), post.get("channel", "x+ig+linkedin"),
        "publish", {"dry_run": dry_run},
    )
    result = channels.publish_master(post, dry_run=dry_run)
    result["ledger_fired"] = fired
    result["ledger_key"] = key
    label = "publish (dry-run)" if dry_run else "PUBLISH LIVE"
    note = "" if fired else " · already published (ledger dedupe — no double-send)"
    stream.action(run_id, NS, "Channel Mouth",
                  f"{label} → {post.get('channel')} · OAuth as-buyer · ledger marked{note}",
                  dry_run=dry_run, urls=result["urls"], ledger_fired=fired)
    return result


# ─── A2A skill + agent card ───────────────────────────────────────────────────
def _launch_campaign(brief: str = "", **kw) -> dict:
    """A2A entry: accept a launch and hold it at the founder's publish gate.

    The mouth never publishes on an A2A command alone — the campaign is accepted
    and held; only the founder's tap-2 puts it live.
    """
    return {"accepted": True, "brief": brief, "held_at": "founder publish gate (tap 2)",
            "channel": "x+ig+linkedin", "as_buyer": True}


a2a.register_skill(NS, "launch_campaign", _launch_campaign)
a2a.register_card(NS, {
    "name": "kural",
    "description": "The company's only mouth — outreach, replies, and publishing kalai's approved creative behind the founder's gate. Holds the channel keys; every claim fact-checked.",
    "protocol": "a2a",
    "url": "/api/kural",
    "skills": [
        {"id": "launch_campaign", "name": "Launch a campaign",
         "description": "Publish an approved creative master to the channels, behind the founder's publish sign-off.",
         "tags": ["engagement", "publish", "fact-checked", "human-gated"]},
    ],
})
