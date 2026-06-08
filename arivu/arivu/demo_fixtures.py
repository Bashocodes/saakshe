"""arivu — deterministic offline replay fixtures.

A thin net so the full ADK pipeline runs without live credentials (CI, or
surviving a 429 mid-demo). The numbers mirror the Sundara Coffee Co. case in the
brief; the live chamber produces these for real. NOT the deliverable — live is.
"""

from __future__ import annotations

import json

# The org's own numbers, as the example MCP grounding would return them.
DEMO_GROUNDING = {
    "admin_stats": {
        "paying_users": 412,
        "mrr_usd": 11948,
        "current_pro_price": 29,
        "contribution_margin_pct": 71,
    },
    "admin_analytics_user_growth": {
        "trial_to_paid_pct": 18.4,
        "top_of_funnel_30d": 2640,
        "price_sensitivity_note": "conversion drags ~2pts per +$5 above $34",
    },
    "admin_analytics_activity": {
        "cohort_retention_12mo_pct": 74,
        "churn_cliff": "retention breaks past $36; sharp drop at $39",
    },
    "manas_a2a": {
        "brand_canon": "grandfathering existing users is a stated trust promise",
        "voice": "calm, candid, anti-hype",
    },
    "kural_a2a": {"pipeline_open": 6, "list_size": 1840},
}

# Role → canned model output. Structured roles return JSON strings.
_POSITIONS = {
    "economist": {
        "lens": "unit-economics & pricing",
        "claim": "Contribution margin (71%) holds at $39; the higher list only leaves "
        "margin on the table if churn stays flat — which it will not.",
        "citation": "admin_stats: margin 71%, 412 paying, MRR $11,948",
        "confidence": 0.74,
        "stance": "qualify",
    },
    "growth": {
        "lens": "funnel & acquisition",
        "claim": "A price rise reads as a positioning signal and can lift perceived "
        "value, but $39 drags top-of-funnel conversion ~2pts; a $29 capture tier "
        "would protect the funnel.",
        "citation": "admin_analytics(user-growth): trial→paid 18.4%, drag ~2pts/+$5",
        "confidence": 0.69,
        "stance": "oppose",
    },
    "brand": {
        "lens": "canon & promises",
        "claim": "Grandfathering existing subscribers is a brand-trust requirement, "
        "not a nicety — breaking it violates a stated promise in the canon.",
        "citation": "manas A2A: brand canon — grandfathering is a trust promise",
        "confidence": 0.83,
        "stance": "qualify",
    },
    "risk": {
        "lens": "downside-first",
        "claim": "There is a churn cliff at $39: cohort retention breaks past $36 and "
        "drops sharply at $39. The lone-analyst path misses this entirely.",
        "citation": "admin_analytics(activity): 12mo retention 74%, cliff past $36",
        "confidence": 0.86,
        "stance": "oppose",
    },
    "ops": {
        "lens": "can-we-ship-this",
        "claim": "The pricing flag flip is low blast-radius and billing-safe to ship "
        "now; no deploy or config risk blocks the move.",
        "citation": "ops signals: flag flip isolated, billing system healthy",
        "confidence": 0.81,
        "stance": "support",
    },
}

_VERDICT = {
    "decision": "Raise Pro to $34 (not $39), grandfather all existing subscribers, "
    "give 30-day notice before the new price applies.",
    "reasons": [
        "Captures most of the margin upside while staying below the $36 churn cliff "
        "the Risk lens surfaced from cohort retention.",
        "Grandfathering honours the brand-trust promise in manas canon.",
        "30-day notice de-risks the top-of-funnel conversion drag Growth flagged.",
    ],
    "dissent": "Growth holds that a $29 capture tier should ship alongside $34 to "
    "fully protect acquisition; recorded, not adopted.",
    "confidence": 0.88,
}

# Two prosecution rounds: round 1 nearly shatters (<0.80), round 2 re-forms (>=0.80).
_PROSECUTION_BY_ROUND = [
    {
        "attack": "Steelman do-nothing: at $29 the funnel is proven and churn is "
        "known; any rise risks the cliff and the trust hit. $34 is still untested.",
        "rebuttal": "The $36 cliff leaves clear headroom at $34; grandfathering and "
        "30-day notice neutralise the trust and conversion risks.",
        "defensibility": 0.71,
        "survived": False,
    },
    {
        "attack": "Stronger do-nothing: even $34 forfeits the simplicity of one price "
        "and invites a competitor to undercut at $29.",
        "rebuttal": "Competitor undercut is already possible at $29; $34 with "
        "grandfathering preserves trust and adds margin without crossing the cliff.",
        "defensibility": 0.84,
        "survived": True,
    },
]


def scripted_payload(role: str, llm_request=None) -> str:
    """Return the canned output for a role in deterministic-replay mode."""
    if role in _POSITIONS:
        return json.dumps(_POSITIONS[role])
    if role == "verdict":
        return json.dumps(_VERDICT)
    if role == "prosecutor":
        # Round is threaded via the system instruction marker the loop sets;
        # default to the surviving round so a one-shot call still terminates.
        rnd = 1
        if llm_request is not None:
            text = _request_text(llm_request)
            if "PROSECUTION_ROUND::0" in text:
                rnd = 0
        return json.dumps(_PROSECUTION_BY_ROUND[rnd])
    if role == "chair":
        return json.dumps(
            {
                "subquestions": [
                    "What does the margin math say at $39 vs lower?",
                    "What does the funnel do as price rises?",
                    "Does this break a brand promise?",
                    "What is the churn/retention downside?",
                    "Can we ship the change safely now?",
                ]
            }
        )
    return "Acknowledged."


def _request_text(llm_request) -> str:
    try:
        si = getattr(llm_request, "config", None)
        si = getattr(si, "system_instruction", "") if si else ""
        return str(si or "")
    except Exception:
        return ""
