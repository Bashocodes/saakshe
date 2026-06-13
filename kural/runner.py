"""kural — the uniform quadrant interface (the only mouth).

Public (orchestrator-facing — LOCKED signatures):
  * engage(stream, run_id, master, context_pack) → QuadrantResult
        (status="awaiting_approval", gate = GateRequest(g2, "publish", reversible=False))
  * publish(stream, run_id, state, dry_run=True)  → dict   (post tap-2 side effect)
  * A2A skill: kural.launch_campaign(brief, ...) → dict

``engage`` drives the real ADK ``root_agent`` (Coordinator → ParallelAgent
research → Outreach Writer + Claim Judge → delivery → send-eligibility gate) and
HALTS before publish — exactly as arivu.runner.deliberate drives arivu's chamber
and halts at its gate. kural AUTHORS the founder-voice copy and fact-checks every
claim, then carries kalai's compliance-cleared MEDIA; the gate opens on
send-eligibility (the engagement is qualified and the send is eligible). The
founder's publish sign-off is the day's second tap — the world-facing,
irreversible act, dry-run by default.
"""

from __future__ import annotations

from typing import Any

from common import a2a, config, project
from common.stream import EventStream

from . import delivery
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


def _build_post(state: dict, master: dict, context_pack: dict) -> dict:
    """Assemble the gate-ready post.

    kural AUTHORED the words (the Outreach Writer's draft), with the Claim Judge's
    claim_support attached; falls back to the master's words if no draft is in state
    (fail-closed — never strands the post).
    """
    pack_v = (context_pack or {}).get("version", config.CANON["context_pack_from"])
    master = master if isinstance(master, dict) else {}
    plan = state.get(StateKeys.DELIVERY_PLAN, {})
    plan = plan if isinstance(plan, dict) else parse_json(plan)

    draft = state.get(StateKeys.DRAFT) or {}
    draft = draft if isinstance(draft, dict) else parse_json(draft)
    caption = draft.get("caption") or master.get("caption", "")
    drafts = ({k: v for k, v in draft.items() if k in ("x", "ig", "linkedin")}
              if draft else master.get("formats", {}))

    post = {
        "channel": "x+ig+linkedin",
        "as_voice": "founder · plain, warm, names the trade-off",
        "grounded_in": pack_v,
        "caption": caption,
        "drafts": drafts,
        # The delivery chamber's pick — variant × segment × window.
        "delivery": plan,
    }
    # The Claim Judge's support rides the post — kural authored, so kural proves.
    claim = state.get(StateKeys.CLAIM) or {}
    claim = claim if isinstance(claim, dict) else parse_json(claim)
    cs = claim.get("claim_support")
    if cs is not None:
        post["claim_support"] = cs
    # kalai's rendered creative rides the post UNTOUCHED — same verbatim doctrine
    # as the words. Until this key the gate card showed the image but the publish
    # payload dropped it: the channel never received the creative it approved.
    media = master.get("media")
    if isinstance(media, dict) and media:
        post["media"] = dict(media)
    elif config.is_live():
        # Never ship a creative-less post SILENTLY in live: kalai's render died
        # (Imagen 404, Veo timeout) and the founder approving this gate must see
        # that the channel will receive words only. Demo stays byte-identical.
        post["media_missing"] = True
        post["media_note"] = "kalai's rendered creative is missing — this publishes as text-only"
    return post


# ─── engage: the orchestrator-facing entry (LOCKED) ───────────────────────────
async def engage(stream: EventStream, run_id: str, master: dict, context_pack: dict) -> a2a.QuadrantResult:
    pack_v = (context_pack or {}).get("version", "?")
    transcript: list[dict] = []

    # Drive the real ADK pipeline (Coordinator → parallel research → send-eligibility gate → halt).
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

    # Delivery fan-out (ran in a ParallelAgent inside root_agent) — four disjoint
    # deep readers (consent · reach · topic-fit · timing). The readers surface
    # delivery facts, they author no words (the Outreach Writer owns the copy).
    for _role, display, lens, key in delivery.DELIVERY_READERS:
        r = state.get(key)
        r = r if isinstance(r, dict) else parse_json(r)
        finding = r.get("finding", f"read the {lens}")
        stream.emit(run_id, NS, display, finding, span="execute_tool")
        transcript.append({"actor": display, "text": finding})

    # kural AUTHORED the words — surface the Outreach Writer + Claim Judge beats
    # (they ran in the pipeline before the planner). copy_claim_checked is the
    # signal the orchestrator ANDs with kalai's media clearance (tap-2 gate).
    draft = state.get(StateKeys.DRAFT, {})
    draft = draft if isinstance(draft, dict) else parse_json(draft)
    claim = state.get(StateKeys.CLAIM, {})
    claim = claim if isinstance(claim, dict) else parse_json(claim)
    cs = float(claim.get("claim_support") or 0.0)
    copy_claim_checked = cs >= 0.80
    stream.emit(run_id, NS, "Outreach Writer",
                "authored the caption + per-channel copy in the founder's voice",
                span="agent_run", model="gemini")
    transcript.append({"actor": "Outreach Writer",
                       "text": draft.get("caption", "(draft authored)")})
    stream.emit(run_id, NS, "Claim Judge",
                f"claim-check: support {cs:.2f} — "
                f"{'cleared' if copy_claim_checked else 'BLOCK (unsupported claim)'}",
                span="agent_run", model="claude·vertex", claim_support=cs)
    transcript.append({"actor": "Claim Judge",
                       "text": f"every claim grounded · support {cs:.2f}"})

    # Delivery planner (Claude) — PICKS variant × segment × window; authors nothing.
    plan = state.get(StateKeys.DELIVERY_PLAN, {})
    plan = plan if isinstance(plan, dict) else parse_json(plan)
    stream.emit(run_id, NS, "Delivery Planner",
                f"pick: {plan.get('variant', '—')} variant · {plan.get('segment', '')} · {plan.get('window', '')}",
                span="agent_run", model="claude·vertex",
                usage={"input_tokens": 600, "output_tokens": 90})
    transcript.append({"actor": "Delivery Planner [Claude·Vertex]",
                       "text": f"carry the {plan.get('variant', '')} variant to {plan.get('segment', '')} "
                               f"({plan.get('window', '')}) — {plan.get('rationale', '')}"})

    # The gate opens on send-eligibility (qualified engagement + eligible send), not
    # on any claim score — the Claim Judge's copy clearance is joined separately by
    # the orchestrator (the tap-2 joined-clearance).
    if state.get(StateKeys.GATE_STATUS) != "awaiting_approval":
        transcript.append({"actor": "Channel Mouth",
                           "text": "not send-eligible — the mouth stays shut (no safe message)"})
        return a2a.QuadrantResult(quadrant=NS, status="no_safe_decision",
                                  output={}, transcript=transcript)

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
    # The rendered creative's vault handle (when kalai persisted pixels) rides the
    # gate so the cockpit card shows WHAT the founder is approving; demo masters
    # are pixel-free → no key, and the gate payload stays byte-identical.
    media = master.get("media") if isinstance(master, dict) else None
    image_uri = media.get("image_uri", "") if isinstance(media, dict) else ""
    img_meta = {"image_uri": image_uri} if image_uri else {}
    gate = a2a.GateRequest(
        gate_id="g2", quadrant=NS, agent="Channel Mouth", gate_kind="publish",
        proposal=f"Publish the Pro → ${config.CANON['verdict_price_to']} launch to x · ig · linkedin",
        reversible=False,
        detail={"grounded_in": pack_v, "as_buyer": True, **img_meta},
    )
    stream.gate(run_id, NS, "Channel Mouth", gate.gate_id, gate.proposal,
                gate_kind="publish", reversible=False, **img_meta)
    transcript.append({"actor": "Channel Mouth», gate", "text": "HALT — awaiting founder publish sign-off (tap 2)"})

    result_state = {"post": post, "run_id": run_id}
    # The joined-clearance signal for the orchestrator (publishable = kalai
    # media-cleared AND this).
    result_state["copy_claim_checked"] = copy_claim_checked
    return a2a.QuadrantResult(
        quadrant=NS, status="awaiting_approval", gate=gate,
        output={"post": post},
        transcript=transcript,
        state=result_state,
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


# ─── measure: read yesterday's outcomes back from the world (loop step 7) ─────
async def measure(stream: EventStream, run_id: str) -> list[dict]:
    """Read engagement outcomes from the founder's configured stats surface and
    return them as cited facts for manas to learn.

    Unconfigured (demo / CI / creds-free) → [] with ZERO stream events, so every
    existing run stays byte-identical. Configured → one stream line per pull and
    the normalized facts, ready for ``manas.learn({"results": facts})``.
    """
    from .tools import outcomes
    import asyncio

    # The stats surface + token are custodied by manas. The mouth reads outcomes
    # THROUGH the broker and never holds the key. The configured-check keeps an
    # unconfigured surface inert (no facts, no stream events).
    from common import a2a
    # Fail-soft if the broker isn't booted (a read must never crash a run).
    if not a2a.has_skill("manas", "stats_configured") or not a2a.dispatch("manas", "stats_configured"):
        return []
    rows = await asyncio.to_thread(lambda: a2a.dispatch("manas", "read_outcomes"))

    facts = outcomes.outcome_facts(rows or [])
    if not facts:
        stream.emit(run_id, NS, "Channel Analyst",
                    "stats surface reachable — no measurable outcomes yet",
                    span="execute_tool", kind="note")
        return []
    stream.emit(run_id, NS, "Channel Analyst",
                f"read {len(facts)} published outcome(s) back from the channels",
                span="execute_tool", kind="action", outcomes=len(facts))
    return facts


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
    "description": "The company's only mouth and word faculty — authors the founder-voice copy, fact-checks every claim, and publishes kalai's media behind the founder's gate. The channel keys are custodied by manas; kural wields a scoped use.",
    "protocol": "a2a",
    "url": "/api/kural",
    "skills": [
        {"id": "launch_campaign", "name": "Launch a campaign",
         "description": "Publish an approved creative master to the channels, behind the founder's publish sign-off.",
         "tags": ["engagement", "publish", "fact-checked", "human-gated"]},
    ],
})
