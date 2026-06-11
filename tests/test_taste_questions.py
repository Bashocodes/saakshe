"""The chamber asks the founder — founder-taste questions.

Pins the always-asking contract: arivu raises a SIGNED, non-blocking question
whenever a verdict is defensible but below the comfort bar (and when no safe
path exists at all). Demo/CI default stays byte-identical: no flag, no question.
"""

from __future__ import annotations

import pytest

from common import a2a, config, project, taste
from common.stream import EventStream
import orchestrator


@pytest.fixture
def stream(monkeypatch):
    s = EventStream()
    monkeypatch.setattr(orchestrator, "STREAM", s, raising=False)
    return s


# ─── default (demo/CI): byte-identical, no question ──────────────────────────
async def test_demo_default_raises_no_taste_question(stream):
    await orchestrator.start(stream=s_or(stream))
    assert not _taste_questions()


# ─── flag on: the close-call ask fires, signed, non-blocking ─────────────────
async def test_close_call_asks_signed_question(stream, monkeypatch):
    monkeypatch.setenv("SAAKSHE_TASTE_QUESTIONS", "1")
    started = await orchestrator.start(stream=stream)
    qs = _taste_questions()
    # demo canon verdict survives at 0.84 — between the 0.80 bar and 0.90 comfort
    assert started["status"] == "awaiting_approval"
    assert len(qs) == 1
    q = qs[0]
    assert q.trigger == "founder_taste"
    assert q.asked_by == "arivu · Verdict Chair"
    assert "0.84" in q.text
    # never a third gate, never blocks grounding
    assert q.blocks == ""
    assert q not in project.STORE.blocking_questions()
    # the ask is witnessed on the stream, signed by the asking seat
    notes = [e for e in stream.all() if e.kind == "note" and "question for the founder" in e.text]
    assert notes and notes[0].agent == "Verdict Chair"


async def test_taste_question_is_answerable_and_survives_reingest(stream, monkeypatch):
    monkeypatch.setenv("SAAKSHE_TASTE_QUESTIONS", "1")
    await orchestrator.start(stream=stream)
    q = _taste_questions()[0]
    # a manas re-detection must not drop the chamber's open ask
    project.STORE.set_questions([])
    assert _taste_questions(), "open founder_taste question dropped by set_questions"
    # the founder answers through the existing path; it folds closed
    answered = project.STORE.answer_question(q.id, "comfortable — proceed")
    assert answered is not None and answered.status == "answered"
    assert not _taste_questions()


# ─── the deterministic triggers themselves ────────────────────────────────────
def test_close_call_trigger_band(monkeypatch):
    monkeypatch.setenv("SAAKSHE_TASTE_QUESTIONS", "1")
    v = {"decision": "Raise to $34", "dissent": "churn risk"}
    assert taste.close_call("r1", "raise?", v, 0.84), "in-band must ask"
    assert not taste.close_call("r1", "raise?", v, 0.95), "comfortable → silent"
    assert not taste.close_call("r1", "raise?", v, 0.50), "below bar → rollback path, not close-call"
    assert not taste.close_call("r1", "raise?", v, "not-a-number")


def test_no_safe_path_asks_for_the_tradeoff(monkeypatch):
    monkeypatch.setenv("SAAKSHE_TASTE_QUESTIONS", "1")
    qs = taste.no_safe_path("r2", "rewrite billing?")
    assert qs and qs[0].trigger == "founder_taste"
    assert qs[0].asked_by == "arivu · Prosecutor"


def test_flag_off_is_silent(monkeypatch):
    monkeypatch.setenv("SAAKSHE_TASTE_QUESTIONS", "0")
    assert not taste.close_call("r3", "q", {}, 0.84)
    assert not taste.no_safe_path("r3", "q")


# ─── helpers ──────────────────────────────────────────────────────────────────
def s_or(s):
    return s


def _taste_questions() -> list[a2a.ClarifyingQuestion]:
    return [q for q in project.STORE.open_questions() if q.trigger == "founder_taste"]
