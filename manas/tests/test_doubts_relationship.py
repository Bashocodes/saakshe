"""Public-product interview framing — doubts about a product the founder does
NOT own must never say "your product" / "your customers" / "your logo".

The trigger stays pure code (doubts.detect); only the phrasing flips to third
person when owned=False. The Gemini pass (questions._build_prompt) is told the
same so a live rewrite can never reintroduce the possessive.
"""
from __future__ import annotations

from common import a2a
from manas import doubts, questions


def _texts(owned: bool) -> str:
    qs = doubts.detect([], [], [], has_social_connection=False,
                       has_logo_asset=False, max_questions=10, owned=owned)
    return " ".join([q.text for q in qs] + [q.why for q in qs]).lower()


def test_owned_keeps_the_founder_framing():
    text = _texts(owned=True)
    assert "your product" in text


def test_public_framing_is_third_person():
    text = _texts(owned=False)
    assert "your product" not in text
    assert "your customers" not in text
    assert "your brand voice" not in text
    assert "your logo" not in text
    assert "this product" in text


def _qs() -> list[a2a.ClarifyingQuestion]:
    return [a2a.ClarifyingQuestion(
        id="missing-aaaa1111", trigger="missing_field",
        text="How does this product make money?",
        why="no connected source mentioned how it prices",
        blocks="any pricing or revenue decision (arivu)",
    )]


def test_build_prompt_carries_public_framing():
    p = questions._build_prompt(_qs(), [], [], [],
                                {"name": "Excalidraw", "relationship": "public"})
    assert "does not own" in p.lower()
    assert "third person" in p.lower()


def test_build_prompt_owned_stays_founder_voiced():
    p = questions._build_prompt(_qs(), [], [], [], {"name": "Excalidraw"})
    assert "does not own" not in p.lower()
