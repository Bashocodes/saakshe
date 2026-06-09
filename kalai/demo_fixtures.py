"""kalai — deterministic offline replay fixtures (the on-brand master).

A thin net so the full ADK studio pipeline runs without live credentials (CI, or
surviving a 429 mid-demo). The numbers mirror the sealed canon: the Brand-Fidelity
climb 6.8 → 8.4 → 9.1 (passes at the top), the fail-closed compliance clearance,
and the Sundara Pro-$34 launch master. NOT the deliverable — live is.

The scripted resolver is registered with ``common.models.register_demo("kalai", …)``
at package import (see ``kalai/__init__.py``); ``ScriptedLlm`` dispatches to it by
(namespace, role). The compliance fixture reads the SAME sentinel screen the tests
read (``tools.analyst.compliance_screen``), so canned + test agree on what blocks.
"""

from __future__ import annotations

import json

from common import a2a, config
from .state import StateKeys
from .tools import analyst

# The sealed Brand-Fidelity climb — passes at the top (9.1 ≥ 8.5). Kept public so
# the runner can also drive the climb deterministically.
FIDELITY_CLIMB = list(config.CANON["fidelity_climb"])   # [6.8, 8.4, 9.1]


# ── canned seat outputs (structured roles return JSON strings) ───────────────
_CREATIVE_FRAME = {
    "concept": "A calm, candid launch banner: 'clearer pricing, same obsession' — "
    "Pro moves to $34, early believers grandfathered, 30 days' notice.",
    "brand_guardrails": [
        "voice: calm, candid, anti-hype — no exclamation-mark hype",
        "honour the grandfathering trust promise from the canon",
        "no vertical gradient streak; B&W grid base with one warm accent",
    ],
    "platforms": ["x", "ig", "linkedin"],
}

_DESIGN = {
    "asset_id": "kalai-sundara-pro34-launch",
    "visual": "B&W grid hero with a single warm cup-amber accent; price '→ $34' set "
    "in the brand display face; grandfather seal lockup bottom-left.",
    "palette": "charcoal + cream + cup-amber accent (brand canon)",
    "platforms": {
        "x": "1600x900 crop, headline + seal",
        "ig": "1080x1350 crop, headline stacked",
        "linkedin": "1200x627 crop, headline + 'why' link",
    },
}

_COPY = {
    "caption": "Same coffee obsession, clearer pricing: Pro moves to $34. Early "
    "believers keep their price; everyone gets 30 days' notice.",
    "x": "Pro is moving to $34 — and if you're already with us, you keep your price. "
    "30 days' notice, no surprises.",
    "ig": "Same coffee obsession, clearer pricing. Pro → $34. Early believers "
    "grandfathered. ☕",
    "linkedin": "We're adjusting Pro to $34. Existing subscribers are grandfathered; "
    "everyone gets 30 days' notice. Here's the why →",
    "seo_keywords": ["pro pricing", "grandfathered subscription", "coffee subscription"],
}


def _fidelity_for_round(rnd: int) -> dict:
    """Scripted scorer output for a 0-indexed loop round → the sealed climb value.

    Kept for back-compat (the single-scorer shape); the 4-scorer panel now uses
    :func:`_scorer_for_lens`, which decomposes the SAME climb per lens."""
    score = FIDELITY_CLIMB[min(max(rnd, 0), len(FIDELITY_CLIMB) - 1)]
    if score >= config.FIDELITY_THRESHOLD:
        off, fix = [], "on brand — ship"
    else:
        off = ["accent skew warm of canon", "headline kerning loose"]
        fix = "tighten the accent to the canon amber and re-set the headline"
    return {"score": score, "off_brand": off, "fix_next": fix}


def _scorer_for_lens(lens: str, rnd_0indexed: int) -> dict:
    """Scripted output for one Brand-Fidelity panel seat at a 0-indexed loop round.

    The four seats' scores AGGREGATE (via ``scorers.aggregate``) to the sealed climb
    value for the round — sourced from ``scorers.demo_subscores`` so the unit test
    (``test_scorers``) and the live climb (``test_make``) can't drift onto two
    tables. The marker round is 0-indexed (the check-agent increments after), so we
    feed ``demo_subscores`` the 1-indexed round (+1)."""
    from . import scorers

    subs = scorers.demo_subscores(rnd_0indexed + 1)
    score = subs.get(lens, 0.0)
    if score >= config.FIDELITY_THRESHOLD:
        off, fix = [], f"on brand on the {lens} lens — ship"
    else:
        off = [f"{lens}: skews off the canon"]
        fix = f"tighten the {lens} lens toward the asset bank"
    return {"lens": lens, "score": score, "off_lens": off, "fix_next": fix}


def _compliance_for_brief(brief: str) -> dict:
    """Fail-closed compliance verdict, gated on the SAME sentinel screen the test
    uses. A clean brief clears; a planted-unsafe brief is blocked — no handoff."""
    safe, hits = analyst.compliance_screen(brief)
    if not safe:
        return {
            "compliance": "blocked",
            "checks": {"claims": "fail", "rights": "fail", "tone": "ok", "sensitive": "ok"},
            "reasons": [f"unsafe/unauthorised content in brief: {', '.join(hits)}"],
        }
    return {
        "compliance": "cleared",
        "checks": {"claims": "ok", "rights": "ok", "tone": "ok", "sensitive": "ok"},
        "reasons": ["claims authorised by the brief; rights/tone/sensitive all clear"],
    }


def scripted_payload(role: str, llm_request=None) -> str:
    """Return the canned output for a kalai seat in deterministic-replay mode."""
    if role == "director":
        return json.dumps(_CREATIVE_FRAME)
    if role == "designer":
        return json.dumps(_DESIGN)
    if role == "copy":
        return json.dumps(_COPY)
    if role.startswith("fidelity__"):
        # One of the four panel seats — role is "fidelity__<lens>".
        lens = role.split("__", 1)[1]
        rnd = _round_from_request(llm_request)
        return json.dumps(_scorer_for_lens(lens, rnd))
    if role == "fidelity":
        # Back-compat: the retired single-scorer seat (no longer in the pipeline).
        rnd = _round_from_request(llm_request)
        return json.dumps(_fidelity_for_round(rnd))
    if role == "compliance":
        return json.dumps(_compliance_for_brief(_brief_from_request(llm_request)))
    return "Acknowledged."


# ── CreativeMaster assembler (used by the runner from final pipeline state) ──
def assemble_master(
    brief: str,
    *,
    design: dict | None = None,
    copy: dict | None = None,
    fidelity_score: float | None = None,
    media: dict | None = None,
    spend_usd: float = 0.42,
) -> a2a.CreativeMaster:
    """Build the compliance-cleared CreativeMaster from the pipeline's outputs.

    On the happy path this carries the sealed finals: fidelity 9.1, compliance
    'cleared'. Formats come from the Copy desk; the asset id from the Designer;
    the media handle (image_ref / video_ref) from the Vertex wrapper (Task 3.3).
    """
    design = design or _DESIGN
    copy = copy or _COPY
    formats = {
        "x": copy.get("x", _COPY["x"]),
        "ig": copy.get("ig", _COPY["ig"]),
        "linkedin": copy.get("linkedin", _COPY["linkedin"]),
    }
    return a2a.CreativeMaster(
        asset_id=design.get("asset_id", "kalai-sundara-pro34-launch"),
        brief=brief,
        caption=copy.get("caption", _COPY["caption"]),
        formats=formats,
        media=media or {},
        fidelity_score=fidelity_score if fidelity_score is not None else config.CANON["fidelity_pass"],
        compliance="cleared",
        spend_usd=spend_usd,
    )


def creative_master(brief: str, spend_usd: float = 0.42) -> a2a.CreativeMaster:
    """Back-compat alias kept for any caller that wants the canon master directly."""
    return assemble_master(brief, spend_usd=spend_usd)


# ── request marker helpers (read the round / brief out of the system prompt) ──
def _request_text(llm_request) -> str:
    try:
        si = getattr(llm_request, "config", None)
        si = getattr(si, "system_instruction", "") if si else ""
        return str(si or "")
    except Exception:  # noqa: BLE001
        return ""


def _round_from_request(llm_request) -> int:
    """Read the [FIDELITY_ROUND::n] marker the scorer's instruction carries."""
    if llm_request is None:
        return 0
    text = _request_text(llm_request)
    marker = "FIDELITY_ROUND::"
    idx = text.find(marker)
    if idx == -1:
        return 0
    tail = text[idx + len(marker):]
    num = ""
    for ch in tail:
        if ch.isdigit():
            num += ch
        else:
            break
    try:
        return int(num)
    except ValueError:
        return 0


def _brief_from_request(llm_request) -> str:
    """Read the [BRIEF::...] marker the compliance instruction carries."""
    if llm_request is None:
        return ""
    text = _request_text(llm_request)
    marker = "[BRIEF::"
    idx = text.find(marker)
    if idx == -1:
        return ""
    tail = text[idx + len(marker):]
    end = tail.find("::BRIEF]")
    return tail[:end] if end != -1 else tail
