"""Pin the Founder-Voice refusal contract + the Context Pack — manas's identity.

The hard refusal (out-of-corpus → refused=True, empty citations) is a CONTRACT, not
a nicety: it keeps the company from being bound by a hallucinated founder opinion. It
is proven against the REAL founder_voice_agent (Claude · output_schema-forced) AND the
SYNC A2A handler — both grounded in the ONE project store, so they can never disagree.

Post-connect-flow truth: the store is EMPTY until a real source is connected, so the
``grounded_company`` fixture (an obviously-synthetic, brand-free company) stands in for
a real connect; an unconnected store refuses everything (the empty-state contract).
"""

from __future__ import annotations

from common import a2a, project
from manas import runner
from manas.tools import corpus


# ─── empty-state: an unconnected company refuses / withholds everything ──────
def test_empty_store_refuses_and_withholds():
    assert project.STORE.is_grounded() is False
    pack = corpus.context_pack("pricing")
    assert pack.grounded is False and pack.facts == []
    fv = corpus.founder_voice("do we grandfather existing subscribers?")
    assert fv.refused is True and fv.citations == []


# ─── the REAL agent: answers in-corpus, refuses out-of-corpus ────────────────
async def test_agent_answers_in_corpus_with_citations(grounded_company):
    ans = await runner.ask_founder_voice_live("do we grandfather existing subscribers?")
    assert ans.refused is False
    assert ans.citations                       # grounded answers cite a source
    assert "grandfather" in ans.answer.lower()


async def test_agent_refuses_out_of_corpus_empty_citations(grounded_company):
    """The contract: an out-of-corpus question is REFUSED with EMPTY citations —
    never an invented founder opinion."""
    ans = await runner.ask_founder_voice_live("what's our 2027 series-A valuation?")
    assert ans.refused is True
    assert ans.citations == []


async def test_agent_does_not_false_match_prompt_words(grounded_company):
    """Regression: prompt/corpus text contains words like 'voice'/'price'; an
    out-of-corpus question must still refuse despite those words in the system
    instruction (the question is isolated via its marker)."""
    ans = await runner.ask_founder_voice_live("which VC should we raise our Series B from?")
    assert ans.refused is True
    assert ans.citations == []


# ─── the DEFAULT path drives Claude in live (mock the seam, force live) ──────
async def test_default_path_drives_claude_agent_in_live(grounded_company, monkeypatch):
    """The default founder-voice entry point routes through the REAL Claude
    founder_voice_agent in live — NOT the sync stem-match. Forced live + a mocked
    agent seam prove the route without any network/model call in CI."""
    monkeypatch.setenv("SAAKSHE_MODE", "live")
    called = {}

    async def _sentinel(question):
        called["q"] = question
        return a2a.FounderVoiceAnswer(answer="VIA_CLAUDE_AGENT", citations=[{"claim": "c", "source": "s"}], refused=False)

    monkeypatch.setattr(runner, "ask_founder_voice_live", _sentinel)
    ans = await runner.ask_founder_voice("do we grandfather existing subscribers?")
    # the default path invoked the Claude agent seam, not the corpus stem-match
    assert ans.answer == "VIA_CLAUDE_AGENT"
    assert called["q"] == "do we grandfather existing subscribers?"


async def test_default_path_falls_back_to_corpus_net_in_demo(grounded_company, monkeypatch):
    """In demo (no creds) the default path NEVER drives the async agent — it returns
    the same corpus-grounded answer the sync handler returns, byte-identical."""
    monkeypatch.setenv("SAAKSHE_MODE", "demo")

    async def _must_not_call(question):
        raise AssertionError("ask_founder_voice_live must NOT run in demo")

    monkeypatch.setattr(runner, "ask_founder_voice_live", _must_not_call)
    ans = await runner.ask_founder_voice("do we grandfather existing subscribers?")
    net = corpus.founder_voice("do we grandfather existing subscribers?")
    assert ans.answer == net.answer and ans.refused is net.refused and ans.citations == net.citations


# ─── the SYNC A2A handler agrees with the agent (shared store) ───────────────
def test_sync_handler_matches_agent_contract(grounded_company):
    grounded = a2a.dispatch("manas", "ask_founder_voice", "do we grandfather existing subscribers?")
    assert grounded["refused"] is False and grounded["citations"]
    refused = a2a.dispatch("manas", "ask_founder_voice", "what's our 2027 series-A valuation?")
    assert refused["refused"] is True and refused["citations"] == []


def test_sync_handler_is_synchronous_and_pure(grounded_company):
    """The A2A handler must be a plain sync call (no event loop) — an async caller
    or a plain `def` test must both work, so it never drives the async agent."""
    import inspect

    out = corpus.founder_voice("do we grandfather existing subscribers?")
    assert isinstance(out, a2a.FounderVoiceAnswer)
    assert not inspect.iscoroutinefunction(corpus.founder_voice)


# ─── the Context Pack: cited facts in-corpus, ungrounded out-of-corpus ───────
def test_context_pack_grounded_in_corpus(grounded_company):
    pack = corpus.context_pack("pricing")
    assert pack.grounded is True
    assert pack.version == project.STORE.version       # the real store version, not a canned pin
    assert any("grandfather" in f["claim"].lower() for f in pack.facts)
    assert all(f.get("source") for f in pack.facts)    # every fact carries a source


def test_context_pack_out_of_corpus_is_ungrounded_and_empty(grounded_company):
    pack = corpus.context_pack("series-c-valuation")
    assert pack.grounded is False
    assert pack.facts == []
    assert pack.voice_rules == [] and pack.brand_rules == []


async def test_ground_refuses_out_of_corpus_topic(grounded_company):
    """ground() serves a grounded pack for an in-corpus topic and an honestly
    ungrounded one (grounded=False) for an out-of-corpus topic — never fabricated."""
    from common.stream import EventStream

    s = EventStream()
    good = await runner.ground(s, "r1", topic="pricing")
    assert good.grounded is True and good.facts
    bad = await runner.ground(s, "r1", topic="series-c-valuation")
    assert bad.grounded is False and bad.facts == []


# ─── canon hygiene: no forbidden values / names anywhere manas presents ──────
def test_no_forbidden_values_or_names_in_corpus(grounded_company):
    import json
    from common import config
    from manas import demo_fixtures as fx

    blob = json.dumps({
        "pack": corpus.context_pack("pricing").as_dict(),
        "ingest": fx._INGEST,                      # the offline replay net
    })
    for bad in config.FORBIDDEN["numbers"]:
        assert str(bad) not in blob, f"forbidden number {bad} leaked into manas memory"
    for name in config.FORBIDDEN["names"]:
        assert name not in blob, f"forbidden name {name!r} leaked into manas memory"
