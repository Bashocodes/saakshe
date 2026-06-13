"""Pin the outcome normalizer + measure — loop step 7 at the kural edge.

The stats surface is pure configuration: unset env → zero network, zero facts, zero
stream noise, so demo/CI stay byte-identical. Configured → the manas broker reads the
rows and ``outcome_facts`` normalizes them into cited facts (no number, no fact)."""

from __future__ import annotations

import asyncio

import pytest

from common.stream import EventStream
from kural import runner
from kural.tools import outcomes
# measure() routes its outcome-read through the manas channel broker (which custodies
# the channel keys); importing connectors registers those skills so this isolated
# kural suite can exercise the read path.
from manas import connectors as _manas_connectors  # noqa: F401


# ─── unconfigured = inert (the demo byte-identity guarantee) ──────────────────
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


# ─── configured: the read flows through the manas broker, fail-soft on a flake ─
def test_measure_emits_and_returns_facts(monkeypatch):
    # Patch the TRANSPORT (httpx.get), not the reader: measure() reads outcomes
    # through the manas broker, which hits httpx.get — the fixture proves the loop.
    monkeypatch.setenv("SAAKSHE_CHANNEL_STATS_URL", "https://stats.example/outcomes")

    class _Resp:
        def raise_for_status(self):  # noqa: D401
            return None

        def json(self):
            return {"outcomes": [{"ref": "x/1", "channel": "x", "reach": 9}]}

    import httpx
    monkeypatch.setattr(httpx, "get", lambda *a, **k: _Resp())
    stream = EventStream()
    facts = asyncio.run(runner.measure(stream, "fw_test"))
    assert len(facts) == 1 and facts[0]["source"] == "channel stats · x/1"
    assert any("outcome" in e.text for e in stream.all())
