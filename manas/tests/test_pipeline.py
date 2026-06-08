"""End-to-end memory pipeline test, in demo mode (full ADK orchestration, replayed
LLM). The whole SequentialAgent runs — Mind-Keeper route, the four imbibers in
PARALLEL, the Curator verify-before-commit LOOP, and the commit — and the Context
Pack ticks v14 -> v15 only when the deterministic groundedness check clears the bar.
"""

from __future__ import annotations

from manas import agent, runner, state as st
from manas.tools import curator
from common import config, project


# ─── the real pipeline drives the curate loop to a grounded commit ───────────
async def test_pipeline_commits_when_grounded():
    out = await runner._run_pipeline({"decision": "Raise Pro to $34"})
    # The loop ran multiple rounds (first pass under-grounded, then revised).
    rounds = out["rounds"]
    assert len(rounds) >= 1
    # It committed on the round that crossed the deterministic groundedness bar.
    assert out["committed"] is True
    assert out["commit_status"] == "committed"
    assert out["groundedness"] >= config.GROUNDING_THRESHOLD
    # The arc is real: an early round is below the bar, a later round crosses it.
    assert rounds[0]["groundedness"] < config.GROUNDING_THRESHOLD
    assert rounds[-1]["groundedness"] >= config.GROUNDING_THRESHOLD
    # And the loop NEVER reports a committed round below the bar.
    for h in rounds:
        if h["committed"]:
            assert h["groundedness"] >= config.GROUNDING_THRESHOLD


async def test_curate_loop_exits_on_threshold_not_max_rounds():
    """The exit is the numeric threshold (groundedness >= 0.80), proven by the
    loop stopping before exhausting MAX_CURATE_ROUNDS."""
    out = await runner._run_pipeline({"decision": "Raise Pro to $34"})
    assert len(out["rounds"]) < config.MAX_CURATE_ROUNDS + 1
    assert out["rounds"][-1]["committed"] is True


# ─── learn() preserves the locked interface while driving the real pipeline ──
async def test_learn_ticks_pack_and_returns_quadrant_result():
    from common.stream import EventStream

    s = EventStream()
    res = await runner.learn(s, "r1", {"decision": "Raise Pro to $34"})
    # Locked return shape: a completed QuadrantResult with a real store version tick
    # (v0 -> v1 from an empty store), NOT a canned v14 -> v15 pin.
    assert res.quadrant == "manas"
    assert res.status == "completed"
    assert res.output["context_pack_from"] != res.output["context_pack_to"]  # the tick
    assert res.output["context_pack_to"] == project.STORE.version
    assert res.output["context_pack_to"].startswith("v")


async def test_learn_emits_witness_readable_commit():
    """The witness reads context_pack_to off the Curator's commit action — the
    flywheel's 'what did manas learn?' answer depends on this emission."""
    from common.stream import EventStream

    s = EventStream()
    await runner.learn(s, "r1", {"decision": "Raise Pro to $34"})
    actions = [e for e in s.all() if e.kind == "action"]
    commit = next(e for e in actions if e.meta.get("context_pack_to"))
    assert commit.meta["context_pack_to"] == project.STORE.version
    # At least one call_llm carries token usage (witness cost aggregation).
    assert any(isinstance(e.meta.get("usage"), dict) for e in s.all())


# ─── the curator never commits a contradictory memory (negative safety) ──────
async def test_curator_never_commits_a_contradiction(monkeypatch):
    """Plant a contradictory claim set into the Curator's synthesis; the
    deterministic check must gate groundedness to 0.0 and the loop must roll back
    to 'no safe commit' — the Curator can never write a self-contradicting memory.
    """
    import json as _json
    import manas.demo_fixtures as fx

    contradictory = {
        "claims": [
            {"claim": "we grandfather existing subscribers", "source": "s1"},
            {"claim": "we never grandfather existing subscribers", "source": "s2"},
        ],
        "contradictions": ["grandfather flip"],
        "groundedness": 0.95,                 # the model CLAIMS high — must be ignored
        "version_to": config.CANON["context_pack_to"],
        "note": "planted contradiction",
    }

    def _poisoned(role, llm_request=None):
        if role == "curator":
            return _json.dumps(contradictory)
        return fx.scripted_payload(role, llm_request)

    # Re-register the poisoned resolver under the manas namespace for this test.
    from common import models
    monkeypatch.setitem(models._RESOLVERS, "manas", _poisoned)

    out = await runner._run_pipeline({"decision": "anything"})
    # Every round's groundedness is gated to 0.0 by the contradiction, regardless
    # of the model's self-claimed 0.95.
    assert all(h["groundedness"] == 0.0 for h in out["rounds"])
    # The loop exhausts its rounds and rolls back — it does NOT commit.
    assert out["committed"] is False
    assert out["commit_status"] == "no_safe_commit"
    assert len(out["rounds"]) == config.MAX_CURATE_ROUNDS


# ─── seats: exactly two Claude, the rest Gemini ──────────────────────────────
def test_exactly_two_claude_seats():
    """The chamber wires exactly the two high-stakes Claude-via-Vertex seats:
    the Memory Curator and the Founder Voice. Everything else is Gemini."""
    # Built via models.claude(...) which in demo returns a ScriptedLlm whose role
    # we can read back from the assembled agents.
    curator_agent = agent.build_root_agent().sub_agents[2].sub_agents[0]  # curate_loop -> curator
    voice_agent = agent.build_founder_voice_agent()
    assert curator_agent.name == "memory_curator"
    assert voice_agent.name == "founder_voice"
    # And the two Gemini tiers exist: Mind Keeper (pro) + four imbibers (flash).
    root = agent.build_root_agent()
    assert root.sub_agents[0].name == "mind_keeper"
    imbibers = root.sub_agents[1].sub_agents
    assert len(imbibers) == 4
    assert {a.name for a in imbibers} == {
        "imbiber_repo", "imbiber_web", "imbiber_docs", "imbiber_social"
    }
