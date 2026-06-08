"""kural — deterministic offline replay fixtures (the checked, gated message).

A thin net so the full ADK pipeline (Coordinator → parallel research → Writer →
Claim-Judge loop → halt) runs without live credentials (CI, or surviving a 429
mid-demo). The numbers mirror the Sundara Coffee Co. case; the live mouth
produces these for real. NOT the deliverable — live is.

Reproduces the sealed canon: the Claim-Judge passes at claim_support 0.86 ≥ 0.80,
and the post announces Pro → $34. NEVER presents a forbidden value (0.62 / 0.81)
as canon. The one pre-pass rewrite-loop midpoint (0.72) is below the bar by
design — it shows the bounded loop re-grounding the draft, and it is never
surfaced as the verified support.
"""

from __future__ import annotations

import json

from common import config, models

NS = "kural"
CLAIM_SUPPORT = config.CANON["claim_support"]          # 0.86 (the sealed final)
_PRICE = config.CANON["verdict_price_to"]              # 34

# The org's grounding, as the manas Context Pack + funnel would return it.
DEMO_GROUNDING = {
    "manas_context_pack": {
        "version": config.CANON["context_pack_from"],   # v14 (binds the message)
        "grandfather_promise": "existing subscribers keep their current price — a stated trust promise",
        "voice": "calm, candid, anti-hype; name the trade-off",
        "verdict_price_to": _PRICE,
    },
    "funnel": {
        "list_size": 1840,
        "consented_30d_opens": 980,
        "pipeline_open": 6,
        "topic_match_pct": 64,
    },
    "market": {
        "competitor_posts_7d": 2,
        "our_last_post_days": 9,
    },
}


# ─── Role → canned model output (structured roles return JSON strings) ─────────
_QUALIFY = {
    "worth_engaging": True,
    "channel": "x+ig+linkedin",
    "as_voice": "founder · plain, warm, names the trade-off",
    "rationale": f"A price change touches every customer — say it once, clearly, in the founder's voice.",
}

_RESEARCH = {
    "prospect": {
        "lens": "audience & consent",
        "finding": "Send only to the 980 consented, topic-fit openers (of 1,840) — "
        "not the whole list; ~628 are a real topic fit.",
        "citation": "funnel: 1,840 list, 980 consented 30d opens, 64% topic match",
    },
    "market": {
        "lens": "timing & feed",
        "finding": "Feed is open and we've been quiet 9 days — post now, no competitor crowding.",
        "citation": "market: 2 competitor posts/7d, 9 days since our last post",
    },
}

_DRAFT = {
    "headline": f"Pro is moving to ${_PRICE} — and if you're already with us, your price doesn't change.",
    "body": (
        f"We're raising Pro to ${_PRICE} for new subscribers, with 30 days' notice. "
        "Every current subscriber keeps their existing price — that was a promise, and we're keeping it. "
        "We'd rather grow slowly and keep faith than squeeze the people who got us here."
    ),
    "claims": [
        f"Pro is moving to ${_PRICE} for new subscribers",
        "existing subscribers keep their current price (grandfathered)",
        "30 days' notice before the new price applies",
    ],
    "channel_variants": {
        "x": f"Pro → ${_PRICE} for new folks. Already with us? Your price stays. 30 days' notice. We keep our promises.",
        "ig": f"A small change with a firm promise: Pro is ${_PRICE} for new subscribers — current members keep their price.",
        "linkedin": f"We're moving Pro to ${_PRICE} for new subscribers (30-day notice) and grandfathering every current member. Trust over squeeze.",
    },
}

# Two Claim-Judge rounds: round 0 falls just short (re-ground), round 1 verifies
# at the sealed canon 0.86. The 0.72 midpoint is NOT a forbidden value and is
# never presented as the verified support.
_CLAIM_BY_ROUND = [
    {
        "per_claim": [
            {"claim": f"Pro is moving to ${_PRICE} for new subscribers", "verdict": "supported", "evidence": "context pack: verdict_price_to=34"},
            {"claim": "existing subscribers keep their current price", "verdict": "supported", "evidence": "context pack: grandfather promise"},
            {"claim": "30 days' notice", "verdict": "unsupported", "evidence": "none — notice window not yet in the pack"},
        ],
        "claim_support": 0.72,
        "verified": False,
        "fix": "either cite the 30-day notice from the approved verdict or cut the specific window",
    },
    {
        "per_claim": [
            {"claim": f"Pro is moving to ${_PRICE} for new subscribers", "verdict": "supported", "evidence": "context pack: verdict_price_to=34"},
            {"claim": "existing subscribers keep their current price (grandfathered)", "verdict": "supported", "evidence": "context pack: grandfather promise"},
            {"claim": "30 days' notice before the new price applies", "verdict": "supported", "evidence": "approved verdict: 30-day notice"},
        ],
        "claim_support": CLAIM_SUPPORT,   # 0.86 — the sealed final
        "verified": True,
        "fix": "",
    },
]


def _claim_round(llm_request) -> int:
    """Read the loop's round marker out of the system instruction (arivu's trick)."""
    text = _request_text(llm_request)
    if "CLAIM_ROUND::0" in text:
        return 0
    return 1  # default to the surviving round so a one-shot call still terminates


def scripted_payload(role: str, llm_request=None) -> str:
    """Return the canned output for a role in deterministic-replay mode.

    Registered with common.models so the shared ScriptedLlm dispatches the
    kural namespace's roles here — same machinery arivu uses, per-quadrant fixtures.
    """
    if role == "coordinator":
        return json.dumps(_QUALIFY)
    if role in _RESEARCH:
        return json.dumps(_RESEARCH[role])
    if role == "writer":
        return json.dumps(_DRAFT)
    if role == "claim_judge":
        return json.dumps(_CLAIM_BY_ROUND[_claim_round(llm_request)])
    return "Acknowledged."


def _request_text(llm_request) -> str:
    try:
        si = getattr(llm_request, "config", None)
        si = getattr(si, "system_instruction", "") if si else ""
        return str(si or "")
    except Exception:  # noqa: BLE001
        return ""


# Register kural's resolver with the shared model factory at import time.
models.register_demo(NS, scripted_payload)


# ─── Public shapes the runner assembles (kept stable across Phase A → B) ──────
def launch_post(master: dict, context_pack: dict) -> dict:
    """The founder-voice launch post assembled from kalai's master + manas voice.

    Used by the runner when assembling the verified post for the publish gate and
    by ``publish`` as the fallback shape.
    """
    formats = master.get("formats", {}) if isinstance(master, dict) else {}
    pack_v = (context_pack or {}).get("version", config.CANON["context_pack_from"])
    return {
        "channel": "x+ig+linkedin",
        "as_voice": "founder · plain, warm, names the trade-off",
        "grounded_in": pack_v,
        "drafts": formats or _DRAFT["channel_variants"],
        "claim_support": CLAIM_SUPPORT,
    }


def published(post: dict, *, dry_run: bool) -> dict:
    """Back-compat publish result shape (delegates to the channel publisher)."""
    from .tools import channels
    return channels.publish_master(post, dry_run=dry_run)
