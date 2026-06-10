"""The Gemini question-phrasing pass (manas/questions.py).

The contract under test: the TRIGGER stays pure code (doubts.detect) — the model
only rephrases the asks against the real corpus. It may never add, drop, reorder,
or blank a question; demo/CI stays deterministic (no model call at all); and any
live failure falls back to the template phrasing, never an exception.
"""

from __future__ import annotations

import json

import pytest

from common import a2a, config
from manas import questions


def _qs() -> list[a2a.ClarifyingQuestion]:
    return [
        a2a.ClarifyingQuestion(
            id="missing-aaaa1111", trigger="missing_field",
            text="How does your product make money — free, a subscription, usage-based, a one-time price?",
            why="no connected source mentioned how you price / your offer",
            blocks="any pricing or revenue decision (arivu)",
        ),
        a2a.ClarifyingQuestion(
            id="contradiction-bbbb2222", trigger="contradiction",
            text="Two of your sources disagree — “$29/mo” vs “$39/mo”. Which should I trust?",
            why="the imbiber found a numeric conflict between these claims",
            blocks="grounding this fact",
            options=["$29/mo", "$39/mo"],
        ),
    ]


_FACTS = [
    {"claim": "Excalidraw is an open-source virtual whiteboard.", "source": "README.md"},
    {"claim": "The editor runs fully client-side.", "source": "docs/"},
]
_ORG = {"name": "Excalidraw", "what": "virtual whiteboard"}


# ─── demo/CI: deterministic, the model is never consulted ─────────────────────
async def test_demo_mode_returns_questions_unchanged_without_model(monkeypatch):
    monkeypatch.setattr(config, "is_live", lambda: False)
    monkeypatch.setattr(questions, "_call_gemini",
                        lambda prompt: pytest.fail("demo mode must not call the model"))
    out = await questions.personalize(_qs(), _FACTS, org=_ORG)
    assert [q.text for q in out] == [q.text for q in _qs()]
    assert [q.id for q in out] == [q.id for q in _qs()]


# ─── live: the model rephrases, everything else is preserved ─────────────────
async def test_live_rewrites_text_and_preserves_identity(monkeypatch):
    monkeypatch.setattr(config, "is_live", lambda: True)
    rewritten = "Excalidraw is free and open-source today — how do you plan to make money from it?"
    monkeypatch.setattr(questions, "_call_gemini",
                        lambda prompt: json.dumps({"missing-aaaa1111": rewritten}))
    out = await questions.personalize(_qs(), _FACTS, org=_ORG)
    assert out[0].text == rewritten
    assert out[0].id == "missing-aaaa1111"
    assert out[0].trigger == "missing_field"
    assert out[0].why.startswith("no connected source")
    assert out[0].blocks == "any pricing or revenue decision (arivu)"
    # The second question had no rewrite — template phrasing stays.
    assert out[1].text.startswith("Two of your sources disagree")
    assert out[1].options == ["$29/mo", "$39/mo"]


async def test_live_never_adds_or_drops_questions(monkeypatch):
    monkeypatch.setattr(config, "is_live", lambda: True)
    monkeypatch.setattr(questions, "_call_gemini", lambda prompt: json.dumps({
        "missing-aaaa1111": "Who pays for Excalidraw?",
        "invented-zzzz9999": "What is your favourite colour?",  # model-imagined → ignored
    }))
    out = await questions.personalize(_qs(), _FACTS, org=_ORG)
    assert len(out) == len(_qs())
    assert [q.id for q in out] == [q.id for q in _qs()]


async def test_live_rejects_empty_and_bloated_rewrites(monkeypatch):
    monkeypatch.setattr(config, "is_live", lambda: True)
    monkeypatch.setattr(questions, "_call_gemini", lambda prompt: json.dumps({
        "missing-aaaa1111": "",
        "contradiction-bbbb2222": "x" * 500,
    }))
    out = await questions.personalize(_qs(), _FACTS, org=_ORG)
    assert [q.text for q in out] == [q.text for q in _qs()]


async def test_live_malformed_response_falls_back_to_templates(monkeypatch):
    monkeypatch.setattr(config, "is_live", lambda: True)
    monkeypatch.setattr(questions, "_call_gemini",
                        lambda prompt: "I would suggest asking about pricing first.")
    out = await questions.personalize(_qs(), _FACTS, org=_ORG)
    assert [q.text for q in out] == [q.text for q in _qs()]


async def test_live_model_exception_falls_back_to_templates(monkeypatch):
    monkeypatch.setattr(config, "is_live", lambda: True)

    def _boom(prompt):
        raise RuntimeError("429 quota")

    monkeypatch.setattr(questions, "_call_gemini", _boom)
    out = await questions.personalize(_qs(), _FACTS, org=_ORG)
    assert [q.text for q in out] == [q.text for q in _qs()]


# ─── the prompt is grounded: corpus in, triggers in, invention forbidden ──────
def test_prompt_carries_corpus_org_and_question_ids():
    p = questions._build_prompt(_qs(), _FACTS, [], [], _ORG)
    assert "Excalidraw" in p
    assert "open-source virtual whiteboard" in p
    assert "missing-aaaa1111" in p and "contradiction-bbbb2222" in p
    assert "JSON" in p


# ─── the ingest spine routes every raised doubt through the phrasing pass ─────
async def test_ingest_routes_questions_through_personalize(monkeypatch):
    import dataclasses

    from common import project
    from common.stream import EventStream
    from manas import runner
    from manas import sources as src

    async def fake_read(store):
        return [src.SourceBundle(channel="repo", ref="git@github.com:example/app.git",
                                 text="(scripted in demo)", provenance=["README.md"],
                                 org_hint={"name": "Example"}, ok=True)]

    async def tag(qs, facts, voice_rules=None, brand_rules=None, org=None,
                  stream=None, run_id=""):
        return [dataclasses.replace(q, text="[phrased] " + q.text) for q in qs]

    monkeypatch.setattr(runner, "_read_sources", fake_read)
    monkeypatch.setattr(questions, "personalize", tag)

    store = project.STORE
    store.add_connection("github", "git@github.com:example/app.git", {"mechanism": "ssh"})
    res = await runner.ingest_connected(EventStream(), "r1", store)
    assert res["questions"], "this ingest must raise at least one doubt (no logo in vault)"
    assert all(q["text"].startswith("[phrased] ") for q in res["questions"])
    # The store sees the SAME phrased questions the founder will be shown.
    assert all(q.text.startswith("[phrased] ") for q in store.open_questions())
