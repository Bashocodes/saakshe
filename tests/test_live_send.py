"""The arm-real-send AND-gate.

Three keys must all turn before tap-2 fires a real publish: the founder's
per-tap ``arm_real_send`` flag, the deploy-level ``SAAKSHE_ALLOW_LIVE_SEND=1``
env, and a registered channel client. Absent any one, the publish dry-runs —
the hardcoded-safe default the README promises.
"""
from __future__ import annotations

import orchestrator
from common.stream import EventStream
from kural.tools import channels


def _reset_client():
    channels._channel_call = None


async def _run_to_gate2(stream, store):
    summary = await orchestrator.start(question="should we raise pro?", stream=stream, store=store)
    rid = summary["run_id"]
    summary = await orchestrator.approve(rid, "g1", stream=stream, store=store)
    assert summary["step"] == "gate2"
    return rid


async def test_tap2_stays_dry_without_the_env(monkeypatch, grounded_company):
    """arm flag + client registered, but no env → dry-run."""
    monkeypatch.delenv("SAAKSHE_ALLOW_LIVE_SEND", raising=False)
    calls = []
    channels.set_channel_client(lambda action, args: calls.append(action) or {})
    try:
        stream = EventStream()
        rid = await _run_to_gate2(stream, grounded_company)
        summary = await orchestrator.approve(rid, "g2", stream=stream, store=grounded_company,
                                             arm_real_send=True)
        assert summary["status"] == "completed"
        assert not calls, "no env → the real channel must never fire"
        acts = [e for e in stream.all() if e.kind == "action" and e.meta.get("dry_run") is True]
        assert acts, "the publish action must record dry_run=True"
    finally:
        _reset_client()


async def test_tap2_stays_dry_without_the_arm_flag(monkeypatch, grounded_company):
    """env + client, but the founder did not arm the tap → dry-run."""
    monkeypatch.setenv("SAAKSHE_ALLOW_LIVE_SEND", "1")
    calls = []
    channels.set_channel_client(lambda action, args: calls.append(action) or {})
    try:
        stream = EventStream()
        rid = await _run_to_gate2(stream, grounded_company)
        await orchestrator.approve(rid, "g2", stream=stream, store=grounded_company)
        assert not calls
    finally:
        _reset_client()


async def test_tap2_stays_dry_without_a_client(monkeypatch, grounded_company):
    """env + arm flag, but no channel client registered → dry-run (never raises)."""
    monkeypatch.setenv("SAAKSHE_ALLOW_LIVE_SEND", "1")
    _reset_client()
    stream = EventStream()
    rid = await _run_to_gate2(stream, grounded_company)
    summary = await orchestrator.approve(rid, "g2", stream=stream, store=grounded_company,
                                         arm_real_send=True)
    assert summary["status"] == "completed"


async def test_all_three_keys_fire_the_real_channel(monkeypatch, grounded_company):
    """arm flag AND env AND client → the publish reaches the channel adapter,
    and the adapter's returned URLs surface on the stream."""
    monkeypatch.setenv("SAAKSHE_ALLOW_LIVE_SEND", "1")
    calls = []

    def fake_channel(action, args):
        calls.append((action, args))
        return {"urls": {"x": "https://x.com/real/status/123"}}

    channels.set_channel_client(fake_channel)
    try:
        stream = EventStream()
        rid = await _run_to_gate2(stream, grounded_company)
        summary = await orchestrator.approve(rid, "g2", stream=stream, store=grounded_company,
                                             arm_real_send=True)
        assert summary["status"] == "completed"
        assert calls and calls[0][0] == "publish"
        acts = [e for e in stream.all() if e.kind == "action" and e.meta.get("dry_run") is False]
        assert acts and acts[0].meta["urls"]["x"] == "https://x.com/real/status/123"
    finally:
        _reset_client()
