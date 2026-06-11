"""Pin the outcome reader — loop step 7 (measure) at the kural edge.

The stats surface is pure configuration (like the webhook adapter): unset env →
zero network, zero facts, zero stream noise, so demo/CI stay byte-identical.
Configured → rows normalize into cited facts (no number, no fact)."""

from __future__ import annotations

import asyncio

import pytest

from common.stream import EventStream
from kural import runner
from kural.tools import outcomes


# ─── unconfigured = inert (the demo byte-identity guarantee) ──────────────────
def test_pull_returns_empty_without_env(monkeypatch):
    monkeypatch.delenv("SAAKSHE_CHANNEL_STATS_URL", raising=False)
    assert outcomes.pull_outcomes() == []


def test_measure_unconfigured_emits_nothing(monkeypatch):
    monkeypatch.delenv("SAAKSHE_CHANNEL_STATS_URL", raising=False)
    stream = EventStream()
    facts = asyncio.run(runner.measure(stream, "fw_test"))
    assert facts == []
    assert stream.all() == []           # not one event — demo streams stay canon


# ─── normalization: no number, no fact ────────────────────────────────────────
def test_outcome_facts_normalize_metrics():
    rows = [
        {"ref": "x/123", "channel": "x", "reach": 1240, "replies": 3},
        {"ref": "ig/9", "channel": "ig"},                  # no metrics → dropped
        {"url": "https://l.in/p/7", "channel": "linkedin", "clicks": 18.0},
        "not-a-dict-was-filtered-upstream",
    ]
    facts = outcomes.outcome_facts([r for r in rows if isinstance(r, dict)])
    assert len(facts) == 2
    assert facts[0]["claim"] == "Published x/123 on x: reach 1240 · replies 3."
    assert facts[0]["source"] == "channel stats · x/123"
    assert "clicks 18" in facts[1]["claim"]                # 18.0 → 18, cite-clean


def test_outcome_facts_ignore_bools_and_strings():
    facts = outcomes.outcome_facts([{"ref": "p", "channel": "x",
                                     "reach": True, "replies": "many"}])
    assert facts == []                                     # no real number, no fact


# ─── configured: the read flows, fail-soft on a flaky surface ─────────────────
def test_pull_outcomes_fetches_and_filters(monkeypatch):
    monkeypatch.setenv("SAAKSHE_CHANNEL_STATS_URL", "https://stats.example/outcomes")

    class _Resp:
        def raise_for_status(self):  # noqa: D401
            return None

        def json(self):
            return {"outcomes": [{"ref": "x/1", "channel": "x", "reach": 9}, 42]}

    import httpx
    monkeypatch.setattr(httpx, "get", lambda *a, **k: _Resp())
    rows = outcomes.pull_outcomes()
    assert rows == [{"ref": "x/1", "channel": "x", "reach": 9}]


def test_pull_outcomes_fail_soft(monkeypatch):
    monkeypatch.setenv("SAAKSHE_CHANNEL_STATS_URL", "https://stats.example/outcomes")
    import httpx

    def _boom(*a, **k):
        raise httpx.ConnectError("down")

    monkeypatch.setattr(httpx, "get", _boom)
    assert outcomes.pull_outcomes() == []                  # reads fail SOFT


def test_measure_emits_and_returns_facts(monkeypatch):
    monkeypatch.setenv("SAAKSHE_CHANNEL_STATS_URL", "https://stats.example/outcomes")
    monkeypatch.setattr(outcomes, "pull_outcomes",
                        lambda: [{"ref": "x/1", "channel": "x", "reach": 9}])
    stream = EventStream()
    facts = asyncio.run(runner.measure(stream, "fw_test"))
    assert len(facts) == 1 and facts[0]["source"] == "channel stats · x/1"
    assert any("outcome" in e.text for e in stream.all())
