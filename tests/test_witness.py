"""Witness regression tests — the three bugs the wiring audit found + fixed.

  1. whos_acting_now must surface the working seats, not just the founder's ask
     (the old filter mixed `kind` and `span`).
  2. the refusal must match on WORD BOUNDARIES — "ad" must not fire inside
     "already" / "roadmap" / "headcount" / "lead".
  3. the voice `hello` must advertise the real telemetry tool names.

These pin the witness seam the same way test_flywheel pins the cross-quadrant one.
"""

from __future__ import annotations

from common.stream import EventStream
from witness import agent as witness
from witness import telemetry as tel
from witness import voice as witness_voice


def _seed(s: EventStream, rid: str = "fw_test") -> EventStream:
    s.emit(rid, "saakshe", "founder", 'asks: "Should we?"', span="invocation", kind="span_start")
    s.emit(rid, "saakshe", "witness", "route to arivu", span="agent_run")          # meta, not a seat
    s.emit(rid, "manas", "Mind Keeper", "grounding the topic", span="agent_run")
    s.action(rid, "arivu", "Executor", "commit flag flip")                          # span=execute_tool
    s.emit(rid, "kalai", "Brand-Fidelity scorer", "round 3: 9.1 >= 8.5", span="call_llm")
    return s


# ── bug 1: whos_acting_now surfaces the working seats ─────────────────────────
def test_whos_acting_now_shows_working_seats_not_just_founder():
    out = tel.whos_acting_now(stream=_seed(EventStream()))
    seats = {e["agent"] for e in out["acting"]}
    assert {"Mind Keeper", "Executor", "Brand-Fidelity scorer"} <= seats
    assert "founder" not in seats              # the founder's question is not "acting"
    assert out["count"] >= 3


def test_whos_acting_now_empty_when_nothing_in_flight():
    s = EventStream()
    s.emit("fw", "saakshe", "founder", 'asks: "x"', span="invocation", kind="span_start")
    assert tel.whos_acting_now(stream=s)["count"] == 0


# ── bug 2: word-boundary refusal (no false "ad" inside "already") ──────────────
def test_already_does_not_trigger_false_refusal():
    r = witness.answer("is anyone already waiting on me?", stream=EventStream())
    assert r["refused"] is False
    assert r.get("tool") == "anyone_waiting"


def test_substring_ad_words_not_refused_as_ad_spend():
    s = EventStream()
    for q in ("what's our roadmap?", "how is headcount?", "who's the lead?"):
        r = witness.answer(q, stream=s)
        # may still fall through to the honest fallback, but NOT via the ad-spend bucket
        assert "I won't invent a number I can't see" not in r["text"], q


def test_genuine_ad_spend_still_refuses():
    s = EventStream()
    for q in ("what's our ad spend today?", "how much on ads?", "advertising budget?"):
        r = witness.answer(q, stream=s)
        assert r["refused"] is True, q
        assert "no bucket" in r["text"], q


# ── bug 3: voice hello advertises the real tool names ─────────────────────────
def test_voice_hello_tool_names_are_real_telemetry_functions():
    assert witness_voice._TOOL_NAMES == [
        "anyone_waiting", "cost_today", "whats_reversible", "what_learned", "whos_acting_now"]
    for name in witness_voice._TOOL_NAMES:
        assert callable(getattr(tel, name)), name


# ─── tenant-stream regression: the live agent's tools read the CALLER's stream ─
def test_live_witness_tools_read_the_passed_stream_not_the_global():
    """build_witness_agent(stream, run_id) must close its telemetry tools over the
    tenant stream it was handed — a gate open in that stream is reported even when
    the module-global STREAM is empty (the multi-tenant contract)."""
    from common.stream import EventStream
    from witness import agent as wagent

    tenant = EventStream()
    tenant.gate("run-t", "arivu", "Chair", "g1", "raise Pro",
                gate_kind="decision", reversible=True)

    built = wagent.build_witness_agent(tenant, "run-t")
    tools = {t.func.__name__: t.func for t in built.tools}
    out = tools["anyone_waiting"]()
    assert out["waiting"], "the tenant stream's open gate must be visible"
    assert out["gates"][0]["gate_id"] == "g1"

    # And the same tool over a fresh (empty) stream sees nothing — proving the
    # closure binds per-call state, not the module global.
    empty_built = wagent.build_witness_agent(EventStream(), "run-t")
    empty_tools = {t.func.__name__: t.func for t in empty_built.tools}
    assert not empty_tools["anyone_waiting"]()["waiting"]
