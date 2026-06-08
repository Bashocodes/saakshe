"""End-to-end walking-skeleton test: the whole flywheel, both gates, the witness.

This is the integration guard the deep builds (Phase B) must keep green. It pins
the cross-quadrant SEAMS — not the per-quadrant internals — so deepening a
quadrant behind its interface can't silently break the company.
"""

from __future__ import annotations

import pytest

from common import config, project
from common.stream import EventStream
import orchestrator
from witness import agent as witness


@pytest.fixture
def stream(monkeypatch):
    """A fresh isolated stream per test (so cost/gate assertions are clean)."""
    s = EventStream()
    monkeypatch.setattr(orchestrator, "STREAM", s, raising=False)
    # orchestrator.start/approve default their stream arg at call time from the
    # module global, so patch the names the default binds to.
    return s


async def _run_full(s):
    started = await orchestrator.start(stream=s)
    rid = started["run_id"]
    g1 = await orchestrator.approve(rid, "g1", stream=s)
    g2 = await orchestrator.approve(rid, "g2", stream=s)
    return started, g1, g2, rid


# ─── the flywheel ────────────────────────────────────────────────────────────
async def test_flywheel_two_gates_and_completes(stream):
    started, g1, g2, rid = await _run_full(stream)

    assert started["status"] == "awaiting_approval"
    assert started["open_gate"]["gate_id"] == "g1"
    assert started["open_gate"]["gate_kind"] == "decision"
    assert str(config.CANON["verdict_price_to"]) in started["verdict"]["decision"]

    assert g1["status"] == "awaiting_approval"
    assert g1["open_gate"]["gate_id"] == "g2"
    assert g1["open_gate"]["gate_kind"] == "publish"

    assert g2["status"] == "completed"
    assert {a["quadrant"] for a in g2["actions"]} == {"arivu", "kural", "manas"}


async def test_exactly_two_gates_both_resolved(stream):
    _, _, _, rid = await _run_full(stream)
    gate_events = [e for e in stream.all() if e.kind == "gate"]
    assert {e.meta["gate_id"] for e in gate_events} == {"g1", "g2"}
    # both resolved → the derived queue is empty at the end
    assert stream.open_gates(rid) == []


async def test_gate_queue_is_live(stream):
    started = await orchestrator.start(stream=stream)
    rid = started["run_id"]
    assert [g["gate_id"] for g in stream.open_gates(rid)] == ["g1"]
    await orchestrator.approve(rid, "g1", stream=stream)
    assert [g["gate_id"] for g in stream.open_gates(rid)] == ["g2"]
    await orchestrator.approve(rid, "g2", stream=stream)
    assert stream.open_gates(rid) == []


async def test_cannot_skip_or_double_tap(stream):
    started = await orchestrator.start(stream=stream)
    rid = started["run_id"]
    with pytest.raises(RuntimeError):
        await orchestrator.approve(rid, "g2", stream=stream)   # wrong gate
    await orchestrator.approve(rid, "g1", stream=stream)
    await orchestrator.approve(rid, "g2", stream=stream)
    with pytest.raises(RuntimeError):
        await orchestrator.approve(rid, "g2", stream=stream)   # already done


# ─── the manas A2A hub ───────────────────────────────────────────────────────
def test_manas_grounds_and_refuses_out_of_corpus(grounded_company):
    from common import a2a
    pack = a2a.dispatch("manas", "get_founder_context", "pricing")
    assert pack["grounded"] and any("grandfather" in f["claim"].lower() for f in pack["facts"])
    out = a2a.dispatch("manas", "get_founder_context", "series-c-valuation")
    assert out["grounded"] is False and out["facts"] == []

    grounded = a2a.dispatch("manas", "ask_founder_voice", "do we grandfather existing subscribers?")
    assert grounded["refused"] is False and grounded["citations"]
    refused = a2a.dispatch("manas", "ask_founder_voice", "what's our 2027 series-A valuation?")
    assert refused["refused"] is True and refused["citations"] == []


# ─── the witness (the refusal is the agent) ──────────────────────────────────
async def test_witness_answers_and_refuses(stream):
    _, _, _, rid = await _run_full(stream)

    waiting = witness.answer("anyone waiting on me?", rid, stream)
    assert waiting["refused"] is False and waiting["waiting"] is False  # both gates cleared

    cost = witness.answer("what did today cost?", rid, stream)
    assert cost["refused"] is False and cost["llm_calls"] >= 1

    learned = witness.answer("what did manas learn?", rid, stream)
    # The flywheel's learn() ticks the REAL store version (no canned v15 pin).
    assert learned["learned"] is True
    assert learned["context_pack"] == project.STORE.version

    refusal = witness.answer("how much did we spend on ads today?", rid, stream)
    assert refusal["refused"] is True and "ads" not in refusal["text"].lower().split("bucket")[0]


# ─── the sealed canon (live + canned tell one story) ─────────────────────────
async def test_no_forbidden_numbers_as_canon(stream):
    started, _, _, rid = await _run_full(stream)
    # The verdict the orchestrator surfaces must carry the sealed finals, never midpoints.
    assert started["verdict"]["confidence"] == config.CANON["verdict_confidence"]
    # The gate proposal (what the founder sees) must show the final defensibility, not 0.62/0.81.
    proposal = next(e for e in stream.all() if e.kind == "gate" and e.meta["gate_id"] == "g1").text
    for bad in config.FORBIDDEN["numbers"]:
        assert str(bad) not in proposal
    assert str(config.CANON["defensibility_final"]) in proposal
