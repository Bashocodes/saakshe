"""The connect → extract → doubt → ground flow (the setu bridge into manas).

Proves the new real-ingestion spine without network: the imbibers run over source
bundles (scripted in demo), the deterministic curator math verifies, doubts are
raised by CODE triggers (a contradiction, a missing dimension), and the founder's
answer folds back into the corpus and re-grounds. Empty-state stays sacred: nothing
is committed until a real source is read.
"""

from __future__ import annotations

import pytest

from common import a2a, project
from common.stream import EventStream
from manas import doubts, runner
from manas import sources as src


# ─── doubts: deterministic triggers only ─────────────────────────────────────
def test_doubts_flags_a_contradiction():
    facts = [
        {"claim": "Pro list price is $29/mo", "source": "README.md"},
        {"claim": "Pro list price is $39/mo", "source": "/pricing"},
    ]
    qs = doubts.detect(facts, voice_rules=["warm"], brand_rules=[])
    contra = [q for q in qs if q.trigger == "contradiction"]
    assert contra, "a numeric price clash must raise a contradiction question"
    assert contra[0].options and len(contra[0].options) == 2


def test_doubts_flags_a_missing_dimension():
    # Facts cover pricing but nothing about a channel → ask for the channel.
    facts = [{"claim": "Pro is billed monthly at a fixed price.", "source": "README.md"}]
    qs = doubts.detect(facts, voice_rules=["warm"], brand_rules=[], has_social_connection=False)
    keys = {q.trigger for q in qs}
    assert "missing_field" in keys
    assert any("reach" in q.text.lower() or "channel" in q.text.lower() for q in qs)


def test_doubts_silent_when_well_grounded():
    facts = [
        {"claim": "Pro is a paid monthly subscription.", "source": "/pricing"},
        {"claim": "Built for independent makers and small teams (our customers).", "source": "home"},
        {"claim": "We post updates on Instagram, our main channel.", "source": "social"},
    ]
    qs = doubts.detect(facts, voice_rules=["plain and warm"], brand_rules=["honor subscribers"])
    assert qs == []


_WELL_GROUNDED = [
    {"claim": "Pro is a paid monthly subscription.", "source": "/pricing"},
    {"claim": "Built for independent makers and small teams (our customers).", "source": "home"},
    {"claim": "We post updates on Instagram, our main channel.", "source": "social"},
]


def test_doubts_flags_a_missing_logo_asset():
    # Well-grounded corpus, but the vault holds no logo → one non-blocking ask.
    qs = doubts.detect(_WELL_GROUNDED, voice_rules=["plain and warm"],
                       brand_rules=["honor subscribers"], has_logo_asset=False)
    logo = [q for q in qs if q.trigger == "missing_asset"]
    assert logo and "logo" in logo[0].text.lower()
    assert logo[0].status == "open"            # a ClarifyingQuestion, never a gate


def test_doubts_silent_about_logo_when_vault_holds_one():
    qs = doubts.detect(_WELL_GROUNDED, voice_rules=["plain and warm"],
                       brand_rules=["honor subscribers"], has_logo_asset=True)
    assert qs == []


# ─── vault-completeness doubt rides the real ingest, without blocking it ─────
async def _fake_read(store):
    return [
        src.SourceBundle(channel="repo", ref="git@github.com:example/app.git",
                         text="(scripted in demo)", provenance=["README.md"],
                         org_hint={"name": "Example", "one_liner": "a tiny web app"}, ok=True),
        src.SourceBundle(channel="web", ref="https://example.test",
                         text="(scripted)", provenance=["https://example.test"],
                         org_hint={"name": "Example", "one_liner": "for makers"}, ok=True),
    ]


async def test_ingest_asks_for_logo_but_stays_grounded(monkeypatch):
    monkeypatch.setattr(runner, "_read_sources", _fake_read)
    store = project.STORE
    store.add_connection("github", "git@github.com:example/app.git", {"mechanism": "ssh"})
    res = await runner.ingest_connected(EventStream(), "r1", store)

    assert any(q["trigger"] == "missing_asset" for q in res["questions"])
    assert res["grounded"] is True             # the doubt must NOT flip grounded
    assert store.is_grounded() is True


async def test_ingest_logo_doubt_not_raised_when_vault_has_one(monkeypatch):
    monkeypatch.setattr(runner, "_read_sources", _fake_read)
    store = project.STORE
    store.add_connection("github", "git@github.com:example/app.git", {"mechanism": "ssh"})
    store.add_asset(kind="logo", filename="logo.png", content_type="image/png",
                    uri="vault://a1", sha256="ab" * 32, provenance="https://example.test/logo.png")
    res = await runner.ingest_connected(EventStream(), "r1", store)

    assert not any(q["trigger"] == "missing_asset" for q in res["questions"])


# ─── ingest: connect sources → grounded, versioned Context Pack ──────────────
async def test_ingest_grounds_the_company(monkeypatch):
    async def fake_read(store):
        return [
            src.SourceBundle(channel="repo", ref="git@github.com:example/app.git",
                             text="(scripted in demo)", provenance=["README.md"],
                             org_hint={"name": "Example", "one_liner": "a tiny web app"}, ok=True),
            src.SourceBundle(channel="web", ref="https://example.test",
                             text="(scripted)", provenance=["https://example.test"],
                             org_hint={"name": "Example", "one_liner": "for makers"}, ok=True),
        ]
    monkeypatch.setattr(runner, "_read_sources", fake_read)

    store = project.STORE
    store.add_connection("github", "git@github.com:example/app.git", {"mechanism": "ssh"})
    store.add_connection("website", "https://example.test")
    res = await runner.ingest_connected(EventStream(), "r1", store)

    assert res["grounded"] is True
    assert store.is_grounded() is True
    assert res["version"] == "v1"               # first commit ticks v0 -> v1
    assert res["fact_count"] >= 1
    assert all(f.get("source") for f in res["facts"])   # every committed fact is cited
    assert store.org["name"] == "Example"


# ─── answer-folding: a founder answer re-grounds + ticks the version ─────────
async def test_answer_folds_back_and_reticks(grounded_company):
    store = grounded_company
    v_before = store.version
    q = a2a.ClarifyingQuestion(id="missing-channel", text="Where do you reach people?",
                               why="no channel found", trigger="missing_field")
    store.set_questions([q])
    assert store.open_questions()

    res = await runner.answer_question(EventStream(), "r1", "missing-channel",
                                       "Mostly Instagram and a weekly email.", store)
    assert res["ok"] is True
    assert res["remaining"] == 0
    assert res["version"] != v_before           # the answer re-ticked the pack
    # the answer is now a cited fact in the corpus
    assert any("Instagram" in f["claim"] for f in store.all_facts())


# ─── empty-state: ingest with nothing connected is a no-op-safe path ─────────
async def test_ingest_requires_a_connection():
    store = project.STORE
    assert not store.is_connected()
    res = await runner.ingest_connected(EventStream(), "r1", store)
    # No sources → nothing committed, store stays ungrounded (never fabricates).
    assert store.is_grounded() is False
    assert res["fact_count"] == 0


# ─── org one-liner: HTML banners in famous-repo READMEs never leak markup ─────
def test_first_paragraph_skips_html_banners():
    md = (
        '<a href="https://example.com" target="_blank">\n'
        '<picture><source media="(prefers-color-scheme: dark)" '
        'srcset="https://cdn.example.com/cover-dark.png" /><img src="cover.png" /></picture>\n'
        "</a>\n\n"
        "[![CI](https://badge.example/ci.svg)](https://ci.example)\n\n"
        "An open source virtual whiteboard that is collaborative and end-to-end encrypted.\n"
    )
    line = src._first_paragraph(md)
    assert "<" not in line and "srcset" not in line and "https://" not in line
    assert line.startswith("An open source virtual whiteboard")


def test_first_paragraph_skips_blockquote_alerts():
    md = (
        "> [!WARNING]\n"
        "> Use at your own risk. The community edition is intended for self-hosters.\n\n"
        "The open scheduling infrastructure for absolutely everyone.\n"
    )
    line = src._first_paragraph(md)
    assert line.startswith("The open scheduling infrastructure")
    assert "WARNING" not in line


# ─── the EMPTY START: no sources → the interview, not a dead end ──────────────
async def test_empty_start_opens_the_interview():
    """Zero connections + ingest = clarifying questions open (NEEDS_ANSWERS),
    nothing fabricated, nothing committed."""
    store = project.ProjectStore(user="empty-start")
    res = await runner.ingest_connected(EventStream(), "r-empty", store)
    assert res["grounded"] is False
    assert res["fact_count"] == 0                       # nothing fabricated
    assert len(res["questions"]) >= 1                   # the interview is open
    assert store.ingest_status == project.NEEDS_ANSWERS
    assert store.open_questions()


async def test_empty_start_answers_become_cited_facts():
    """Each interview answer folds back as a 'founder answer' fact and ticks the
    pack — the founder's own words are the first source."""
    store = project.ProjectStore(user="empty-start-2")
    s = EventStream()
    await runner.ingest_connected(s, "r-empty2", store)
    q = store.open_questions()[0]
    out = await runner.answer_question(s, "r-empty2", q.id, "We sell HDR film presets.",
                                       store=store)
    assert out["ok"] is True
    facts = store.all_facts()
    assert any("founder answer" in str(f.get("source", "")) for f in facts)
    assert store.version != "v0"


async def test_unreadable_connection_still_no_interview_hijack(monkeypatch):
    """A CONNECTED store whose sources failed to read keeps the old honest path
    (CONNECTING, no questions) — the interview is only the EMPTY start."""
    store = project.ProjectStore(user="bad-source")
    store.add_connection("website", "https://unreachable.invalid")

    async def _none(_store):
        return [src.SourceBundle(channel="web", ref="https://unreachable.invalid",
                                 ok=False, text="", meta={"error": "unreachable"})]

    monkeypatch.setattr(runner, "_read_sources", _none)
    res = await runner.ingest_connected(EventStream(), "r-bad", store)
    assert res["questions"] == []
    assert store.ingest_status == project.CONNECTING
