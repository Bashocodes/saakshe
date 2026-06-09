"""kalai — session-state contract + seat roster (import-light, no ADK runtime).

Mirrors arivu's ``config.StateKeys`` + ``MANTRIS`` pattern, but kalai imports its
thresholds from the shared ``common.config`` (FIDELITY_THRESHOLD, MAX_FIDELITY_ROUNDS)
rather than defining a competing config. This module only names the keys the studio
pipeline reads/writes and the five seats, so the ParallelAgent fan-out, the
Brand-Fidelity loop, and the compliance gate never drift.

The studio (MAKES): a brief enters; a finished, on-brand, compliance-cleared
multi-platform master exits and is handed to kural. Five seats, two on Claude.
"""

from __future__ import annotations

NS = "kalai"


class StateKeys:
    # ── inputs ───────────────────────────────────────────────────────────────
    BRIEF = "brief"                  # the approved launch brief (input)
    CONTEXT_PACK = "context_pack"    # manas Context Pack dict (brand/voice rules)
    BRAND_BLOCK = "brand_block"      # rendered brand-asset-bank text for prompts

    # ── Creative Director (Claude · coordinator + taste) ─────────────────────
    CREATIVE_FRAME = "creative_frame"   # the director's frame: concept + brand guardrails

    # ── Parallel production desk (Gemini) ────────────────────────────────────
    DESIGN = "design"                # Designer/Producer output (example media spec)
    COPY = "copy"                    # Copy & SEO output (per-platform copy)

    # ── Brand-Fidelity loop (4-scorer panel + deterministic reducer + check) ──
    # The panel's four seats each write a DISJOINT sub-key (fidelity_score_sub_<lens>,
    # built by scorers._sub_state_key); the reducer folds them into FIDELITY_SCORE.
    FIDELITY_ROUND = "fidelity_round"
    FIDELITY_SCORE = "fidelity_score"     # the reducer's consolidated {"score", "subs", ...}
    FIDELITY_DONE = "fidelity_done"
    FIDELITY_PASSED = "fidelity_passed"   # crossed the threshold (vs max-round escalate)
    FIDELITY_HISTORY = "fidelity_history"

    # ── Compliance gate (Claude · fail-closed) ───────────────────────────────
    COMPLIANCE = "compliance"        # {"compliance": "cleared"|"blocked", "reasons":[...]}
    COMPLIANCE_CLEARED = "compliance_cleared"  # bool — default-deny

    # ── handoff ──────────────────────────────────────────────────────────────
    MASTER = "creative_master"       # CreativeMaster.as_dict()
    SPEND_USD = "spend_usd"          # kalai's one world-facing irreversible act
    TRANSCRIPT = "studio_transcript"


# The two parallel production seats, in desk order. (role, display, output_key, lane).
PRODUCERS = [
    ("designer", "Designer · Producer", StateKeys.DESIGN, "visual / example media"),
    ("copy", "Copy & SEO", StateKeys.COPY, "platform copy + SEO"),
]


# The four Brand-Fidelity scorer seats — kalai's chamber panel for the one
# deciding question "is it on-brand + cleared?". (lens, display, focus). The lens
# key matches scorers.WEIGHTS, the sub-state-key suffix, and the demo_subscores key
# — one name, no mapping table. All four are Gemini Flash (panel advisors).
SCORERS = [
    ("brand", "Brand-Consistency",
     "palette · lockups · grid · the asset-bank references vs. the canon"),
    ("voice", "Voice-Tone",
     "calm, candid, anti-hype — the voice rules, no exclamation-mark hype"),
    ("platform", "Platform-Fit",
     "the crop / format / length right for x · ig · linkedin"),
    ("compliance", "Compliance-Edge",
     "claims / rights / tone risk a hair before the fail-closed gate"),
]
