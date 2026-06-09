"""arivu — central configuration & contracts.

This module is the single source of truth every other module imports. It holds:
  * run-mode detection (live vs. deterministic offline replay),
  * model ids and the regions Gemini / Claude target on Vertex,
  * the deterministic chamber thresholds (debate convergence, defensibility),
  * the session-state key names that form the contract between pipeline stages,
  * the demo org profile.

Keep this import-light (stdlib + dotenv only) so it can be imported from tools,
tests, and the deployment script without pulling in the ADK runtime.
"""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

# Load .env next to the project root if present (no-op in deployed runtimes).
load_dotenv(Path(__file__).resolve().parent.parent / ".env")


def _flag(name: str, default: bool) -> bool:
    return os.environ.get(name, str(default)).strip().lower() in ("1", "true", "yes", "on")


def _num(name: str, default: float) -> float:
    try:
        return float(os.environ.get(name, default))
    except (TypeError, ValueError):
        return default


def _int(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, default))
    except (TypeError, ValueError):
        return default


# ─── Models ──────────────────────────────────────────────────────────────────
# Routine intelligence (chair-orchestration + the five mantris) on Gemini.
MODEL_CHAIR = os.environ.get("ARIVU_MODEL_CHAIR", "gemini-2.5-pro")
MODEL_MANTRI = os.environ.get("ARIVU_MODEL_MANTRI", "gemini-2.5-flash")
# Decision intelligence (verdict synthesis + adversarial prosecution) on Claude
# via Vertex AI Model Garden — the challenge's third-party-LLM-via-Vertex path.
MODEL_VERDICT = os.environ.get("ARIVU_MODEL_VERDICT", "claude-opus-4-1@20250805")
MODEL_PROSECUTOR = os.environ.get("ARIVU_MODEL_PROSECUTOR", "claude-opus-4-1@20250805")

# ─── Vertex regions ──────────────────────────────────────────────────────────
GOOGLE_CLOUD_PROJECT = os.environ.get("GOOGLE_CLOUD_PROJECT", "")
GEMINI_LOCATION = os.environ.get("GOOGLE_CLOUD_LOCATION", "global")
# Claude on Vertex is region-restricted; keep it independent of the Gemini region.
CLAUDE_LOCATION = os.environ.get("ARIVU_CLAUDE_LOCATION", "us-east5")

# ─── Deterministic chamber thresholds ────────────────────────────────────────
# These never depend on what any model says — they are the safety property.
DEFENSIBILITY_THRESHOLD = _num("ARIVU_DEFENSIBILITY_THRESHOLD", 0.80)
CONVERGENCE_THRESHOLD = _num("ARIVU_CONVERGENCE_THRESHOLD", 0.75)
MAX_DEBATE_ROUNDS = _int("ARIVU_MAX_DEBATE_ROUNDS", 3)
MAX_PROSECUTION_ROUNDS = _int("ARIVU_MAX_PROSECUTION_ROUNDS", 3)

# ─── Grounding (example MCP — the org's own live numbers) ──────────────────────
EXAMPLE_MCP_URL = os.environ.get("EXAMPLE_MCP_URL", "https://mcp.example.com/mcp")
EXAMPLE_MCP_SECRET_FILE = os.path.expanduser(
    os.environ.get("EXAMPLE_MCP_SECRET_FILE", "~/.example_mcp_secret")
)

# ─── Safety ──────────────────────────────────────────────────────────────────
# Executor side-effects (publish resolution, planner entry, A2A dispatch, token
# spend) fire ONLY when this is False *and* a human approved at the one gate.
EXECUTOR_DRY_RUN = _flag("ARIVU_EXECUTOR_DRY_RUN", True)

# ─── Observability ───────────────────────────────────────────────────────────
OTEL_CONSOLE = _flag("ARIVU_OTEL_CONSOLE", True)
BIGQUERY_DATASET = os.environ.get("ARIVU_BIGQUERY_DATASET", "")


# ─── Run-mode detection ──────────────────────────────────────────────────────
def creds_available() -> bool:
    """True when live LLM credentials look resolvable.

    Vertex path: a project id plus ADC on disk (or an explicit SA key).
    Gemini-API path: a GOOGLE_API_KEY / GEMINI_API_KEY.
    """
    if os.environ.get("GOOGLE_API_KEY") or os.environ.get("GEMINI_API_KEY"):
        return True
    if not GOOGLE_CLOUD_PROJECT:
        return False
    adc = Path("~/.config/gcloud/application_default_credentials.json").expanduser()
    return adc.exists() or bool(os.environ.get("GOOGLE_APPLICATION_CREDENTIALS"))


def mode() -> str:
    """Resolved run mode: 'live' or 'demo'.

    ARIVU_MODE=live|demo forces it; ARIVU_MODE=auto (default) picks live when
    creds resolve, else demo.
    """
    requested = os.environ.get("ARIVU_MODE", "auto").strip().lower()
    if requested in ("live", "demo"):
        return requested
    return "live" if creds_available() else "demo"


def is_live() -> bool:
    return mode() == "live"


def claude_live() -> bool:
    """Whether the two Claude·Vertex seats (verdict + prosecutor) run live.

    Live only when arivu is live AND Claude isn't forced off. Set
    SAAKSHE_CLAUDE_MODE=demo (or ARIVU_CLAUDE_MODE=demo) to keep the verdict +
    prosecutor on scripted replay while the five Gemini mantris run LIVE — the
    hybrid used while the Vertex Anthropic quota is pending.
    """
    if not is_live():
        return False
    for var in ("SAAKSHE_CLAUDE_MODE", "ARIVU_CLAUDE_MODE"):
        v = os.environ.get(var, "").strip().lower()
        if v in ("demo", "off", "scripted"):
            return False
        if v in ("live", "on"):
            return True
    return True


# ─── Session-state contract ──────────────────────────────────────────────────
# The keys every pipeline stage reads/writes. Centralised so the ParallelAgent
# fan-out, the debate/prosecution loops, the chair, and the executor never drift.
class StateKeys:
    QUESTION = "question"            # the founder's loaded question (input)
    ORG = "org"                      # org profile dict
    GROUNDING = "grounding"          # live numbers bundle (example MCP + A2A)
    SUBQUESTIONS = "subquestions"    # chair's decomposition
    # Mantri positions — one output_key per advisor (ParallelAgent writes these).
    POS_ECONOMIST = "pos_economist"
    POS_GROWTH = "pos_growth"
    POS_BRAND = "pos_brand"
    POS_RISK = "pos_risk"
    POS_OPS = "pos_ops"
    # Debate loop.
    DEBATE_ROUND = "debate_round"
    DEBATE_TRANSCRIPT = "debate_transcript"
    DEBATE_HISTORY = "debate_history"
    CONVERGENCE = "convergence_score"
    DEBATE_DONE = "debate_done"
    # Verdict ↔ prosecution loop.
    VERDICT = "verdict"              # {decision, reasons[], dissent, confidence}
    PROSECUTION = "prosecution"      # {attack, rebuttal, defensibility, survived}
    PROSECUTION_ROUND = "prosecution_round"
    PROSECUTION_HISTORY = "prosecution_history"
    DEFENSIBILITY = "defensibility"
    VERDICT_SURVIVED = "verdict_survived"
    # Gate + execution.
    GATE_STATUS = "gate_status"      # awaiting_approval | approved | rejected
    RESOLUTION = "resolution"        # {url, doc_id, content_hash}
    DISPATCH = "dispatch"            # {kural:{...}, kalai:{...}}
    TRANSCRIPT = "chamber_transcript"  # ordered list of transcript lines


# The five mantris, in chamber order. (key, display, output_key, gemini lens).
MANTRIS = [
    ("economist", "Economist", StateKeys.POS_ECONOMIST, "unit-economics & pricing"),
    ("growth", "Growth advocate", StateKeys.POS_GROWTH, "funnel & acquisition"),
    ("brand", "Brand & voice guardian", StateKeys.POS_BRAND, "canon & promises"),
    ("risk", "Risk · devil's advocate", StateKeys.POS_RISK, "downside-first"),
    ("ops", "Ops-feasibility", StateKeys.POS_OPS, "can-we-ship-this"),
]

# ─── Mantri ensembles (2b.1) ─────────────────────────────────────────────────
# Each mantri is no longer a lone advisor: it fans into a 3-advisor ParallelAgent
# of disjoint sub-lenses (anti-groupthink WITHIN the lens), then a deterministic
# reducer folds the three disjoint sub-claims into the SAME consolidated POS_*
# position the chamber already consumes — now carrying an `evidence` list.
#
# Per role: three (sub_lens_key, display) sub-advisors. The FIRST entry is the
# PRIMARY sub-lens — the reducer lifts the consolidated claim/confidence/stance
# verbatim from it, so the rolled-up position stays byte-identical to today's
# _POSITIONS[role]; the other two attach as cited supporting evidence.
MANTRI_ENSEMBLES = {
    "economist": [
        ("margin", "Contribution-margin"),
        ("retention", "Retention-yield"),
        ("competitor_bench", "Competitor-benchmark"),
    ],
    "growth": [
        ("acquisition", "Top-of-funnel acquisition"),
        ("conversion", "Trial→paid conversion"),
        ("positioning", "Positioning signal"),
    ],
    "brand": [
        ("promise", "Stated-promise canon"),
        ("voice", "Voice & positioning"),
        ("trust", "Customer-trust ledger"),
    ],
    "risk": [
        ("churn_cliff", "Churn-cliff downside"),
        ("competitor_undercut", "Competitor-undercut"),
        ("execution_blast", "Execution blast-radius"),
    ],
    "ops": [
        ("deploy_health", "Deploy health"),
        ("config_risk", "Config-change risk"),
        ("billing_safety", "Billing blast-radius"),
    ],
}


def ensemble_subroles(role: str) -> list[str]:
    """The three sub-advisor role keys for a mantri (namespaced `role__sublens`)."""
    return [f"{role}__{sub}" for sub, _display in MANTRI_ENSEMBLES.get(role, [])]


def ensemble_primary(role: str) -> str:
    """The primary sub-lens key for a mantri (the reducer lifts its claim/conf)."""
    subs = MANTRI_ENSEMBLES.get(role, [])
    return subs[0][0] if subs else ""

# ─── Offline fallback org (NEVER the product — the orchestrator passes the REAL
# connected company in; this only stands in for arivu's standalone self-test). No
# brand: a generic small subscription product, kept only so the elasticity math has
# a current price to reason from. ───────────────────────────────────────────────
DEFAULT_ORG = {
    "name": "the connected company",
    "kind": "small subscription product",
    "connected_days": 0,
    "memory_pack": "v1",
    "current_pro_price": 29,
}
DEFAULT_QUESTION = "Should we adjust our Pro subscription price?"
