"""End-to-end engagement test, in demo mode (full ADK orchestration, replayed LLM).

The whole pipeline runs — Coordinator (Claude) qualify, the ParallelAgent research
fan-out, the Writer ↔ Claim-Judge LoopAgent (re-grounding once before it verifies),
the publish gate — and HALTS at g2 awaiting the founder's tap-2. The publish is the
separate, human-approved step, dry-run by default and only real when dry_run=False.
"""

from __future__ import annotations

import pytest

from common import a2a, config
from common.stream import EventStream
from kural import runner
from kural.state import StateKeys
from kural.tools import analyst, channels

_MASTER = {
    "asset_id": "asset-1", "brief": config.CANON["verdict_decision"],
    "formats": {"x": "x copy", "ig": "ig copy", "linkedin": "li copy"},
    "fidelity_score": config.CANON["fidelity_pass"], "compliance": "cleared", "spend_usd": 1.2,
}
_PACK = {"version": config.CANON["context_pack_from"], "topic": "pricing", "grounded": True}


# ─── separation fix #1: kural carries kalai's words untouched ─────────────────
async def test_kural_publishes_kalai_words_untouched():
    master = {"asset_id": "a1", "brief": "b", "caption": "KALAI CAPTION",
              "formats": {"x": "KALAI X", "ig": "KALAI IG", "linkedin": "KALAI LI"},
              "fidelity_score": 9.1, "compliance": "cleared", "spend_usd": 1.2}
    res = await runner.engage(EventStream(), "fw", master, _PACK)
    post = res.state["post"] if "post" in res.state else res.output
    # kural carried kalai's EXACT words — authored nothing of its own.
    assert post["drafts"] == master["formats"]
    assert "claim_support" not in post            # the judge is gone
    assert res.status == "awaiting_approval"       # still halts at tap-2


async def test_no_writer_or_judge_in_transcript():
    res = await runner.engage(EventStream(), "fw", _MASTER, _PACK)
    actors = " ".join(l["actor"] for l in res.transcript)
    assert "Outreach Writer" not in actors and "Claim Judge" not in actors
    assert "Scout" in actors or "Delivery" in actors


# ─── the ADK pipeline runs and halts at the publish gate ──────────────────────
async def test_run_engagement_reaches_send_eligible_publish_gate():
    state = await runner._run_engagement(_MASTER, _PACK)
    # Halts at the gate awaiting a human — nothing published. The gate opened on
    # send-eligibility (qualified engagement + eligible send), not a claim score.
    assert state[StateKeys.GATE_STATUS] == "awaiting_approval"
    # The Claude coordinator qualified the engagement (spine entry).
    qualify = state[StateKeys.QUALIFY]
    qualify = qualify if isinstance(qualify, dict) else runner.parse_json(qualify)
    assert qualify.get("worth_engaging") is True


# ─── engage() returns the locked QuadrantResult and never auto-publishes ───────
async def test_engage_halts_at_g2_publish_gate_never_auto_publishes():
    s = EventStream()
    res = await runner.engage(s, "run1", _MASTER, _PACK)
    assert isinstance(res, a2a.QuadrantResult)
    assert res.status == "awaiting_approval"
    assert res.gate is not None
    assert res.gate.gate_id == "g2"
    assert res.gate.gate_kind == "publish"
    assert res.gate.reversible is False
    # A gate row was raised; NO action row published anything during engage.
    assert any(e.kind == "gate" and e.meta["gate_id"] == "g2" for e in s.all())
    assert not any(e.kind == "action" and "PUBLISH" in e.text.upper() for e in s.all())
    # The carry-state hands the verified post to publish().
    assert "post" in res.state


async def test_engage_emits_the_seat_transcript():
    s = EventStream()
    res = await runner.engage(s, "run2", _MASTER, _PACK)
    actors = " ".join(t["actor"] for t in res.transcript)
    # The post-separation seats: qualify, the two scouts, the channel desk. No
    # Outreach Writer / Claim Judge — kural authors nothing.
    for seat in ("Envoy Lead", "Prospect Scout", "Market Watcher", "Email Envoy", "Channel Mouth"):
        assert seat in actors
    assert "Outreach Writer" not in actors and "Claim Judge" not in actors
    # The sealed price appears in the gate proposal (never a forbidden number).
    proposal = next(e for e in s.all() if e.kind == "gate").text
    assert str(config.CANON["verdict_price_to"]) in proposal


# ─── publish(): dry-run by default; only real when dry_run=False ──────────────
async def test_publish_is_dry_run_by_default(monkeypatch):
    monkeypatch.setattr(analyst, "LEDGER", analyst.SendLedger())
    s = EventStream()
    res = await runner.engage(s, "run3", _MASTER, _PACK)
    out = await runner.publish(s, "run3", res.state)   # default dry_run=True
    assert out["dry_run"] is True
    assert all("DRAFT" in url for url in out["urls"].values())
    assert out["ledger_fired"] is True


async def test_publish_live_only_when_dry_run_false(monkeypatch):
    monkeypatch.setattr(analyst, "LEDGER", analyst.SendLedger())
    s = EventStream()
    res = await runner.engage(s, "run4", _MASTER, _PACK)

    # A real publish requires a registered channel client — otherwise it must raise
    # (no silent fake). Register a fake to prove the live path is taken.
    calls = {}
    def fake_client(action, args):
        calls["action"] = action
        return {"urls": {"x": "https://x.com/LIVE", "ig": "https://instagram.com/LIVE", "linkedin": "https://linkedin.com/LIVE"}}
    channels.set_channel_client(fake_client)
    try:
        out = await runner.publish(s, "run4", res.state, dry_run=False)
    finally:
        channels.set_channel_client(None)
    assert out["dry_run"] is False
    assert calls["action"] == "publish"
    assert all("LIVE" in url for url in out["urls"].values())


async def test_publish_ledger_prevents_double_publish(monkeypatch):
    monkeypatch.setattr(analyst, "LEDGER", analyst.SendLedger())
    s = EventStream()
    res = await runner.engage(s, "run5", _MASTER, _PACK)
    first = await runner.publish(s, "run5", res.state)
    second = await runner.publish(s, "run5", res.state)   # an approve-retry
    assert first["ledger_fired"] is True
    assert second["ledger_fired"] is False                # no double-publish


# ─── not send-eligible: the mouth stays shut, no gate ─────────────────────────
async def test_not_send_eligible_yields_no_safe_decision(monkeypatch):
    """If the gate never opens (engagement not qualified / not send-eligible),
    engage returns no_safe_decision and raises NO publish gate — the mouth
    refuses to say it."""
    async def fake_run(master, context_pack, org=None):
        return {
            StateKeys.GATE_STATUS: "no_safe_message",
            StateKeys.QUALIFY: {"worth_engaging": False},
        }
    monkeypatch.setattr(runner, "_run_engagement", fake_run)
    s = EventStream()
    res = await runner.engage(s, "run6", _MASTER, _PACK)
    assert res.status == "no_safe_decision"
    assert res.gate is None
    assert not any(e.kind == "gate" for e in s.all())


# ─── A2A skill: accept but hold at the founder gate (never publishes on command) ─
def test_a2a_launch_campaign_holds_at_gate():
    out = a2a.dispatch("kural", "launch_campaign", "launch the Pro pricing change")
    assert out["accepted"] is True
    assert "publish gate" in out["held_at"]
