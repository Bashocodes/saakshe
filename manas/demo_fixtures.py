"""manas — deterministic offline replay fixtures (the OFFLINE NET, never the product).

A thin net so the full ADK pipeline runs without live credentials (CI, or surviving
a 429 mid-demo). It is NOT a company: it is brand-free, obviously-synthetic
placeholder extraction so the orchestration (Parallel / Loop / escalate / commit)
exercises end-to-end. The PRODUCT is always empty until you connect a real source,
then live Gemini reads it — these scripts only stand in when there are no creds.

This module is the demo payload RESOLVER registered with the shared scripted model:
``scripted_payload(role, llm_request) -> role-appropriate text/JSON``. The committed
memory lives in ``common.project.STORE`` (filled by a real ingestion); these fixtures
only script what each ADK seat *says* when replayed offline.
"""

from __future__ import annotations

import json

from .tools import corpus

# Public corpus accessors kept here for backward-compat with callers that import
# fx.context_pack / fx.founder_voice (both now read the project store via corpus).
context_pack = corpus.context_pack
founder_voice = corpus.founder_voice


# ─── Synthetic per-channel extraction (brand-free; covers the 4 required dims) ──
# Obviously generic: a small subscription web product. No real company is named.
# Covers pricing / audience / voice / channel so an offline ingest grounds cleanly
# (zero contradictions, zero missing-field questions) — the live example run is where
# real, specific facts and real clarifying questions come from.
_INGEST = {
    "repo": {
        "channel": "repo",
        "claims": [
            {"claim": "The product is a web app with a free tier and a paid Pro tier.",
             "source": "README.md"},
            {"claim": "Pro is billed monthly per user.", "source": "package.json · pricing notes"},
        ],
        "voice_rules": ["plain and direct"],
        "brand_rules": ["honor existing subscribers on any change"],
    },
    "web": {
        "channel": "web",
        "claims": [
            {"claim": "The site positions the product for independent makers and small teams.",
             "source": "homepage"},
            {"claim": "The pricing page lists a Pro plan with monthly billing.", "source": "/pricing"},
        ],
        "voice_rules": ["warm, never hypey"],
        "brand_rules": ["no dark-pattern urgency"],
    },
    "docs": {
        "channel": "docs",
        "claims": [
            {"claim": "The docs describe onboarding and the core workflow.",
             "source": "docs/overview.md"},
        ],
        "voice_rules": [],
        "brand_rules": [],
    },
    "social": {
        "channel": "social",
        "claims": [
            {"claim": "The company posts product updates on its main social channel.",
             "source": "social handle"},
        ],
        "voice_rules": [],
        "brand_rules": [],
    },
}

# All channels' claims, as the Curator would synthesise them (every claim cited,
# non-contradictory → groundedness clears the bar, computed in tools/curator.py).
_COMMIT_CLAIMS = [c for blob in _INGEST.values() for c in blob["claims"]]


def _curation(round_: int, version_to: str) -> dict:
    """The Curator's synthesis for a round (offline learn-narrative).

    Round 1 is honestly under-grounded (one claim still uncited) so the verify loop
    does NOT commit on the first pass; round 2 cites every claim → commit."""
    if round_ <= 1:
        claims = []
        for i, c in enumerate(_COMMIT_CLAIMS):
            claims.append({"claim": c["claim"], "source": "" if i == 0 else c["source"]})
        return {"claims": claims, "contradictions": [], "groundedness": 0.7,
                "version_to": version_to, "note": "first pass — one signal still needs its source"}
    return {"claims": [dict(c) for c in _COMMIT_CLAIMS], "contradictions": [],
            "groundedness": 0.9, "version_to": version_to,
            "note": "revised — every claim now cites an imbibed source"}


# ─── The scripted resolver (role, llm_request) -> text ───────────────────────
def scripted_payload(role: str, llm_request=None) -> str:
    """Return the canned output for a manas seat in deterministic-replay mode."""
    if role == "mind_keeper":
        return json.dumps(
            {"topic": "company", "imbibe": ["repo", "web", "docs", "social"],
             "why": "ground the company's memory across every connected channel"}
        )
    if role in _INGEST:                       # one of the four channel readers
        # Honest per-channel: a channel with no connected source extracts nothing
        # (the instruction carries the "(no source connected…)" marker).
        if "(no source connected for this channel)" in _request_text(llm_request):
            return json.dumps({"channel": role, "claims": [], "voice_rules": [], "brand_rules": []})
        return json.dumps(_INGEST[role])
    if role == "curator":
        rnd = 2
        version_to = _version_to_from_request(llm_request)
        if llm_request is not None:
            text = _request_text(llm_request)
            if "CURATE_ROUND::1" in text:
                rnd = 1
            elif "CURATE_ROUND::2" in text:
                rnd = 2
        return json.dumps(_curation(rnd, version_to))
    if role == "founder_voice":
        question = _question_from_request(llm_request)
        answer, cites, refused = corpus.founder_voice_lookup(question)
        return json.dumps({"answer": answer, "citations": cites, "refused": refused})
    return "Acknowledged."


# ─── request introspection helpers ───────────────────────────────────────────
def _request_text(llm_request) -> str:
    """The system instruction text (where the loop's round marker lives)."""
    try:
        cfg = getattr(llm_request, "config", None)
        si = getattr(cfg, "system_instruction", "") if cfg else ""
        return str(si or "")
    except Exception:
        return ""


def _question_from_request(llm_request) -> str:
    """Pull ONLY the founder's question out of the request (wrapped in a marker)."""
    sys_text = _request_text(llm_request)
    if "[[VOICE_Q::" in sys_text and "::VOICE_Q]]" in sys_text:
        try:
            return sys_text.split("[[VOICE_Q::", 1)[1].split("::VOICE_Q]]", 1)[0]
        except Exception:
            pass
    parts: list[str] = []
    try:
        for content in getattr(llm_request, "contents", []) or []:
            for p in getattr(content, "parts", []) or []:
                t = getattr(p, "text", None)
                if t:
                    parts.append(str(t))
    except Exception:
        pass
    return "\n".join(parts)


from common import config as _config  # noqa: E402


def _version_to_from_request(llm_request) -> str:
    """The target version the loop threaded in (defaults to canon's offline label)."""
    text = _request_text(llm_request)
    marker = "VERSION_TO::"
    if marker in text:
        try:
            return text.split(marker, 1)[1].split()[0].strip()
        except Exception:
            pass
    return _config.CANON["context_pack_to"]
