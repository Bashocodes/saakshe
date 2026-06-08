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


# ─── the ADK pipeline runs and halts at the publish gate ──────────────────────
async def test_run_engagement_reaches_verified_publish_gate():
    state = await runner._run_engagement(_MASTER, _PACK)
    # Halts at the gate awaiting a human — nothing published.
    assert state[StateKeys.GATE_STATUS] == "awaiting_approval"
    # The claim verified at/above the bar — and at the sealed canon support.
    assert state[StateKeys.CLAIM_VERIFIED] is True
    assert float(state[StateKeys.CLAIM_SUPPORT]) >= config.CLAIM_THRESHOLD
    assert float(state[StateKeys.CLAIM_SUPPORT]) == config.CANON["claim_support"]
    # The Claude coordinator qualified the engagement (spine entry).
    qualify = state[StateKeys.QUALIFY]
    qualify = qualify if isinstance(qualify, dict) else runner.parse_json(qualify)
    assert qualify.get("worth_engaging") is True


async def test_claim_loop_re_grounds_before_it_verifies():
    """The bounded rewrite loop genuinely iterates: round 1 falls short, round 2
    verifies — never a one-shot 'looks good'. The midpoint is below the bar and is
    NEVER a forbidden value."""
    state = await runner._run_engagement(_MASTER, _PACK)
    history = state[StateKeys.CLAIM_HISTORY]
    assert len(history) == 2
    assert history[0]["verified"] is False and history[0]["claim_support"] < config.CLAIM_THRESHOLD
    assert history[1]["verified"] is True and history[1]["claim_support"] == config.CANON["claim_support"]
    for h in history:
        assert h["claim_support"] not in config.FORBIDDEN["numbers"]


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
    assert res.output["claim_support"] == config.CANON["claim_support"]
    # A gate row was raised; NO action row published anything during engage.
    assert any(e.kind == "gate" and e.meta["gate_id"] == "g2" for e in s.all())
    assert not any(e.kind == "action" and "PUBLISH" in e.text.upper() for e in s.all())
    # The carry-state hands the verified post to publish().
    assert "post" in res.state


async def test_engage_emits_the_seat_transcript():
    s = EventStream()
    res = await runner.engage(s, "run2", _MASTER, _PACK)
    actors = " ".join(t["actor"] for t in res.transcript)
    for seat in ("Envoy Lead", "Outreach Writer", "Claim Judge", "Email Envoy", "Channel Mouth"):
        assert seat in actors
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


# ─── unverified path: the mouth stays shut, no gate ───────────────────────────
async def test_unverified_message_yields_no_safe_decision(monkeypatch):
    """If the Claim-Judge never verifies, engage returns no_safe_decision and
    raises NO publish gate — the mouth refuses to say it."""
    async def fake_run(master, context_pack, org=None):
        return {
            StateKeys.GATE_STATUS: "no_safe_message",
            StateKeys.CLAIM_VERIFIED: False,
            StateKeys.CLAIM_SUPPORT: 0.62,   # below the bar; never surfaced as canon
            StateKeys.CLAIM_HISTORY: [
                {"round": 1, "claim_support": 0.62, "verified": False, "reason": "below bar"},
                {"round": 2, "claim_support": 0.62, "verified": False, "reason": "no safe message"},
            ],
            StateKeys.QUALIFY: {"worth_engaging": True},
            StateKeys.DRAFT: {},
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
