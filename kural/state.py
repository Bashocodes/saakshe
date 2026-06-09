"""kural — the session-state contract between pipeline stages.

Centralised (like arivu's config.StateKeys) so the Coordinator, the ParallelAgent
research fan-out, and the channel agents never drift on a key name. kural reads the
*shared* thresholds from common.config; only the state-key names and the one local
send cap live here. (The Outreach Writer + Claim-Judge loop were retired in the
separation fix — kalai authors everything; kural carries the master untouched.)
"""

from __future__ import annotations

import os


def _num(name: str, default: float) -> float:
    try:
        return float(os.environ.get(name, default))
    except (TypeError, ValueError):
        return default


# A campaign-class value cap: a single automated send may never exceed this
# notional value without a human in the loop. The mouth is a buyer, not a
# spender — this is the blast-radius guard on the send tool's before_tool gate.
SEND_VALUE_CAP_USD = _num("KURAL_SEND_VALUE_CAP_USD", 500.0)


class StateKeys:
    # Inputs (seeded by the runner / Coordinator).
    BRIEF = "brief"                   # the campaign brief (from arivu's verdict)
    MASTER = "master"                 # kalai's compliance-cleared CreativeMaster
    CONTEXT_PACK = "context_pack"     # manas's versioned Context Pack (grounding)
    ORG = "org"                       # org profile dict

    # Coordinator (Claude) — the qualify decision, spine entry.
    QUALIFY = "qualify"               # {worth_engaging, channel, as_voice, rationale}

    # Research fan-out (ParallelAgent writes these disjointly).
    RESEARCH_PROSPECT = "research_prospect"   # Prospect Scout (pre-Phase-4)
    RESEARCH_MARKET = "research_market"       # Market Watcher (pre-Phase-4)

    # Delivery chamber (Phase 4): four deep readers → planner → deterministic assembler.
    DELIVERY_CONSENT = "delivery_consent"     # Consent Reader  · consent & permission
    DELIVERY_REACH = "delivery_reach"         # Reach Reader    · reachable audience size
    DELIVERY_TOPIC = "delivery_topic"         # Topic-fit Reader · topic match
    DELIVERY_TIMING = "delivery_timing"       # Timing Reader   · open window
    DELIVERY_PICK = "delivery_pick"           # planner's pick {variant, segment, window, rationale}
    DELIVERY_PLAN = "delivery_plan"           # assembled {..., text = kalai formats[variant], verbatim}

    # Message.
    DRAFT = "draft"                   # Outreach Writer's founder-voice draft
    CLAIM_REPORT = "claim_report"     # Claim Judge (Claude) {claim_support, ...}

    # Claim-Judge rewrite loop (deterministic).
    CLAIM_ROUND = "claim_round"
    CLAIM_SUPPORT = "claim_support"
    CLAIM_VERIFIED = "claim_verified"
    CLAIM_HISTORY = "claim_history"

    # Channel (eligibility + ledger; publish is the HITL, not in root_agent).
    SEND_ELIGIBLE = "send_eligible"
    SEND_REASON = "send_reason"
    GATE_STATUS = "gate_status"       # awaiting_approval | no_safe_message
    POST = "post"                     # the assembled, verified post for the gate

    TRANSCRIPT = "engagement_transcript"
