"""the live ClarifyingQuestions must be visible and answerable everywhere the
cockpit claims them. The bug: the badge said 3 and the overview listed them,
but the Questions page and the manas page rendered empty — they read the
per-agent store (Q/quadQ) that status.open_questions never hydrated; only the
overview had a fold-in special case. And the chat seed dumped all questions as
one raw paragraph on EVERY page load (reveal() re-fires, the feed persists)."""
from pathlib import Path

ROOT = Path(__file__).parents[1]
COCKPIT = (ROOT / "web" / "cockpit.html").read_text()
CHAT = (ROOT / "web" / "chat-panel.js").read_text()


def test_open_questions_hydrate_the_per_agent_store():
    # cockpitSetOrg lands status.open_questions in Q.manas/quadQ — the one store
    # every question surface (Questions view, agent pages, overview) renders from
    assert "Q.manas.questions" in COCKPIT
    assert "quadQ.manas" in COCKPIT
    # …which retires the overview-only fold-in special case
    assert "fold them in here" not in COCKPIT


def test_live_questions_are_answerable_in_place():
    # a live qcard commits against the real question id over /api/connect/answer
    assert "cockpitAnswerQuestion" in COCKPIT
    assert "data-qid" in COCKPIT
    # contradiction candidates (ClarifyingQuestion.options) render as one-tap answers
    assert "data-liveans" in COCKPIT


def test_chat_seed_is_structured_and_seeds_once():
    # the seed hands the panel a structured payload — the panel formats, never a raw dump
    assert "SK_CHAT.questions" in COCKPIT
    # reveal() fires on every load — the same question set must not seed twice
    assert "sk-seeded:" in COCKPIT
    # each question renders as its own row, with a chip that jumps to the Questions page
    assert "qseed" in CHAT
    assert "nav.questions" in CHAT


def test_restored_feed_is_structured_not_raw_html():
    # persistence is structured JSON re-rendered through msg() — dead chrome
    # (the "new messages ↓" pill, the typing row) is never persisted at all,
    # and the feed is never rebuilt via a raw innerHTML re-injection
    assert "JSON.stringify({ v: 2" in CHAT
    assert "feed.innerHTML = restored" not in CHAT
