"""common.agents — the canonical staff registry: 42 agents · 4 realms.

The founder's company has exactly FORTY-TWO staff agents, divided into four
realms — manas=Memory (knows) · arivu=Intellect (decides) · kalai=Imagination
(makes) · kural=Communication (engages) — plus saakshe the Witness, who stands
ABOVE the staff (the 43rd eye, never counted among the 42).

Naming canon (user-locked):
  * a name is at most TWO common words — precise, recognizable, no padding
  * every agent carries a compressed call-sign built from its name's syllables
    (the founder's "SoMeMa = social media manager" device): Social Reader→SoRe,
    Mind Keeper→MiKe — unique across the whole staff
  * one capability = one agent; modalities/platforms are STREAMS inside an
    agent, never excuses for ten more agents (one Media Reader, not a PDF
    reader + a video reader + …)
  * no Devanagari, no IAST diacritics, nothing in config.FORBIDDEN["names"]

Types (the founder's taxonomy):
  * orchestrator — controls/routes/frames; tells others what to do
  * action       — performs exactly one kind of action
  * verifier     — checks, scores, prosecutes, gates; never authors
  * keeper       — holds memory/assets/versions; the storehouses

This module is import-light pure data (config only — no ADK). The cockpit
renders it; /api/saakshe/agents serves it; tests pin its invariants.
"""

from __future__ import annotations

from . import config

# ─── Realms ──────────────────────────────────────────────────────────────────
# Cockpit hues are the landing-locked theme tokens (Brut light / Obsidian dark);
# `hue` is the backend canonical from config.QUADRANTS.
REALMS = {
    "manas": {
        "realm": "memory", "verb": "knows", "glyph": "●",
        "hue": config.QUADRANTS["manas"]["hue"],
        "ui": {"light": "#E3A52B", "dark": "#E0B25A"},
        "line": "the storehouse — everything the company has ever grasped",
    },
    "arivu": {
        "realm": "intellect", "verb": "decides", "glyph": "◆",
        "hue": config.QUADRANTS["arivu"]["hue"],
        "ui": {"light": "#3551C8", "dark": "#7C97F2"},
        "line": "the chamber — deliberation earned through opposition",
    },
    "kalai": {
        "realm": "imagination", "verb": "makes", "glyph": "▲",
        "hue": config.QUADRANTS["kalai"]["hue"],
        "ui": {"light": "#CC4632", "dark": "#E0685C"},
        "line": "the studio — everything the company shows the world",
    },
    "kural": {
        "realm": "communication", "verb": "engages", "glyph": "◼",
        "hue": config.QUADRANTS["kural"]["hue"],
        "ui": {"light": "#3E8F5E", "dark": "#5EF08A"},
        "line": "the mouth — consented, gated, never a blast",
    },
}

_TYPES = ("orchestrator", "action", "verifier", "keeper")

# The canonical per-realm headcount (Σ == 42). The TOTAL alone is not enough: a
# faculty re-assignment that moves a seat between realms keeps the total at 42
# while silently inverting ownership. validate() pins this map so such a move
# fails at IMPORT (the Docker build), not only in tests/test_agents_registry.py
# — which a bare `pytest` (testpaths=tests) runs, but the realm suites it does
# not. Update this in the SAME commit that moves the seats.
REALM_HEADCOUNT = {"manas": 10, "arivu": 10, "kalai": 11, "kural": 11}


def _a(id, call, name, expansion, realm, type, model, status, does):
    return {
        "id": id, "call": call, "name": name, "expansion": expansion,
        "realm": realm, "type": type, "model": model, "status": status,
        "does": does,
    }


# ─── The 42 ──────────────────────────────────────────────────────────────────
AGENTS = [
    # MANAS — Memory (10) ● ----------------------------------------------------
    _a("mind_keeper", "MiKe", "Mind Keeper", "ingestion coordinator",
       "manas", "orchestrator", "gemini-pro", "live",
       "Routes every connect across the channel readers and owns the imbibe."),
    _a("repo_reader", "ReRe", "Repo Reader", "repository imbiber",
       "manas", "action", "gemini-flash", "live",
       "Reads a GitHub repo (public, SSH or PAT) — README, manifests, structure, docs."),
    _a("web_reader", "WeRe", "Web Reader", "website imbiber",
       "manas", "action", "gemini-flash", "live",
       "Crawls the live site — copy, pages, og-images; feeds the Asset Keeper."),
    _a("docs_reader", "DoRe", "Docs Reader", "document imbiber",
       "manas", "action", "gemini-flash", "live",
       "Reads linked docs pages and parses the brand canon."),
    _a("social_reader", "SoRe", "Social Reader", "social-profile imbiber",
       "manas", "action", "gemini-flash", "live",
       "Reads public X/Instagram/LinkedIn profiles for voice and pulse."),
    _a("media_reader", "MeRe", "Media Reader", "pdf · video · image imbiber",
       "manas", "action", None, "planned",
       "ONE reader, many streams — PDF, video, image decode land here, not as ten agents."),
    _a("memory_curator", "MeCu", "Memory Curator", "verify-before-commit librarian",
       "manas", "verifier", "claude-vertex", "live",
       "No claim enters memory without a source; finds contradictions, raises doubts."),
    _a("founder_voice", "FoVo", "Founder Voice", "grounded company answerer",
       "manas", "action", "claude-vertex", "live",
       "Answers only from the corpus — refuses anything it cannot cite."),
    _a("asset_keeper", "AsKe", "Asset Keeper", "brand-asset vault custodian",
       "manas", "keeper", "deterministic", "live",
       "Holds logos and references with provenance + sha256; serves them to kalai."),
    _a("pack_binder", "PaBi", "Pack Binder", "context-pack versioner",
       "manas", "keeper", "deterministic", "live",
       "Binds each learn into Context Pack vN→vN+1 — the company remembers."),

    # ARIVU — Intellect (10) ◆ -------------------------------------------------
    _a("chair", "ChAi", "Chair", "chamber framer",
       "arivu", "orchestrator", "gemini-pro", "live",
       "Frames the question and grounds the chamber before any mantri speaks."),
    _a("economist", "EcOn", "Economist", "unit-economics mantri",
       "arivu", "action", "gemini-flash", "live",
       "Argues the numbers — pricing, margin, unit economics (3-advisor ensemble)."),
    _a("growth_advocate", "GrAd", "Growth Advocate", "funnel & acquisition mantri",
       "arivu", "action", "gemini-flash", "live",
       "Argues reach — funnel, acquisition, what compounds (3-advisor ensemble)."),
    _a("brand_guardian", "BrGu", "Brand Guardian", "canon & promises mantri",
       "arivu", "verifier", "gemini-flash", "live",
       "Defends the canon — what the brand has promised and must not break."),
    _a("risk_advocate", "RiAd", "Risk Advocate", "downside-first devil's advocate",
       "arivu", "verifier", "gemini-flash", "live",
       "Attacks every plan downside-first so the verdict is earned, not agreed."),
    _a("ops_mantri", "OpMa", "Ops Mantri", "can-we-ship-this mantri",
       "arivu", "verifier", "gemini-flash", "live",
       "Checks feasibility — can the company actually execute this."),
    _a("debate_moderator", "DeMo", "Debate Moderator", "convergence loop moderator",
       "arivu", "orchestrator", "gemini-flash", "live",
       "Runs the debate rounds; exits only on numeric convergence or rollback."),
    _a("verdict_chair", "VeCh", "Verdict Chair", "chamber synthesizer",
       "arivu", "orchestrator", "claude-vertex", "live",
       "Writes the one verdict the chamber earned; halts at the founder's tap."),
    _a("prosecutor", "PrOs", "Prosecutor", "verdict cross-examiner",
       "arivu", "verifier", "claude-vertex", "live",
       "Prosecutes the verdict; below defensibility 0.80 it dies (reviser stream repairs)."),
    _a("executor", "ExEc", "Executor", "approved-decision dispatcher",
       "arivu", "action", "deterministic", "live",
       "Fires ONLY after tap-1 approval — commits and dispatches to kalai/kural."),

    # KALAI — Imagination (11) ▲ -----------------------------------------------
    _a("creative_director", "CrDi", "Creative Director", "concept & guardrail framer",
       "kalai", "orchestrator", "claude-vertex", "live",
       "Frames the concept and brand guardrails every desk works inside."),
    _a("designer_producer", "DePr", "Designer Producer", "visual master-spec desk",
       "kalai", "action", "gemini-flash", "live",
       "Composes the visual spec — layout, palette, formats per platform."),
    _a("copy_smith", "CoSm", "Copy Smith", "copy & SEO desk",
       "kalai", "action", "gemini-flash", "live",
       "Writes every variant of the words — captions, posts, SEO."),
    _a("still_maker", "StMa", "Still Maker", "poster & still renderer",
       "kalai", "action", "vertex-imagen", "live",
       "Renders stills and posters (Imagen) after compliance clears — never before."),
    _a("reel_maker", "ReMa", "Reel Maker", "reel & shorts renderer",
       "kalai", "action", "vertex-veo", "live",
       "Renders motion (Veo). Reels and Shorts are ONE craft — one agent, two stages."),
    _a("sound_maker", "SoMa", "Sound Maker", "music · sfx · voice renderer",
       "kalai", "action", None, "planned",
       "Audio as one craft — music, SFX and voice land here as streams."),
    _a("brand_scorer", "BrSc", "Brand Scorer", "brand-consistency lens",
       "kalai", "verifier", "gemini-flash", "live",
       "Scores palette, lockups, grid against the brand pack (0–10)."),
    _a("voice_scorer", "VoSc", "Voice Scorer", "voice-tone lens",
       "kalai", "verifier", "gemini-flash", "live",
       "Scores the words against the voice rules — calm, candid, anti-hype."),
    _a("platform_scorer", "PlSc", "Platform Scorer", "platform-fit lens",
       "kalai", "verifier", "gemini-flash", "live",
       "Scores crop, format, length per destination platform."),
    _a("edge_scorer", "EdSc", "Edge Scorer", "compliance-edge lens",
       "kalai", "verifier", "gemini-flash", "live",
       "Scores claims/rights/tone risk before the gate even looks."),
    _a("compliance_gate", "CoGa", "Compliance Gate", "fail-closed clearance",
       "kalai", "verifier", "claude-vertex", "live",
       "Cleared or blocked — default-deny; nothing renders or ships uncleared."),

    # KURAL — Communication (11) ◼ ----------------------------------------------
    _a("envoy_lead", "EnLe", "Envoy Lead", "engagement qualifier",
       "kural", "orchestrator", "claude-vertex", "live",
       "Decides if this is worth saying at all before anyone drafts a send."),
    _a("prospect_scout", "PrSc", "Prospect Scout", "audience prospector",
       "kural", "action", "gemini-flash", "live",
       "Scouts profiles and communities; brings strategy back, never posts."),
    _a("market_watcher", "MaWa", "Market Watcher", "feed & competitor watcher",
       "kural", "action", "gemini-flash", "live",
       "Watches the feeds — what the market is saying and when it's crowded."),
    _a("consent_reader", "CoRe", "Consent Reader", "consent & permission lens",
       "kural", "verifier", "gemini-flash", "live",
       "Counts who actually consented — kural never blasts."),
    _a("reach_reader", "ReaRe", "Reach Reader", "reachable-audience lens",
       "kural", "action", "gemini-flash", "live",
       "Measures who is reachable and active in the last 30 days."),
    _a("topic_reader", "ToRe", "Topic Reader", "topic-fit lens",
       "kural", "verifier", "gemini-flash", "live",
       "Checks the message actually fits what this audience signed up for."),
    _a("timing_reader", "TiRe", "Timing Reader", "open-window lens",
       "kural", "action", "gemini-flash", "live",
       "Finds the open window — crowded feed, staleness, when to speak."),
    _a("delivery_planner", "DePl", "Delivery Planner", "variant × segment × window picker",
       "kural", "orchestrator", "claude-vertex", "live",
       "Picks what goes where and when — its schema has no text field; it cannot author."),
    _a("email_envoy", "EmEn", "Email Envoy", "consented outreach sender",
       "kural", "action", "deterministic", "live",
       "Sends the consented one-to-one outreach, ledgered — no double-send, ever."),
    _a("channel_mouth", "ChMo", "Channel Mouth", "platform publisher",
       "kural", "action", "deterministic", "live",
       "The one mouth. Streams: X · Instagram · LinkedIn live; Pinterest · YouTube "
       "planned. Assembles kalai's words verbatim and publishes only past tap-2."),
    _a("send_gate", "SeGa", "Send Gate", "send-eligibility gate",
       "kural", "verifier", "deterministic", "live",
       "Fail-closed: qualified + consented + under cap, or nothing leaves."),
]

# saakshe itself — the Witness. Stands above the staff; never one of the 42.
WITNESS = {
    "id": "witness", "call": "Witness", "name": "saakshe", "expansion": "the founder's eye",
    "realm": "witness", "type": "verifier", "model": "gemini-pro", "status": "live",
    "does": "Sees everything, touches nothing — telemetry-only, refuses to invent "
            "numbers it can't see. The 43rd eye above the 42.",
}

# Benched — designed, named, deliberately not fielded yet.
BENCHED = [
    _a("prahari", "PraHa", "Prahari", "code-change sentry",
       "arivu", "action", None, "benched",
       "The hands that change code — drafts the diff, opens the request, never "
       "merges. Benched for the hackathon; wakes after."),
]


# ─── Helpers ─────────────────────────────────────────────────────────────────
def get(agent_id: str) -> dict | None:
    for a in AGENTS:
        if a["id"] == agent_id:
            return a
    return None


def by_realm() -> dict[str, list[dict]]:
    out: dict[str, list[dict]] = {name: [] for name in REALMS}
    for a in AGENTS:
        out[a["realm"]].append(a)
    return out


def counts_by_type() -> dict[str, int]:
    out = {t: 0 for t in _TYPES}
    for a in AGENTS:
        out[a["type"]] += 1
    return out


def validate() -> None:
    """Raise AssertionError on any breach of the staff canon."""
    assert len(AGENTS) == 42, f"the staff is 42, found {len(AGENTS)}"
    ids = [a["id"] for a in AGENTS]
    calls = [a["call"] for a in AGENTS]
    assert len(set(ids)) == 42, "duplicate agent ids"
    assert len(set(calls)) == 42, "duplicate call-signs"
    forbidden = set(config.FORBIDDEN["names"])
    for a in AGENTS + [WITNESS] + BENCHED:
        assert a["realm"] in REALMS or a is WITNESS, f"unknown realm: {a['realm']}"
        assert a["type"] in _TYPES, f"unknown type: {a['type']}"
        assert len(a["name"].split()) <= 2, f"name over two words: {a['name']}"
        assert a["name"].lower() not in forbidden, f"forbidden name: {a['name']}"
        assert a["status"] in ("live", "planned", "benched")
    # Per-realm headcount is a hard invariant, not just the total — a cross-realm
    # seat move keeps Σ==42 while inverting ownership. Pin it at import.
    counts: dict[str, int] = {name: 0 for name in REALMS}
    for a in AGENTS:
        counts[a["realm"]] += 1
    assert counts == REALM_HEADCOUNT, f"per-realm headcount drift: {counts} != {REALM_HEADCOUNT}"
    # Every realm stays self-checking: at least one orchestrator (frames/routes)
    # and one verifier (gates) live in each.
    for name in REALMS:
        types = {a["type"] for a in AGENTS if a["realm"] == name}
        assert "orchestrator" in types, f"{name} has no orchestrator"
        assert "verifier" in types, f"{name} has no verifier"


def as_payload() -> dict:
    """The JSON the cockpit and /api/saakshe/agents render. Deterministic."""
    realms = {}
    for name, meta in REALMS.items():
        staff = [a for a in AGENTS if a["realm"] == name]
        realms[name] = {
            **meta,
            "count": len(staff),
            "live": sum(1 for a in staff if a["status"] == "live"),
            "agents": staff,
        }
    return {
        "total": len(AGENTS),
        "types": counts_by_type(),
        "realms": realms,
        "witness": WITNESS,
        "benched": BENCHED,
    }


validate()
