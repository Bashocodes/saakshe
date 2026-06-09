"""kural — deterministic offline replay fixtures (qualify + parallel research).

A thin net so the full ADK pipeline (Coordinator → parallel research → halt) runs
without live credentials (CI, or surviving a 429 mid-demo). The numbers mirror the
Sundara Coffee Co. case; the live mouth produces these for real. NOT the
deliverable — live is.

kural authors NOTHING: kalai owns all copy, and kural carries the cleared master's
formats untouched (separation fix #1). These fixtures only feed the qualify
decision and the two research scouts; the post the founder publishes is kalai's
own `formats`, byte-for-byte.
"""

from __future__ import annotations

import json

from common import config, models

NS = "kural"
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

def scripted_payload(role: str, llm_request=None) -> str:
    """Return the canned output for a role in deterministic-replay mode.

    Registered with common.models so the shared ScriptedLlm dispatches the
    kural namespace's roles here — same machinery arivu uses, per-quadrant fixtures.
    Only two role families remain after the separation fix: the Claude qualify
    decision and the two research scouts. kural authors no copy.
    """
    if role == "coordinator":
        return json.dumps(_QUALIFY)
    if role in _RESEARCH:
        return json.dumps(_RESEARCH[role])
    return "Acknowledged."


# Register kural's resolver with the shared model factory at import time.
models.register_demo(NS, scripted_payload)


# ─── Public shapes the runner assembles (kept stable across Phase A → B) ──────
def launch_post(master: dict, context_pack: dict) -> dict:
    """The launch post assembled from kalai's master + manas voice.

    Used by the runner when assembling the gate-ready post and by ``publish`` as
    the fallback shape. kural authors NOTHING — the drafts are kalai's `formats`
    and the caption is kalai's `caption`, carried untouched.
    """
    master = master if isinstance(master, dict) else {}
    formats = master.get("formats", {})
    pack_v = (context_pack or {}).get("version", config.CANON["context_pack_from"])
    return {
        "channel": "x+ig+linkedin",
        "as_voice": "founder · plain, warm, names the trade-off",
        "grounded_in": pack_v,
        "caption": master.get("caption", ""),
        "drafts": formats,
    }


def published(post: dict, *, dry_run: bool) -> dict:
    """Back-compat publish result shape (delegates to the channel publisher)."""
    from .tools import channels
    return channels.publish_master(post, dry_run=dry_run)
