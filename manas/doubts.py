"""manas.doubts — deterministic clarifying-question detection.

The honest basis for manas asking the founder anything during a connect. A doubt
is raised by a CODE trigger that found a real gap, never by a model that imagined a
question — that is what keeps "no fabricated data / refuse-out-of-corpus" sacred
even while manas is curious:

  * contradiction  — two imbibed facts clash (the existing curator.find_contradictions
                     detector; e.g. a price in the repo vs a different price on the site)
  * missing_field  — a dimension the company NEEDS grounded was not found in any source
  * missing_asset  — the org is connected but the brand-asset vault holds no logo

Phrasing is plain English (could be Gemini-written later); the trigger is pure code.
These become ``a2a.ClarifyingQuestion``s surfaced in the saakshe chat. They are NOT
flywheel gates — answering one folds back into the corpus and re-grounds; the two
HITL gates (arivu decision, kural publish) are untouched.
"""

from __future__ import annotations

import hashlib

from common import a2a
from .tools import curator

# Dimensions the company needs grounded for the flywheel to decide / make / engage
# well. Each is satisfied if ANY source mentions one of its stems (substring match
# over the whole imbibed corpus), so we only ask about a genuinely-absent dimension.
_REQUIRED = [
    {
        "key": "pricing",
        "stems": ("pric", "plan", "tier", "subscrib", "cost", "/mo", "per month",
                  "free", "paid", "$", "usd", "revenue", "billing"),
        "blocks": "any pricing or revenue decision (arivu)",
        "ask": "How does your product make money — free, a subscription, usage-based, a one-time price? "
               "Name the tier(s) and rough price if you can.",
        "label": "how you price / your offer",
        "ask_public": "How does this product make money — free, a subscription, usage-based, "
                      "a one-time price? Name the tier(s) and rough price if you know.",
        "label_public": "how it prices / its offer",
    },
    {
        "key": "audience",
        "stems": ("custom", "user", "audien", "creator", "founder", "team", "buyer",
                  "client", "market", "segment", "persona", "subscriber"),
        "blocks": "audience-grounded making + outreach (kalai · kural)",
        "ask": "Who is this for — who are your customers, in your own words?",
        "label": "who your customers are",
        "ask_public": "Who is this product for — who uses it, in your own words?",
        "label_public": "who its users are",
    },
    {
        "key": "voice",
        "stems": ("voice", "tone", "brand", "warm", "plain", "playful", "bold",
                  "minimal", "we believe", "manifesto", "values"),
        "blocks": "on-brand creative (kalai)",
        "ask": "How should the company sound — describe your brand voice in a line or two "
               "(e.g. 'plain and warm, never hypey').",
        "label": "your brand voice",
        "ask_public": "How does this product sound — describe its brand voice in a line or two "
                      "(e.g. 'plain and warm, never hypey').",
        "label_public": "its brand voice",
    },
    {
        # Specific channel signals only — NOT bare "post"/"channel"/"x", which
        # false-match "POST /v1/decode", "Channel Mouth", etc. (the example footgun).
        "key": "channel",
        "stems": ("instagram", "twitter", "linkedin", "youtube", "tiktok", "discord",
                  "substack", "newsletter", "newslet", "email list", "social media",
                  "we post", "our channel", "audience on", "follower"),
        "blocks": "outreach (kural)",
        "ask": "Where do you reach people — your main channel(s) (Instagram, X, LinkedIn, email…)?",
        "label": "your main channel",
        "ask_public": "Where does this product reach people — its main channel(s) "
                      "(Instagram, X, LinkedIn, email…)?",
        "label_public": "its main channel",
    },
]


def _qid(trigger: str, payload: str) -> str:
    h = hashlib.sha1(f"{trigger}:{payload}".encode("utf-8")).hexdigest()[:8]
    return f"{trigger}-{h}"


def detect(
    facts: list[dict],
    voice_rules: list[str] | None = None,
    brand_rules: list[str] | None = None,
    *,
    has_social_connection: bool = False,
    has_logo_asset: bool = True,
    max_questions: int = 4,
    owned: bool = True,
) -> list[a2a.ClarifyingQuestion]:
    """Return the clarifying questions a connect raises. Contradictions first
    (they're concrete and load-bearing), then the most important missing fields.
    Stable ids (hash of content) so a re-ingest doesn't re-ask an answered one.
    ``owned=False`` (org.relationship == "public" — a product the founder is
    exploring, not theirs) flips the phrasing to third person; the triggers and
    ids are identical either way."""
    voice_rules = voice_rules or []
    brand_rules = brand_rules or []
    out: list[a2a.ClarifyingQuestion] = []

    # 1) Contradictions — a real clash the founder must adjudicate.
    for pair in curator.find_contradictions(facts):
        a, b = pair.get("a", ""), pair.get("b", "")
        out.append(a2a.ClarifyingQuestion(
            id=_qid("contradiction", a + "|" + b),
            text=f"Two of your sources disagree — “{a}” vs “{b}”. Which should I trust?",
            why=f"the imbiber found a {pair.get('why', 'conflict')} between these claims",
            trigger="contradiction",
            blocks="grounding this fact",
            options=[a, b],
            sources=[a, b],
        ))

    # 2) Missing required dimensions — only ask about what no source mentioned.
    corpus_text = " ".join(
        [str(f.get("claim", "")) + " " + str(f.get("source", "")) for f in facts]
        + list(voice_rules) + list(brand_rules)
    ).lower()
    for dim in _REQUIRED:
        if dim["key"] == "voice" and voice_rules:
            continue
        if dim["key"] == "channel" and has_social_connection:
            continue
        if any(stem in corpus_text for stem in dim["stems"]):
            continue
        out.append(a2a.ClarifyingQuestion(
            id=_qid("missing", dim["key"]),
            text=dim["ask"] if owned else dim["ask_public"],
            why=f"no connected source mentioned {dim['label'] if owned else dim['label_public']}",
            trigger="missing_field",
            blocks=dim["blocks"],
        ))

    # 3) Missing brand assets — the vault index served no logo (the caller reads
    #    the store's assets index and tells us). Non-blocking like every doubt:
    #    kalai can still make; it just makes bare until the founder adds one.
    if not has_logo_asset:
        out.append(a2a.ClarifyingQuestion(
            id=_qid("missing_asset", "logo"),
            text=("I don't have your logo. Add one to the vault so kalai can put it on what it makes?"
                  if owned else
                  "I don't have this product's logo. Add one to the vault so kalai can put it on what it makes?"),
            why="the brand-asset vault holds no asset of kind 'logo'",
            trigger="missing_asset",
            blocks="logo placement on creative (kalai)",
        ))

    return out[:max_questions]
