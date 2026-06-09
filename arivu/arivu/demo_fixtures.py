"""arivu — deterministic offline replay fixtures.

A thin net so the full ADK pipeline runs without live credentials (CI, or
surviving a 429 mid-demo). The numbers mirror the Sundara Coffee Co. case in the
brief; the live chamber produces these for real. NOT the deliverable — live is.
"""

from __future__ import annotations

import json

from . import config

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

# ─── Ensemble sub-advisor replay (2b.1) ──────────────────────────────────────
# Each mantri fans into three disjoint sub-advisors. The PRIMARY sub-lens (the
# first entry of config.MANTRI_ENSEMBLES[role]) replays the canonical position
# from _POSITIONS[role] VERBATIM, so the reducer's consolidated POS_* stays
# byte-identical to today's value (claim · confidence · stance · citation). The
# two SECONDARY sub-lenses replay distinct, cited supporting sub-claims, so the
# rolled-up position gains an `evidence` list of three cited sub-claims.
#
# Keyed `role__sublens` → {sub_lens, claim, source, confidence}. The primary is
# synthesised from _POSITIONS at lookup time (no duplication of the canon text).
_SUBPOSITIONS = {
    # Economist — primary: margin (lifts _POSITIONS["economist"]).
    "economist__retention": {
        "sub_lens": "retention-yield",
        "claim": "Retention-adjusted, the gain only holds while churn stays flat; "
        "past $36 the cliff erases the margin upside.",
        "source": "admin_analytics(activity): 12mo retention 74%, cliff past $36",
        "confidence": 0.72,
    },
    "economist__competitor_bench": {
        "sub_lens": "competitor-benchmark",
        "claim": "At $29 the product sits below comparable tiers; modest room exists "
        "to lift list without leaving the band.",
        "source": "admin_stats: current_pro_price $29 vs comparable $34-39 band",
        "confidence": 0.66,
    },
    # Growth — primary: acquisition (lifts _POSITIONS["growth"]).
    "growth__conversion": {
        "sub_lens": "trial→paid conversion",
        "claim": "Conversion drags ~2pts per +$5 above $34; the threshold, not the "
        "direction, is what bites the funnel.",
        "source": "admin_analytics(user-growth): trial→paid 18.4%, drag ~2pts/+$5",
        "confidence": 0.7,
    },
    "growth__positioning": {
        "sub_lens": "positioning signal",
        "claim": "A higher price can lift perceived value, but only a $29 capture "
        "tier fully protects top-of-funnel volume.",
        "source": "admin_analytics(user-growth): top_of_funnel_30d 2640",
        "confidence": 0.64,
    },
    # Brand — primary: promise (lifts _POSITIONS["brand"]).
    "brand__voice": {
        "sub_lens": "voice & positioning",
        "claim": "A quiet, grandfathered rise reads as calm/candid; an across-the-"
        "board hike reads off-voice (hype/greed).",
        "source": "manas A2A: voice — calm, candid, anti-hype",
        "confidence": 0.78,
    },
    "brand__trust": {
        "sub_lens": "customer-trust ledger",
        "claim": "Honouring grandfathering compounds long-run trust with the 412 "
        "existing subscribers; breaking it spends it.",
        "source": "admin_stats: 412 paying; manas A2A: grandfathering trust promise",
        "confidence": 0.8,
    },
    # Risk — primary: churn_cliff (lifts _POSITIONS["risk"], carries 'cliff').
    "risk__competitor_undercut": {
        "sub_lens": "competitor-undercut",
        "claim": "A rise opens a window for a rival to undercut at $29 — but that "
        "window is already open today, so it is not a net-new risk.",
        "source": "admin_stats: current_pro_price $29 (undercut window pre-existing)",
        "confidence": 0.62,
    },
    "risk__execution_blast": {
        "sub_lens": "execution blast-radius",
        "claim": "Worst-case blast radius is bounded: an isolated flag flip with a "
        "clean rollback, no revenue-column write.",
        "source": "ops signals: flag flip isolated, billing system healthy",
        "confidence": 0.75,
    },
    # Ops — primary: deploy_health (lifts _POSITIONS["ops"]).
    "ops__config_risk": {
        "sub_lens": "config-change risk",
        "claim": "The pricing flag is isolated; flipping it does not ripple into "
        "other config that could break.",
        "source": "ops signals: flag flip isolated",
        "confidence": 0.8,
    },
    "ops__billing_safety": {
        "sub_lens": "billing blast-radius",
        "claim": "The billing path is healthy and a price change has a clean "
        "rollback; the move is billing-safe to ship now.",
        "source": "ops signals: billing system healthy",
        "confidence": 0.82,
    },
}


def _subposition_payload(sub_role: str) -> str:
    """Scripted output for one ensemble sub-advisor (`role__sublens`).

    The primary sub-lens lifts the canonical _POSITIONS[role] verbatim (so the
    reducer's roll-up is byte-identical); secondaries return their cited
    supporting sub-claim from _SUBPOSITIONS.
    """
    role, _, sub = sub_role.partition("__")
    if sub and config.ensemble_primary(role) == sub:
        canon = dict(_POSITIONS[role])
        # The primary carries the full canonical position so the reducer lifts
        # claim/confidence/stance/citation/lens from it unchanged. It also exposes
        # `sub_lens` + `source` so it reads as a well-formed evidence entry.
        canon.setdefault("sub_lens", sub)
        canon.setdefault("source", canon.get("citation", ""))
        return json.dumps(canon)
    if sub_role in _SUBPOSITIONS:
        return json.dumps(_SUBPOSITIONS[sub_role])
    return ""


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

# Two prosecution rounds: round 1 nearly shatters (<0.80) and faults reason #0
# (the margin-below-the-cliff claim); the reviser strengthens THAT reason; round 2
# re-prosecutes the strengthened verdict and re-forms (>=0.80, nothing left to fault).
_PROSECUTION_BY_ROUND = [
    {
        "attack": "Steelman do-nothing: at $29 the funnel is proven and churn is "
        "known; any rise risks the cliff and the trust hit. $34 is still untested.",
        "rebuttal": "The $36 cliff leaves clear headroom at $34; grandfathering and "
        "30-day notice neutralise the trust and conversion risks.",
        "defensibility": 0.71,
        "survived": False,
        "faulted_reason_index": 0,
    },
    {
        "attack": "Stronger do-nothing: even $34 forfeits the simplicity of one price "
        "and invites a competitor to undercut at $29.",
        "rebuttal": "Competitor undercut is already possible at $29; $34 with "
        "grandfathering preserves trust and adds margin without crossing the cliff.",
        "defensibility": 0.84,
        "survived": True,
        "faulted_reason_index": -1,
    },
]

# The graduated reviser's targeted repair of the faulted reason #0 (2b.2). Replayed
# only when the prosecutor faulted a reason; a surviving round replays the no-op.
_REASON_REVISION = {
    "target_reason_index": 0,
    "revised_reason": "Captures most of the margin upside while holding a ~$2 buffer "
    "below the $36 churn cliff (admin_analytics(activity): retention breaks past $36) "
    "— so $34 is bounded by the cohort-retention data, not untested.",
    "note": "answers the 'untested $34 risks the cliff' attack with the explicit "
    "$2 cliff headroom from cohort retention",
}
_REVISION_NOOP = {"target_reason_index": -1, "revised_reason": "", "note": "verdict survived — no repair needed"}


def scripted_payload(role: str, llm_request=None) -> str:
    """Return the canned output for a role in deterministic-replay mode."""
    # Ensemble sub-advisors (`role__sublens`) — three disjoint cited sub-claims
    # per mantri that the reducer folds into the consolidated POS_*.
    if "__" in role:
        return _subposition_payload(role)
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
    if role == "reviser":
        # Strengthen the faulted reason; a surviving round (marker [REVISE::none])
        # replays the no-op, so the revision ledger records only real repairs.
        text = _request_text(llm_request) if llm_request is not None else ""
        if "[REVISE::none]" in text:
            return json.dumps(_REVISION_NOOP)
        return json.dumps(_REASON_REVISION)
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
