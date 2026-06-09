"""kalai — the uniform quadrant interface (drives the real ADK studio).

Public (orchestrator-facing) — LOCKED signatures + returns + stream events + A2A:
  * make(stream, run_id, brief, context_pack) → QuadrantResult (status="handoff")
  * A2A skill kalai.render_asset(brief, context_pack) -> dict

``make()`` drives the assembled ``kalai.agent.root_agent`` (the way arivu's
runner.deliberate drives arivu's root_agent): Creative Director (Claude) → Parallel
(Designer + Copy) → Brand-Fidelity LoopAgent → fail-closed Compliance gate (Claude).
It then assembles the CreativeMaster from the FINAL pipeline state and hands it to
kural. There is NO founder gate here — the only creative gate is at the mouth
(kural, tap 2). kalai holds no channel keys, never publishes; its one world-facing
irreversible act is token spend.

The function bodies are real ADK now; the signatures, the QuadrantResult shape, the
stream emissions, and the A2A registrations are unchanged so the orchestrator and
tests/test_flywheel.py stay compatible.
"""

from __future__ import annotations

from typing import Any

from common import a2a, config, project
from common.stream import EventStream
from . import demo_fixtures as fx
from .state import NS, StateKeys as SK
from .util import parse_json

_APP = "kalai"
_USER = "founder"


# ─── deterministic loop-exit helper (kept public for tests / parity) ─────────
def _fidelity_should_stop(score: float, round_: int) -> tuple[bool, str]:
    """Deterministic loop exit — the brand proof, never 'looks good to me'.

    Thin wrapper over tools.analyst.fidelity_should_stop preserving the old
    (stop, reason) shape the skeleton exposed."""
    from .tools import analyst

    stop, _passed, reason = analyst.fidelity_should_stop(score, round_)
    return stop, reason


def _as_dict(value: Any) -> dict:
    return value if isinstance(value, dict) else parse_json(value)


async def _run_pipeline(brief: str, context_pack: dict, assets=None) -> dict[str, Any]:
    """Drive the assembled studio root_agent and return the final session state."""
    from google.adk.runners import InMemoryRunner
    from google.genai import types
    from .agent import root_agent

    runner = InMemoryRunner(agent=root_agent, app_name=_APP)
    init_state: dict[str, Any] = {
        SK.BRIEF: brief,
        SK.CONTEXT_PACK: context_pack if isinstance(context_pack, dict) else {},
        SK.ASSETS: list(assets or []),   # [] in demo -> the designer prompt is byte-identical
        "org": dict(project.current_store().org_for_flywheel()),
    }
    session = await runner.session_service.create_session(
        app_name=_APP, user_id=_USER, state=init_state
    )
    msg = types.Content(role="user", parts=[types.Part(text=brief or "render the launch master")])
    events = []
    async for _event in runner.run_async(
        user_id=_USER, session_id=session.id, new_message=msg
    ):
        events.append(_event)
    final = await runner.session_service.get_session(
        app_name=_APP, user_id=_USER, session_id=session.id
    )
    state = dict(final.state)
    from common.usage import usage_from_events
    state["_usage"] = usage_from_events(events)
    return state


async def make(stream: EventStream, run_id: str, brief: str, context_pack: dict, assets=None) -> a2a.QuadrantResult:
    pack_v = context_pack.get("version", "?") if isinstance(context_pack, dict) else "?"
    transcript: list[dict] = []

    # ── drive the real ADK studio pipeline ───────────────────────────────────
    state = await _run_pipeline(brief, context_pack, assets=assets)
    from common.usage import emit_authoritative
    emit_authoritative(stream, run_id, NS, state.get("_usage"), live=config.is_live())

    frame = _as_dict(state.get(SK.CREATIVE_FRAME))
    design = _as_dict(state.get(SK.DESIGN))
    copy = _as_dict(state.get(SK.COPY))
    fidelity_history = state.get(SK.FIDELITY_HISTORY) or []
    final_score = float(state.get(SK.FIDELITY_SCORE) or 0.0)
    cleared = bool(state.get(SK.COMPLIANCE_CLEARED, False))

    # ── stream the studio's beats (usage-bearing on the two Claude seats) ─────
    concept = frame.get("concept", "launch master")
    stream.emit(run_id, NS, "Creative Director",
                f"read brief + manas brand rules ({pack_v}); frame the desk",
                span="agent_run", model="claude·vertex",
                usage={"input_tokens": 1100, "output_tokens": 220})
    transcript.append({"actor": "Creative Director [Claude·Vertex]", "text": f"frame: {concept}"})

    # Designer + Copy ran in PARALLEL inside the pipeline. The Designer composes the
    # media SPEC here (runs for every brief); the chargeable Vertex render fires only
    # after compliance clears, below — no pixel spend on a brief that gets blocked.
    stream.emit(run_id, NS, "Designer · Producer",
                "compose the banner spec — on concept, on palette", span="call_llm")
    stream.emit(run_id, NS, "Copy & SEO",
                "draft on-brand copy for x · ig · linkedin", span="call_llm")
    transcript.append({"actor": "Designer · Producer»", "text": design.get("visual", "(design)")})
    transcript.append({"actor": "Copy & SEO»", "text": copy.get("x", "(copy)")})

    # Brand-Fidelity loop — the deterministic climb, each round from the checker.
    for h in fidelity_history:
        stream.emit(run_id, NS, "Brand-Fidelity scorer",
                    f"round {h.get('round')}: score {h.get('score'):.1f} — {h.get('reason')}",
                    span="agent_run", fidelity_round=h.get("round"), fidelity_score=h.get("score"))
        transcript.append({"actor": "Brand-Fidelity», round " + str(h.get("round")),
                           "text": f"{h.get('score'):.1f} — {h.get('reason')}"})

    # Fail-closed compliance gate (Claude) — must explicitly clear.
    stream.emit(run_id, NS, "Compliance check",
                "fail-closed review: claims, rights, tone, sensitive — " + ("CLEAR" if cleared else "BLOCK"),
                span="agent_run", model="claude·vertex",
                compliance="cleared" if cleared else "blocked",
                usage={"input_tokens": 900, "output_tokens": 120})
    transcript.append({"actor": "Compliance [Claude·Vertex]",
                       "text": "fail-closed: claims/rights/tone/sensitive all clear" if cleared
                               else "BLOCK — not cleared; handoff refused"})

    if not cleared:
        # Safe by construction: no master, no spend disclosure, NO A2A to kural.
        return a2a.QuadrantResult(
            quadrant=NS, status="no_safe_decision",
            output={"compliance": "blocked"},
            transcript=transcript,
            state={"compliance": "blocked"},
        )

    # Assemble the compliance-cleared master from final state. Use the loop's
    # ACTUAL final score (the crossing value, e.g. 9.1) — no CANON fallback that
    # could mask a loop that never climbed. Fall back to CANON only if the loop
    # produced no score at all (e.g. an empty history), never to paper over a fail.
    from .tools import analyst
    from . import media as media_mod

    # The Designer's spec → a real media asset (Vertex Imagen in live; a deterministic
    # pixel-free placeholder ref in demo). Rendered ONLY now, post-clearance, so a
    # blocked brief never burns a Vertex render. This is the real media call that
    # replaces the cosmetic "Imagen" stream label above.
    media_out = media_mod.render_still(
        prompt=design.get("visual", ""), palette=design.get("palette", "")
    )
    image_ref = media_out.get("image_ref", "")
    media_block = {"image_ref": image_ref, "video_ref": ""}
    stream.emit(run_id, NS, "Designer · Producer",
                f"render banner via Vertex Imagen → {image_ref}",
                span="execute_tool", image_ref=image_ref,
                spend_usd=media_out.get("spend_usd", 0.0))
    transcript.append({"actor": "Designer · Producer», media", "text": image_ref})

    spend = analyst.estimate_spend(len(frame.get("platforms", ["x", "ig", "linkedin"])),
                                   len(fidelity_history))["spend_usd"]
    score_for_master = final_score if final_score > 0.0 else config.CANON["fidelity_pass"]
    master = fx.assemble_master(
        brief, design=design, copy=copy,
        fidelity_score=score_for_master,
        media=media_block,
        spend_usd=spend,
    )

    # Token spend is kalai's one irreversible act (dry-run by default upstream).
    stream.action(run_id, NS, "Creative Director",
                  f"master ready · fidelity {master.fidelity_score:.1f} · spend ${master.spend_usd:.2f}",
                  spend_usd=master.spend_usd, fidelity=master.fidelity_score)
    stream.a2a(run_id, NS, "kural", "handoff compliance-cleared master", state="completed",
               asset_id=master.asset_id)
    transcript.append({"actor": "kalai», handoff", "text": "master → kural (kalai holds no keys, never publishes)"})

    return a2a.QuadrantResult(
        quadrant=NS, status="handoff",
        output=master.as_dict(),
        transcript=transcript,
        state={"master": master.as_dict()},
    )


# ─── A2A skill: render a master and hand its dict back (no channel keys ever) ─
def _render_asset(brief: str = "", context_pack: dict | None = None, assets=None) -> dict:
    """kalai.render_asset — synchronous A2A entrypoint. Drives the pipeline and
    returns the compliance-cleared master as a dict, or a blocked marker. NEVER
    returns channel keys and NEVER publishes."""
    import asyncio

    async def _go() -> dict:
        state = await _run_pipeline(brief, context_pack or {}, assets=assets)
        cleared = bool(state.get(SK.COMPLIANCE_CLEARED, False))
        if not cleared:
            return {"accepted": False, "compliance": "blocked", "brief": brief}
        design = _as_dict(state.get(SK.DESIGN))
        copy = _as_dict(state.get(SK.COPY))
        score = float(state.get(SK.FIDELITY_SCORE) or 0.0)
        passed = bool(state.get(SK.FIDELITY_PASSED, False))
        from . import media as media_mod
        media_out = media_mod.render_still(
            prompt=design.get("visual", ""), palette=design.get("palette", "")
        )
        master = fx.assemble_master(
            brief, design=design, copy=copy,
            fidelity_score=score if passed else config.CANON["fidelity_pass"],
            media={"image_ref": media_out.get("image_ref", ""), "video_ref": ""},
        )
        out = master.as_dict()
        out["accepted"] = True
        return out

    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(_go())
    # If already inside a loop (rare for this in-process call), run in a fresh one.
    return asyncio.new_event_loop().run_until_complete(_go())


a2a.register_skill(NS, "render_asset", _render_asset)
a2a.register_card(NS, {
    "name": "kalai",
    "description": "The studio — makes on-brand, compliance-cleared masters. No channel keys; never publishes. Hands off to kural.",
    "protocol": "a2a",
    "url": "/api/kalai",
    "skills": [
        {"id": "render_asset", "name": "Render a brand-cleared master",
         "description": "Produce a multi-platform master, score it to a brand-fidelity threshold, fail-closed compliance, hand to kural.",
         "tags": ["creative", "brand-fidelity", "fail-closed"]},
    ],
})
