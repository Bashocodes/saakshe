"""saakshe.common — shared configuration & contracts for the whole company.

ONE source of truth the four quadrants + the witness + the orchestrator import.
It holds: run-mode (demo vs live, kept consistent across every quadrant), model
ids and the Vertex regions Gemini / Claude target, the company profile and the
*sealed canon numbers* every demo fixture must reproduce, and the forbidden-value
list no surface may ever present as canon.

Keep this import-light (stdlib + dotenv only) so tools/tests/deploy can import it
without pulling in the ADK runtime.

Run-mode is deliberately shared with arivu: arivu (the already-shipped, untouched
module) reads ``ARIVU_MODE``; the rest of the company reads ``SAAKSHE_MODE``.
``mode()`` honours either, and :func:`sync_runtime_mode` pushes the resolved mode
back into ``ARIVU_MODE`` so the whole flywheel runs in one mode at once — never
arivu live while kalai is replaying.
"""

from __future__ import annotations

import os
from pathlib import Path

try:  # dotenv is optional in deployed runtimes
    from dotenv import load_dotenv

    load_dotenv(Path(__file__).resolve().parent.parent / ".env")
except Exception:  # noqa: BLE001
    pass


# ─── env helpers ─────────────────────────────────────────────────────────────
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
# Routine intelligence on Gemini; the two highest-stakes seats per quadrant on
# Claude via Vertex AI Model Garden — the challenge's third-party-LLM-via-Vertex
# path, deliberately a separate, stronger model than the one it must now judge.
# Defaults mirror the probe-verified ids in .env (2026-06-08) so a missing .env
# falls back to models this project actually serves, not stale ones.
MODEL_PRO = os.environ.get("SAAKSHE_MODEL_PRO", "gemini-3.1-pro-preview")
MODEL_FLASH = os.environ.get("SAAKSHE_MODEL_FLASH", "gemini-3.5-flash")
MODEL_CLAUDE = os.environ.get("SAAKSHE_MODEL_CLAUDE", "claude-sonnet-4-6@default")

# ─── Vertex regions ──────────────────────────────────────────────────────────
GOOGLE_CLOUD_PROJECT = os.environ.get("GOOGLE_CLOUD_PROJECT", "")
GEMINI_LOCATION = os.environ.get("GOOGLE_CLOUD_LOCATION", "global")
# Claude on Vertex is region-restricted; keep it independent of Gemini's region.
CLAUDE_LOCATION = os.environ.get("SAAKSHE_CLAUDE_LOCATION", os.environ.get("ARIVU_CLAUDE_LOCATION", "us-east5"))

# ─── Grounding (example MCP — the org's own live numbers / assets) ─────────────
EXAMPLE_MCP_URL = os.environ.get("EXAMPLE_MCP_URL", "https://mcp.example.com/mcp")
EXAMPLE_MCP_SECRET_FILE = os.path.expanduser(
    os.environ.get("EXAMPLE_MCP_SECRET_FILE", "~/.example_mcp_secret")
)

# ─── Safety ──────────────────────────────────────────────────────────────────
# Every quadrant executor (manas commit, kalai spend, kural send/publish) fires a
# real side effect ONLY when dry_run is False *and* a human approved at a gate.
EXECUTOR_DRY_RUN = _flag("SAAKSHE_EXECUTOR_DRY_RUN", True)

# ─── Observability ───────────────────────────────────────────────────────────
OTEL_CONSOLE = _flag("SAAKSHE_OTEL_CONSOLE", True)
BIGQUERY_DATASET = os.environ.get("SAAKSHE_BIGQUERY_DATASET", "")


# ─── Run-mode detection (shared with arivu) ──────────────────────────────────
def creds_available() -> bool:
    """True when live LLM credentials look resolvable (Vertex ADC or an API key)."""
    if os.environ.get("GOOGLE_API_KEY") or os.environ.get("GEMINI_API_KEY"):
        return True
    if not GOOGLE_CLOUD_PROJECT:
        return False
    adc = Path("~/.config/gcloud/application_default_credentials.json").expanduser()
    return adc.exists() or bool(os.environ.get("GOOGLE_APPLICATION_CREDENTIALS"))


def mode() -> str:
    """Resolved run mode: 'live' or 'demo'.

    ``SAAKSHE_MODE`` wins, then ``ARIVU_MODE`` (so the already-shipped module's
    flag still drives the whole company), then auto-detect from creds.
    """
    for var in ("SAAKSHE_MODE", "ARIVU_MODE"):
        requested = os.environ.get(var, "").strip().lower()
        if requested in ("live", "demo"):
            return requested
    return "live" if creds_available() else "demo"


def is_live() -> bool:
    return mode() == "live"


def claude_live() -> bool:
    """Whether the 8 Claude·Vertex seats run live.

    Live only when the company is live AND Claude isn't explicitly forced off.
    Set SAAKSHE_CLAUDE_MODE=demo (or ARIVU_CLAUDE_MODE=demo) to keep the Claude
    seats on deterministic scripted replay while Gemini runs LIVE — the hybrid
    used while the Vertex Anthropic quota is pending. The orchestration (Parallel/
    Loop/escalate/gates/A2A) is identical; only the Claude token source differs.
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


def sync_runtime_mode() -> str:
    """Pin every quadrant (incl. untouched arivu) to one resolved mode + push the
    resolved Vertex settings into the env ADK reads at call time. Call once at
    orchestrator/server boot so the whole flywheel runs in a single mode."""
    resolved = mode()
    os.environ["SAAKSHE_MODE"] = resolved
    os.environ["ARIVU_MODE"] = resolved  # arivu only reads this one
    if resolved == "live":
        os.environ.setdefault("GOOGLE_GENAI_USE_VERTEXAI", "TRUE")
        if GOOGLE_CLOUD_PROJECT:
            os.environ.setdefault("GOOGLE_CLOUD_PROJECT", GOOGLE_CLOUD_PROJECT)
        os.environ.setdefault("GOOGLE_CLOUD_LOCATION", GEMINI_LOCATION)
        os.environ.setdefault("ARIVU_CLAUDE_LOCATION", CLAUDE_LOCATION)
    return resolved


# ─── The company ─────────────────────────────────────────────────────────────
# saakshe (witness/product) · manas (knows) · arivu (decides) · kalai (makes) ·
# kural (engages). Verb identities are user-locked canon; do not re-map.
QUADRANTS = {
    "manas": {"verb": "knows", "seats": 7, "claude_seats": 2, "hue": "#88602c"},
    "arivu": {"verb": "decides", "seats": 9, "claude_seats": 2, "hue": "#5166a7"},
    "kalai": {"verb": "makes", "seats": 5, "claude_seats": 2, "hue": "#b35a4e"},
    "kural": {"verb": "engages", "seats": 7, "claude_seats": 2, "hue": "#3e725f"},
}
TOTAL_SEATS = sum(q["seats"] for q in QUADRANTS.values())          # 28
TOTAL_CLAUDE_SEATS = sum(q["claude_seats"] for q in QUADRANTS.values())  # 8

# NO canned company. The product boots empty and runs on the founder's REAL
# connected project — the org comes from ``common.project.STORE.org_for_flywheel()``
# (filled by a real manas ingestion), never a fixture here. Modules that need a
# placeholder when state carries no org fall back to ``{}`` (→ "the company"), and
# the orchestrator returns an empty-state "connect first" response when ungrounded.
# (DEFAULT_ORG / DEFAULT_QUESTION removed — see common/project.py.)

# ─── Offline replay net (NOT the product's data — never surfaced) ─────────────
# The creds-free / survive-a-429 net that lets the ADK orchestration (Parallel /
# Loop / escalate / gates / A2A) run and the suite stay green WITHOUT live models.
# These are the internal finals the per-quadrant demo fixtures replay so the
# offline run is self-consistent. They are brand-free and the product never shows
# them: it is empty until you connect, then every fact comes from your real
# Context Pack. (Real ingestion versions come from the ProjectStore: v0→v1→…, not
# the context_pack_from/to below, which only label the offline learn-the-day net.)
CANON = {
    "verdict_decision": "Raise the Pro tier modestly, grandfather existing subscribers, give 30-day notice.",
    "verdict_price_to": 34,
    "verdict_confidence": 0.88,
    "defensibility_final": 0.84,        # survives ≥ 0.80
    "fidelity_climb": [6.8, 8.4, 9.1],  # kalai Brand-Fidelity loop; passes at the top
    "fidelity_pass": 9.1,
    "claim_support": 0.86,              # kural Claim-Judge passes ≥ 0.80
    "context_pack_from": "v14",
    "context_pack_to": "v15",
    "resolution_slug": "pricing-decision-2026-06",
}

# Values that must NEVER be presented as canon (animation midpoints / retired names).
FORBIDDEN = {
    "numbers": [0.62, 0.81],   # prosecutor pre-survival / chair pre-prosecution midpoints
    "names": ["saksi", "sākṣī", "saksī", "buddhi", "rasa", "doota", "sakshi"],
    "note": "no Devanagari, no IAST diacritics; only saakshe/manas/arivu/kalai/kural/setu",
}

# ─── Deterministic thresholds (the safety property — never model-dependent) ──
# arivu (mirrored from its own config so the orchestrator agrees):
DEFENSIBILITY_THRESHOLD = _num("SAAKSHE_DEFENSIBILITY_THRESHOLD", 0.80)
CONVERGENCE_THRESHOLD = _num("SAAKSHE_CONVERGENCE_THRESHOLD", 0.75)
# kalai brand-fidelity loop:
FIDELITY_THRESHOLD = _num("SAAKSHE_FIDELITY_THRESHOLD", 8.5)
MAX_FIDELITY_ROUNDS = _int("SAAKSHE_MAX_FIDELITY_ROUNDS", 3)
# kural claim-judge gate:
CLAIM_THRESHOLD = _num("SAAKSHE_CLAIM_THRESHOLD", 0.80)
MAX_CLAIM_ROUNDS = _int("SAAKSHE_MAX_CLAIM_ROUNDS", 2)
# manas curator verify loop:
GROUNDING_THRESHOLD = _num("SAAKSHE_GROUNDING_THRESHOLD", 0.80)
MAX_CURATE_ROUNDS = _int("SAAKSHE_MAX_CURATE_ROUNDS", 3)
